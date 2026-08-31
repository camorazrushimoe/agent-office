#!/usr/bin/env python3
"""Deterministic validation for crew/crew-send.py (no LLM, no pytest).

Run:  python3 crew/validate_crew_send.py
Exit: 0 on success, 1 on any failed check.

Covers the wake-on-failure contract (spec: add-door-client-wake-path):
  - wake target derivation: container_url host -> controller-recognized id,
    wake_hint override, team:role -> team-role normalization
  - wake decision: 4xx -> no wake; connection failure / 5xx -> wake
  - health URL derivation from the delivery door URL
  - orchestration: wake then re-deliver; non-zero (WakeError) on wake or
    re-delivery failure; no silent drop
  - plain-path degradation for instance registries (no host_url)
  - team-qualified wake actor (TEAM_NAME) with CREW_SEND_ACTOR override
  - canonical client rule: no divergent per-instance copies, mount present
    on every agent service
"""
from __future__ import annotations

import importlib.util
import json
import os
import sys
import tempfile
import urllib.error
from unittest import mock

HERE = os.path.dirname(os.path.abspath(__file__))   # crew
if HERE not in sys.path:
    sys.path.insert(0, HERE)

# crew-send.py has a hyphen in its filename, so it cannot be imported by
# module name; load it explicitly by path.
_spec = importlib.util.spec_from_file_location(
    "crew_send", os.path.join(HERE, "crew-send.py"))
assert _spec and _spec.loader
crew_send = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(crew_send)

FAILURES: list[str] = []


def check(name: str, got, want) -> None:
    ok = got == want
    print(f"{'PASS' if ok else 'FAIL'}  {name}: {got!r}"
          + ("" if ok else f"  (want {want!r})"))
    if not ok:
        FAILURES.append(name)


def check_true(name: str, cond: bool) -> None:
    print(f"{'PASS' if cond else 'FAIL'}  {name}")
    if not cond:
        FAILURES.append(name)


def test_wake_target_derivation() -> None:
    # Registry key `developer` in dev-1 -> container_url host dev-1-developer
    # (the exact id/container factory-control registers).
    cfg = {"container_url": "http://dev-1-developer:8644/webhooks/inbox",
           "secret": "s"}
    check("dev-1 developer -> dev-1-developer",
          crew_send.wake_target(cfg), "dev-1-developer")
    check("office architect -> architect",
          crew_send.wake_target(
              {"container_url": "http://architect:8644/webhooks/inbox",
               "secret": "s"}),
          "architect")

    # wake_hint overrides and is normalized team:role -> team-role.
    cfg = {"container_url": "http://wrong-host:8644/webhooks/inbox",
           "wake_hint": "dev-1:developer", "secret": "s"}
    check("wake_hint overrides container_url host",
          crew_send.wake_target(cfg), "dev-1-developer")
    check("wake_hint hyphenated passthrough",
          crew_send.wake_target(
              {"container_url": "http://x:8644/", "wake_hint": "lab-1-evaluation",
               "secret": "s"}),
          "lab-1-evaluation")

    # No container_url host, no hint -> empty (caller must fail loudly).
    check("missing both -> empty target",
          crew_send.wake_target({"secret": "s"}), "")


def test_wake_decision() -> None:
    check("4xx -> no wake",
          crew_send.should_wake(urllib.error.HTTPError(
              "url", 401, "Unauthorized", None, None)), False)
    check("404 -> no wake",
          crew_send.should_wake(urllib.error.HTTPError(
              "url", 404, "Not Found", None, None)), False)
    check("5xx -> wake",
          crew_send.should_wake(urllib.error.HTTPError(
              "url", 503, "Unavailable", None, None)), True)
    check("connection refused -> wake",
          crew_send.should_wake(ConnectionRefusedError()), True)
    check("timeout -> wake",
          crew_send.should_wake(TimeoutError()), True)


def test_health_url() -> None:
    check("container door -> /health",
          crew_send.health_url("http://dev-1-developer:8644/webhooks/inbox"),
          "http://dev-1-developer:8644/health")
    check("host door -> /health",
          crew_send.health_url("http://127.0.0.1:8661/webhooks/inbox"),
          "http://127.0.0.1:8661/health")


def test_wait_healthy() -> None:
    class FakeResp:
        status = 200

        def __enter__(self):
            return self

        def __exit__(self, *a):
            return False

    with mock.patch.object(crew_send.urllib.request, "urlopen",
                           return_value=FakeResp()):
        check_true("wait_healthy: 200 -> True",
                   crew_send.wait_healthy("http://x:8644/health",
                                          timeout_s=5.0, poll_s=0.01))
    with mock.patch.object(crew_send.urllib.request, "urlopen",
                           side_effect=ConnectionRefusedError("down")):
        check_true("wait_healthy: never healthy -> False",
                   not crew_send.wait_healthy("http://x:8644/health",
                                              timeout_s=0.05, poll_s=0.01))


def test_wake_actor() -> None:
    with mock.patch.dict(os.environ, {}, clear=False):
        os.environ.pop("TEAM_NAME", None)
        os.environ.pop("CREW_SEND_ACTOR", None)
        check("actor: default", crew_send.wake_actor(), "crew-send")
        os.environ["TEAM_NAME"] = "dev-1"
        check("actor: team-qualified", crew_send.wake_actor(), "dev-1/crew-send")
        os.environ["CREW_SEND_ACTOR"] = "custom-actor"
        check("actor: CREW_SEND_ACTOR override",
              crew_send.wake_actor(), "custom-actor")


def test_publish_wake_delegation() -> None:
    calls: list[tuple] = []

    class FakeBusClient:
        pass

    def fake_send_wake(bus, agent_id, reason="", actor="lifecycle"):
        calls.append((agent_id, reason, actor))
        return 2

    with mock.patch.object(crew_send, "load_bus_client",
                           return_value=(FakeBusClient, fake_send_wake)), \
         mock.patch.dict(os.environ, {"TEAM_NAME": "spec-1"}, clear=False):
        crew_send.publish_wake("spec-1-technical-product-manager", "tech-pm")
    check("publish_wake: delegates with derived target",
          calls[0][0], "spec-1-technical-product-manager")
    check_true("publish_wake: actor team-qualified",
               calls[0][2] == "spec-1/crew-send")
    check_true("publish_wake: reason mentions the delivery",
               "door-down" in calls[0][1])


def _registry_with_developer() -> dict:
    return {
        "developer": {
            "container_url": "http://dev-1-developer:8644/webhooks/inbox",
            "secret": "s3cret",
        }
    }


def _make_deliver(calls: dict, first_failure: str = "refused"):
    """_post stand-in: first call fails (refused or HTTP 503), then 202."""
    def _deliver(url, payload, secret):
        calls["deliver"] += 1
        if calls["deliver"] == 1:
            if first_failure == "refused":
                raise ConnectionRefusedError("refused")
            raise urllib.error.HTTPError(
                url, 503, "Unavailable", None, None)
        return 202, "accepted"
    return _deliver


def test_send_wake_redeliver() -> None:
    """Door down (connection refused) -> wake -> /health 200 -> re-deliver."""
    calls = {"deliver": 0, "wake": [], "healthy_calls": 0}
    with mock.patch.object(crew_send, "load_registry",
                           return_value=_registry_with_developer()), \
         mock.patch.object(crew_send, "_post",
                           side_effect=_make_deliver(calls, "refused")), \
         mock.patch.object(crew_send, "publish_wake",
                           side_effect=lambda t, a, actor=None: calls["wake"].append(t)), \
         mock.patch.object(crew_send, "wait_healthy",
                           side_effect=lambda url, timeout_s=90.0, poll_s=3.0:
                               calls.__setitem__("healthy_calls",
                                                 calls["healthy_calls"] + 1) or True):
        status, body = crew_send.send("developer", "hello", use_container=True)
    check("send: re-delivered after wake -> 202", (status, body), (202, "accepted"))
    check_true("send: woke once with derived target",
               calls["wake"] == ["dev-1-developer"])
    check_true("send: delivered twice (initial + re-delivery)",
               calls["deliver"] == 2)
    check_true("send: waited for health", calls["healthy_calls"] >= 1)


def test_send_5xx_wakes() -> None:
    """Door answers 503 (up but unhealthy) -> wake -> re-deliver."""
    calls = {"deliver": 0, "wake": [], "healthy_calls": 0}
    with mock.patch.object(crew_send, "load_registry",
                           return_value=_registry_with_developer()), \
         mock.patch.object(crew_send, "_post",
                           side_effect=_make_deliver(calls, "http503")), \
         mock.patch.object(crew_send, "publish_wake",
                           side_effect=lambda t, a, actor=None: calls["wake"].append(t)), \
         mock.patch.object(crew_send, "wait_healthy", return_value=True):
        status, body = crew_send.send("developer", "hello", use_container=True)
    check("send: 5xx first -> wake -> re-deliver", (status, body), (202, "accepted"))
    check_true("send: 5xx woke once", calls["wake"] == ["dev-1-developer"])


def test_send_4xx_no_wake() -> None:
    """4xx is a client error (door up) — never wake, fail loudly."""
    calls = {"deliver": 0, "wake": [], "healthy_calls": 0}

    def _deliver(url, payload, secret):
        calls["deliver"] += 1
        raise urllib.error.HTTPError(url, 401, "Unauthorized", None, None)

    with mock.patch.object(crew_send, "load_registry",
                           return_value=_registry_with_developer()), \
         mock.patch.object(crew_send, "_post", side_effect=_deliver), \
         mock.patch.object(crew_send, "publish_wake",
                           side_effect=lambda t, a, actor=None: calls["wake"].append(t)):
        try:
            crew_send.send("developer", "hello", use_container=True)
            check_true("send: 4xx raised HTTPError", False)
        except urllib.error.HTTPError as e:
            check_true("send: 4xx raised HTTPError", e.code == 401)
            check_true("send: 4xx never woke", calls["wake"] == [])


def test_send_wake_timeout() -> None:
    """Target never healthy -> WakeError naming the target, no silent drop."""
    calls = {"deliver": 0, "wake": [], "healthy_calls": 0}
    with mock.patch.object(crew_send, "load_registry",
                           return_value=_registry_with_developer()), \
         mock.patch.object(crew_send, "_post",
                           side_effect=_make_deliver(calls, "refused")), \
         mock.patch.object(crew_send, "publish_wake",
                           side_effect=lambda t, a, actor=None: calls["wake"].append(t)), \
         mock.patch.object(crew_send, "wait_healthy", return_value=False):
        try:
            crew_send.send("developer", "hello", use_container=True)
            check_true("send: wake timeout raised WakeError", False)
        except crew_send.WakeError as e:
            msg = str(e)
            check_true("send: wake timeout named target", "dev-1-developer" in msg)
            check_true("send: wake timeout not silent",
                       "not delivered" in msg.lower())


def test_send_redelivery_failure_after_wake() -> None:
    """Wake succeeds (health 200) but the re-delivery POST fails -> non-zero.

    Exercises send()'s wake path with a mocked bus and mocked HTTP: first
    POST raises connection refused, health comes back 200, re-delivery POST
    raises again -> WakeError (never a silent drop)."""
    with tempfile.TemporaryDirectory() as d:
        reg = os.path.join(d, "agents.json")
        with open(reg, "w", encoding="utf-8") as f:
            json.dump({"dev-1-qa": {
                "host_url": "http://127.0.0.1:8662/webhooks/inbox",
                "container_url": "http://dev-1-qa:8644/webhooks/inbox",
                "secret": "s"}}, f)

        calls: list[str] = []
        woken: list[str] = []

        class FakeResp:
            status = 200

            def read(self):
                return b"ok"

            def __enter__(self):
                return self

            def __exit__(self, *a):
                return False

        def fake_urlopen(req, timeout=30):
            url = getattr(req, "full_url", req)  # Request obj or plain URL
            calls.append(url)
            # Health probe always answers 200 — the wake succeeds.
            if url.endswith("/health"):
                return FakeResp()
            # Delivery POST: first attempt fails (door down), so does the
            # re-delivery after a successful wake.
            raise ConnectionRefusedError("door lost")

        with mock.patch.object(crew_send, "REGISTRY", reg), \
             mock.patch.object(crew_send.urllib.request, "urlopen",
                               side_effect=fake_urlopen), \
             mock.patch.object(crew_send, "publish_wake",
                               side_effect=lambda t, a, actor=None: woken.append(t)):
            try:
                crew_send.send("dev-1-qa", "msg", use_container=True)
                got = "NO ERROR"
            except crew_send.WakeError as e:
                got = str(e)

    check("re-delivery failure after wake -> WakeError (non-zero)",
          "re-delivery" in got, True)
    check_true("re-delivery failure names target", "dev-1-qa" in got)
    check_true("re-delivery failure not silent",
               "not delivered" in got.lower())
    check("wake was published before re-delivery attempt",
          woken, ["dev-1-qa"])


def test_send_wake_hint_target() -> None:
    """wake_hint overrides container_url host, normalized team:role -> team-role."""
    calls = {"deliver": 0, "wake": [], "healthy_calls": 0}
    registry = {
        "developer": {
            "container_url": "http://wrong-host:8644/webhooks/inbox",
            "secret": "s3cret",
            "wake_hint": "dev-1:developer",
        }
    }
    with mock.patch.object(crew_send, "load_registry", return_value=registry), \
         mock.patch.object(crew_send, "_post",
                           side_effect=_make_deliver(calls, "refused")), \
         mock.patch.object(crew_send, "publish_wake",
                           side_effect=lambda t, a, actor=None: calls["wake"].append(t)), \
         mock.patch.object(crew_send, "wait_healthy", return_value=True):
        crew_send.send("developer", "hello", use_container=True)
    check_true("send: wake_hint normalized to controller id",
               calls["wake"] == ["dev-1-developer"])


def test_send_plain_path_degrades_without_host_url() -> None:
    """Instance registries from derive-agents carry only container_url +
    secret; plain invocation must not KeyError on host_url (review #35 B3)."""
    seen: list[str] = []
    with mock.patch.object(crew_send, "load_registry",
                           return_value=_registry_with_developer()), \
         mock.patch.object(crew_send, "_post",
                           side_effect=lambda url, payload, secret:
                               seen.append(url) or (202, "accepted")):
        status, body = crew_send.send("developer", "hello")  # no --container
    check("plain path: no KeyError, degraded to container_url",
          seen, ["http://dev-1-developer:8644/webhooks/inbox"])


def test_send_unknown_agent_raises() -> None:
    with mock.patch.object(crew_send, "load_registry",
                           return_value={"developer": {"secret": "s"}}):
        try:
            crew_send.send("ghost", "hi", use_container=True)
            check_true("send: unknown agent raises WakeError", False)
        except crew_send.WakeError as e:
            check_true("send: unknown agent raises WakeError", "ghost" in str(e))


def test_canonical_client_rule() -> None:
    """Composition spec: exactly one door client.

    - a divergent per-instance copy is a spec violation (FAIL)
    - a byte-identical copy is migration state: tolerated but should be
      removed in favor of the mount (spec: 'verified by SHA-256 at
      instantiation/sync, and removed in favor of the mount') — same
      acceptance as office/manage_tokens.py verify_canonical_client
    - every agent service in every instance compose mounts the canonical
      file read-only at /opt/crew/crew-send.py
    """
    import hashlib

    office_root = os.path.abspath(os.path.join(HERE, ".."))
    canonical = os.path.join(HERE, "crew-send.py")
    with open(canonical, "rb") as f:
        sha = hashlib.sha256(f.read()).hexdigest()

    instances = os.path.join(office_root, "instances")
    divergent: list[str] = []
    identical_copies: list[str] = []
    for inst in sorted(os.listdir(instances)):
        crew_dir = os.path.join(instances, inst, "crew")
        if not os.path.isdir(crew_dir):
            continue
        for name in sorted(os.listdir(crew_dir)):
            if name == "crew-send.py":
                p = os.path.join(crew_dir, name)
                with open(p, "rb") as f:
                    same = hashlib.sha256(f.read()).hexdigest() == sha
                (identical_copies if same else divergent).append(
                    f"{inst}/crew/{name}")
    check("no divergent per-instance crew-send.py copies", divergent, [])
    if identical_copies:
        print("WARN  byte-identical per-instance copies remain (remove in "
              f"favor of the mount): {', '.join(identical_copies)}")

    # every agent service in every instance compose mounts the canonical file
    missing_mounts = []
    for inst in sorted(os.listdir(instances)):
        compose = os.path.join(instances, inst, "docker-compose.yml")
        if not os.path.isfile(compose):
            continue
        with open(compose, encoding="utf-8") as f:
            lines = f.read().splitlines()
        # split into service blocks under the top-level `services:` section:
        # a 2-space-indented `  name:` line, followed by 6-space volume mounts.
        # APPROXIMATION: this is a deterministic structural check, not a YAML
        # parser — it relies on the repo's uniform compose indentation and
        # only inspects volume lines; `docker compose config` is the real
        # syntax gate and is run separately at deploy time.
        current = None
        services = {}
        in_services = False
        for ln in lines:
            if not in_services:
                if ln.strip() == "services:":
                    in_services = True
                continue
            if ln.startswith("  ") and not ln.startswith("   ") and ln.rstrip().endswith(":"):
                current = ln.strip().rstrip(":")
                services.setdefault(current, [])
            elif ln.startswith("      - ") and current is not None:
                services[current].append(ln.strip())
        for svc, mounts in services.items():
            if not any("crew-send.py:/opt/crew/crew-send.py:ro" in m for m in mounts):
                missing_mounts.append(f"{inst}/{svc}")
    check("every agent service mounts the canonical client", missing_mounts, [])


def main() -> int:
    test_wake_target_derivation()
    test_wake_decision()
    test_health_url()
    test_wait_healthy()
    test_wake_actor()
    test_publish_wake_delegation()
    test_send_wake_redeliver()
    test_send_5xx_wakes()
    test_send_4xx_no_wake()
    test_send_wake_timeout()
    test_send_redelivery_failure_after_wake()
    test_send_wake_hint_target()
    test_send_plain_path_degrades_without_host_url()
    test_send_unknown_agent_raises()
    test_canonical_client_rule()
    print()
    if FAILURES:
        print(f"FAILURES ({len(FAILURES)}): {FAILURES}")
        return 1
    print("ALL PASS")
    return 0


if __name__ == "__main__":
    sys.exit(main())
