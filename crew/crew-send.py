#!/usr/bin/env python3
"""Agent Office — canonical door client (send a message to an Office agent).

Signs the request with HMAC-SHA256 (X-Hub-Signature-256) and POSTs to
/webhooks/inbox. The agent processes asynchronously; this client confirms
receipt (typically 202).

Wake-on-failure (agent-lifecycle sender side): when the target door is down
(connection refused, timeout, or a 5xx answer) the client publishes an
`agent.wake` envelope for the controller-recognized target id, waits for the
door's `/health` to answer 200 (up to WAKE_TIMEOUT_S, default 90s), then
re-delivers the original message. It exits non-zero — never silently drops —
if the wake or the re-delivery fails. 4xx answers are door-up rejections and
never trigger a wake. The wake target is the host of the entry's
`container_url` in crew/agents.json (an entry MAY carry a `wake_hint`
override, normalized `team:role` -> `team-role`).

Usage:
  python3 crew/crew-send.py scrum-master "what is the status of the office?"
  python3 crew/crew-send.py developer "review foundation" --container

Requires crew/agents.json (copy from agents.example.json).
Stdlib only; the wake path uses the office bus client (office/bus/client.py).
"""
from __future__ import annotations

import hashlib
import hmac
import json
import os
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from typing import TypeGuard

HERE = os.path.dirname(os.path.abspath(__file__))
REGISTRY = os.path.join(HERE, "agents.json")

WAKE_TIMEOUT_S = float(os.environ.get("WAKE_TIMEOUT_S", "90"))
HEALTH_INTERVAL_S = float(os.environ.get("HEALTH_INTERVAL_S", "5"))
DELIVERY_TIMEOUT_S = float(os.environ.get("DELIVERY_TIMEOUT_S", "30"))
CREW_SEND_ACTOR = os.environ.get("CREW_SEND_ACTOR", "crew-send")


class CrewSendError(RuntimeError):
    """Delivery failed and the message was not (and will not be) delivered."""


def _office_lib() -> str:
    """Directory containing the office bus client (bus/client.py).

    Inside instance/office containers the office tree is mounted at
    /opt/office-lib; from a repo checkout it lives at <repo>/office.
    """
    env = os.environ.get("OFFICE_LIB", "")
    if env and os.path.isdir(os.path.join(env, "bus")):
        return env
    repo_office = os.path.join(os.path.dirname(HERE), "office")
    for candidate in (repo_office, "/opt/office-lib"):
        if os.path.isdir(os.path.join(candidate, "bus")):
            return candidate
    return repo_office


sys.path.insert(0, _office_lib())
from bus.client import INBOX_PREFIX, BusClient, make_envelope, publish_event  # noqa: E402, pyright: ignore[reportMissingImports]


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


# ---- wake target derivation ----------------------------------------------

def derive_wake_target(cfg: dict) -> str:
    """Controller-recognized agent id to wake for a registry entry.

    The envelope target SHALL be the controller-recognized agent id: the host
    of the entry's `container_url` — per-instance registries are keyed by
    short role, so `developer` in team `dev-1` yields `dev-1-developer`,
    exactly the id/container factory-control registers ({instance}-{role}).
    An entry MAY carry an explicit `wake_hint`; if present it SHALL be used
    instead, normalizing `team:role` -> `team-role` (colon -> hyphen).
    """
    hint = cfg.get("wake_hint")
    if hint:
        return str(hint).replace(":", "-")
    host = urllib.parse.urlparse(str(cfg.get("container_url", ""))).hostname
    return host or ""


def should_wake(status: int | None) -> bool:
    """True when a failed delivery must go through the wake path.

    Door-down = connection-level failure (status None) or a 5xx answer.
    4xx means the door is UP and rejected the message — waking cannot help.
    """
    return status is None or status >= 500


def is_success(status: int | None) -> TypeGuard[int]:
    return status is not None and 200 <= status < 300


# ---- health wait ----------------------------------------------------------

def health_url_of(url: str) -> str:
    """GET /health endpoint on the same origin as a door URL."""
    parts = urllib.parse.urlsplit(url)
    return urllib.parse.urlunsplit(
        (parts.scheme, parts.netloc, "/health", "", ""))


def health_ok(url: str, timeout: float = 5.0) -> bool:
    try:
        with urllib.request.urlopen(url, timeout=timeout) as resp:
            return resp.status == 200
    except Exception:
        return False


def wait_healthy(url: str, timeout_s: float = WAKE_TIMEOUT_S,
                 interval_s: float = HEALTH_INTERVAL_S) -> bool:
    """Poll GET /health until 200 or the wake timeout elapses."""
    deadline = time.monotonic() + timeout_s
    while True:
        if health_ok(url):
            return True
        if time.monotonic() >= deadline:
            return False
        time.sleep(interval_s)


# ---- wake publish ---------------------------------------------------------

def publish_wake(target: str, reason: str, bus=None) -> int:
    """Publish agent.wake durably (office:events) and on the live inbox.

    The inbox pub/sub channel office:inbox:<target> is what the always-on
    factory-control wake listener consumes; the durable stream is what the
    re-scan consumes after a controller outage.
    """
    if bus is None:
        bus = BusClient()
    env = make_envelope(
        actor=CREW_SEND_ACTOR,
        action="agent.wake",
        target=target,
        payload={"reason": reason} if reason else None,
    )
    payload_json = json.dumps(env, ensure_ascii=False)
    published = publish_event(bus, env)
    published += bus.publish(INBOX_PREFIX + target, payload_json)
    return published


# ---- delivery -------------------------------------------------------------

def deliver(url: str, secret: str, message: str,
            timeout: float = DELIVERY_TIMEOUT_S) -> tuple[int | None, str, str]:
    """POST a signed message to a door.

    Returns (status, body, error): status is the HTTP status when the door
    answered (including 4xx/5xx); None for connection-level failures
    (refused / timeout / DNS). body is the response or error text.
    """
    payload = json.dumps({"message": message}, ensure_ascii=False)
    headers = {
        "Content-Type": "application/json",
        "X-Hub-Signature-256": sign(secret, payload),
    }
    req = urllib.request.Request(
        url, data=payload.encode("utf-8"), headers=headers, method="POST"
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return resp.status, resp.read().decode("utf-8", errors="replace"), ""
    except urllib.error.HTTPError as e:
        return e.code, e.read().decode("utf-8", errors="replace"), ""
    except Exception as e:
        return None, "", f"{type(e).__name__}: {e}"


def send(agent: str, message: str, use_container: bool = False,
         wake_timeout: float = WAKE_TIMEOUT_S) -> tuple[int, str]:
    """Deliver a message to an agent door, waking the target on door-down.

    Returns (status, body) once the door accepts the message. Raises
    CrewSendError — the message is NOT silently dropped — when:
      - the target is unknown / the wake target is underivable
      - the door answers 3xx/4xx (door up; wake cannot help)
      - the wake publish fails, the wake times out, or the re-delivery fails
    """
    registry = load_registry(REGISTRY)
    if agent not in registry:
        raise CrewSendError(
            f"Unknown agent '{agent}'. Available: {', '.join(sorted(registry))}"
        )

    cfg = registry[agent]
    url = cfg["container_url"] if use_container else cfg["host_url"]
    secret = cfg["secret"]

    status, body, err = deliver(url, secret, message)
    if is_success(status):
        return status, body
    if status is not None and status < 500:
        # Door answered 3xx/4xx — it is up but rejected the message. Waking
        # cannot help; fail loudly without the wake path.
        raise CrewSendError(
            f"[{agent}] door answered HTTP {status}: {body[:200] or '(empty)'} "
            f"— message NOT delivered (no wake: door is up)"
        )

    target = derive_wake_target(cfg)
    if not target:
        raise CrewSendError(
            f"[{agent}] delivery failed ({err or f'HTTP {status}'}) and no "
            f"wake target derivable (missing container_url host / wake_hint) "
            f"— message NOT delivered"
        )

    detail = err or f"HTTP {status}"
    try:
        publish_wake(target, f"door down for {agent} ({detail}); wake then re-deliver")
    except Exception as exc:
        raise CrewSendError(
            f"[{agent}] wake publish for '{target}' failed: {exc} "
            f"— message NOT delivered"
        ) from exc

    health = health_url_of(url)
    if not wait_healthy(health, timeout_s=wake_timeout):
        raise CrewSendError(
            f"[{agent}] wake timed out after {int(wake_timeout)}s: "
            f"'{target}' never answered {health} — message NOT delivered"
        )

    status2, body2, err2 = deliver(url, secret, message)
    if is_success(status2):
        return status2, body2
    raise CrewSendError(
        f"[{agent}] wake succeeded ('{target}' healthy) but re-delivery "
        f"failed: {err2 or f'HTTP {status2}'} — message NOT delivered"
    )


def main() -> None:
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    use_container = "--container" in sys.argv
    if len(args) < 2:
        print(__doc__)
        sys.exit(1)
    agent, message = args[0], args[1]
    try:
        status, body = send(agent, message, use_container)
    except CrewSendError as e:
        print(f"[{agent}] {e}", file=sys.stderr)
        sys.exit(1)
    except Exception as e:
        print(f"[{agent}] error: {e}", file=sys.stderr)
        sys.exit(1)
    print(f"[{agent}] {status}: {body}")


if __name__ == "__main__":
    main()
