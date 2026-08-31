#!/usr/bin/env python3
"""Agent Office — door client (send a message to an Office agent).

Signs the request with HMAC-SHA256 (X-Hub-Signature-256) and POSTs to
/webhooks/inbox. The agent processes asynchronously; this client confirms
receipt (typically 202).

Wake-on-failure (sender side of the agent-lifecycle wake contract): when the
door is down (connection refused / timeout / 5xx), the client publishes an
`agent.wake` envelope durably (`publish_event` + `office:inbox:<target>`
pub/sub via the office bus client), waits for the target's `/health` to
answer 200 up to the wake timeout, re-delivers the original message, and
exits non-zero if the wake or the re-delivery fails — the message is never
silently dropped. 4xx responses are client errors and do NOT trigger a wake.

Usage:
  python3 crew/crew-send.py scrum-master "what is the status of the office?"
  python3 crew/crew-send.py architect "review foundation" --container

Requires crew/agents.json (copy from agents.example.json).
Stdlib only for the happy path; the wake path imports the office bus client
from /opt/office-lib (or the repo-relative office/ dir).
"""
from __future__ import annotations

import hashlib
import hmac
import json
import os
import sys
import time
import urllib.error
import urllib.request
from urllib.parse import urlparse

HERE = os.path.dirname(os.path.abspath(__file__))
REGISTRY = os.path.join(HERE, "agents.json")
WAKE_TIMEOUT_S = float(os.environ.get("WAKE_TIMEOUT_S", "90"))
HEALTH_PATH = "/health"


class WakeError(RuntimeError):
    """Wake or post-wake re-delivery failed — message not delivered."""


def load_registry(path: str) -> dict:
    if not os.path.isfile(path):
        sys.exit(
            f"Missing {path}. Copy crew/agents.example.json to crew/agents.json and set secrets."
        )
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def sign(secret: str, payload: str) -> str:
    return "sha256=" + hmac.new(
        secret.encode(), payload.encode(), hashlib.sha256
    ).hexdigest()


def normalize_target(target: str) -> str:
    """Normalize `team:role` wake-hint form to canonical `team-role`."""
    return target.replace(":", "-")


def wake_target(cfg: dict) -> str:
    """Controller-recognized agent id for a registry entry.

    The envelope target SHALL be the host of the entry's `container_url`
    (e.g. the `developer` entry in team dev-1 yields `dev-1-developer` — the
    id/container factory-control registers). An explicit `wake_hint`, if
    present, overrides, normalized `team:role` -> `team-role`.
    """
    hint = cfg.get("wake_hint")
    if hint:
        return normalize_target(str(hint))
    host = urlparse(cfg.get("container_url", "")).hostname
    return host or ""


def health_url(delivery_url: str) -> str:
    """Health endpoint for a door URL (same host:port, /health path)."""
    return delivery_url.replace("/webhooks/inbox", HEALTH_PATH)


def should_wake(exc: BaseException) -> bool:
    """True when a delivery failure should trigger the wake path.

    4xx (bad signature, unknown agent, ...) is a client error — waking the
    container will not fix it, so no wake. Connection failures, timeouts and
    5xx mean the door is down/unhealthy — wake.
    """
    if isinstance(exc, urllib.error.HTTPError):
        return exc.code >= 500
    return True


def _post(url: str, payload: str, secret: str) -> tuple[int, str]:
    headers = {
        "Content-Type": "application/json",
        "X-Hub-Signature-256": sign(secret, payload),
    }
    req = urllib.request.Request(
        url, data=payload.encode("utf-8"), headers=headers, method="POST"
    )
    with urllib.request.urlopen(req, timeout=30) as resp:
        return resp.status, resp.read().decode("utf-8")


def wait_healthy(url: str, timeout_s: float, poll_s: float = 3.0) -> bool:
    """Poll GET url until it returns 200 or the timeout expires."""
    deadline = time.monotonic() + timeout_s
    while time.monotonic() < deadline:
        try:
            with urllib.request.urlopen(url, timeout=5) as resp:
                if resp.status == 200:
                    return True
        except Exception:
            pass
        time.sleep(poll_s)
    return False


def load_bus_client() -> tuple | None:
    """Import the office bus client from the standard mount locations.

    Prefers the repo-relative `office/` (fresh checkout = source of truth),
    then the deployed `/opt/office-lib` mount. Returns (BusClient,
    send_wake) or None when the bus client is not importable (wake path then
    fails loudly rather than dropping the message).
    """
    candidates = [
        os.path.abspath(os.path.join(HERE, "..", "office")),  # repo layout
        "/opt/office-lib",                 # container + deployed host mount
    ]
    for cand in candidates:
        if not os.path.isdir(os.path.join(cand, "bus")):
            continue
        sys.path.insert(0, cand)
        try:
            from bus.client import BusClient, send_wake  # noqa: F401
            return BusClient, send_wake
        except ImportError:
            sys.path.pop(0)
    return None


def publish_wake(target: str, agent: str) -> None:
    bus_mod = load_bus_client()
    if bus_mod is None:
        raise WakeError(
            f"cannot publish agent.wake for '{target}': office bus client "
            "not importable (expected /opt/office-lib)"
        )
    BusClient, send_wake = bus_mod
    send_wake(BusClient(), target,
              reason=f"door-down delivery to {agent}", actor="crew-send")


def send(agent: str, message: str, use_container: bool = False) -> tuple[int, str]:
    registry = load_registry(REGISTRY)
    if agent not in registry:
        sys.exit(f"Unknown agent '{agent}'. Available: {', '.join(sorted(registry))}")

    cfg = registry[agent]
    url = cfg["container_url"] if use_container else cfg["host_url"]
    secret = cfg["secret"]

    payload = json.dumps({"message": message}, ensure_ascii=False)

    # 1) Happy path: direct delivery.
    try:
        return _post(url, payload, secret)
    except urllib.error.HTTPError as e:
        if not should_wake(e):
            raise
        # 5xx: door up but unhealthy — fall through to wake.
    except Exception:
        # Connection refused / timeout / DNS — door down — wake.
        pass

    # 2) Wake-on-failure: publish agent.wake durably, wait for health,
    #    then re-deliver. Any failure exits non-zero (no silent drop).
    target = wake_target(cfg)
    if not target:
        raise WakeError(
            f"cannot derive wake target for '{agent}' "
            "(container_url host / wake_hint missing)"
        )
    publish_wake(target, agent)
    health = health_url(url)
    if not wait_healthy(health, WAKE_TIMEOUT_S):
        raise WakeError(
            f"wake failed: '{target}' not healthy at {health} within "
            f"{int(WAKE_TIMEOUT_S)}s"
        )
    try:
        return _post(url, payload, secret)
    except Exception as exc:
        raise WakeError(
            f"re-delivery after wake failed for '{agent}' "
            f"(target '{target}' is up): {exc}"
        ) from exc


def main() -> None:
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    use_container = "--container" in sys.argv
    if len(args) < 2:
        print(__doc__)
        sys.exit(1)
    agent, message = args[0], args[1]
    try:
        status, body = send(agent, message, use_container)
    except urllib.error.HTTPError as e:
        print(f"[{agent}] HTTP {e.code}: {e.read().decode()}")
        sys.exit(1)
    except WakeError as e:
        print(f"[{agent}] wake failed: {e}")
        sys.exit(1)
    except Exception as e:
        print(f"[{agent}] error: {e}")
        sys.exit(1)
    print(f"[{agent}] {status}: {body}")


if __name__ == "__main__":
    main()
