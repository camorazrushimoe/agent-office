#!/usr/bin/env python3
"""Deterministic validation for crew/crew-send.py (door client).

Run:  python3 scripts/validate_crew_send.py
Exit: 0 on success, 1 on any failed check.

Covers the door-client wake-on-failure path (spec add-door-client-wake-path):
  - target derivation: container_url host, or wake_hint override normalized
    team:role -> team-role
  - wake decision: connection-level failure / 5xx triggers wake; 4xx never
  - health wait: GET /health on the delivery URL origin, up to wake timeout
  - wake publish: durable publish_event + office:inbox:<target> pub/sub
  - orchestration: wake then re-deliver; non-zero (CrewSendError) on wake or
    re-delivery failure; no silent drop
"""
from __future__ import annotations

import importlib.util
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CREW = ROOT / "crew"

# crew/crew-send.py carries a hyphen, so it is not importable by module name;
# load it explicitly so the seams below can be exercised deterministically.
_spec = importlib.util.spec_from_file_location(
    "crew_send", CREW / "crew-send.py")
crew_send = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(crew_send)  # type: ignore[union-attr]
cs = crew_send

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


class FakeBus:
    """Records wake envelopes; mimics publish_event + inbox publish."""

    def __init__(self) -> None:
        self.stream_published: list[dict] = []
        self.inbox_published: list[tuple[str, dict]] = []
        self.n_inbox_publishes = 0

    def pipeline_cmds(self, *commands: tuple) -> list:
        # publish_event -> (XADD office:events ..., PUBLISH office:events:topic ...)
        for c in commands:
            if c and c[0] == "PUBLISH":
                import json as _json
                self.stream_published.append(_json.loads(c[2]))
        return [1, 0]

    def publish(self, channel: str, payload_json: str) -> int:
        import json as _json
        self.inbox_published.append((channel, _json.loads(payload_json)))
        self.n_inbox_publishes += 1
        return 1


def test_derive_wake_target() -> None:
    check("target: instance container_url host",
          cs.derive_wake_target({"container_url":
                                 "http://dev-1-developer:8644/webhooks/inbox"}),
          "dev-1-developer")
    check("target: office container_url host",
          cs.derive_wake_target({"container_url":
                                 "http://architect:8644/webhooks/inbox"}),
          "architect")
    check("target: wake_hint overrides (team:role -> team-role)",
          cs.derive_wake_target({"container_url":
                                 "http://dev-1-developer:8644/webhooks/inbox",
                                 "wake_hint": "dev-1:developer"}),
          "dev-1-developer")
    check("target: wake_hint hyphenated passthrough",
          cs.derive_wake_target({"wake_hint": "lab-1-evaluation"}),
          "lab-1-evaluation")
    check("target: no container_url / wake_hint -> empty (caller fails)",
          cs.derive_wake_target({"secret": "x"}), "")


def test_wake_decision() -> None:
    check_true("no 4xx wake: 401", not cs.should_wake(401))
    check_true("no 4xx wake: 404", not cs.should_wake(404))
    check_true("no wake on 2xx: 202", not cs.should_wake(202))
    check_true("wake on 5xx: 500", cs.should_wake(500))
    check_true("wake on 5xx: 503", cs.should_wake(503))
    check_true("wake on connection-level (status None)",
               cs.should_wake(None))


def test_health_url() -> None:
    check("health: container door origin",
          cs.health_url_of("http://dev-1-developer:8644/webhooks/inbox"),
          "http://dev-1-developer:8644/health")
    check("health: host door origin",
          cs.health_url_of("http://127.0.0.1:8751/webhooks/inbox"),
          "http://127.0.0.1:8751/health")


def test_wait_healthy() -> None:
    seen: list[str] = []
    cs.health_ok = lambda url: (seen.append(url), url.endswith("/health"))[1]
    check_true("wait_healthy: answers -> True",
               cs.wait_healthy("http://dev-1-developer:8644/health",
                               timeout_s=30, interval_s=0.0))
    check_true("wait_healthy: probed the /health URL",
               bool(seen) and seen[0] == "http://dev-1-developer:8644/health")

    cs.health_ok = lambda url: False
    check_true("wait_healthy: never healthy -> False",
               not cs.wait_healthy("http://x:8644/health",
                                   timeout_s=0.1, interval_s=0.02))


def test_publish_wake() -> None:
    bus = FakeBus()
    n = cs.publish_wake("dev-1-developer", "door down", bus=bus)
    check_true("publish_wake: durable + inbox (2 publishes)", n == 2)
    check_true("publish_wake: stream got agent.wake envelope",
               len(bus.stream_published) == 1)
    if bus.stream_published:
        env = bus.stream_published[0]
        check("publish_wake: envelope action", env.get("action"), "agent.wake")
        check("publish_wake: envelope target", env.get("target"),
              "dev-1-developer")
    check_true("publish_wake: inbox channel office:inbox:<target>",
               len(bus.inbox_published) == 1
               and bus.inbox_published[0][0] == "office:inbox:dev-1-developer")


def _fake_env(door_down_then_up: bool = True):
    """Monkeypatch crew_send seams for orchestration tests."""
    calls = {"deliver": 0, "wake": [], "healthy_calls": 0}
    registry = {
        "developer": {
            "container_url": "http://dev-1-developer:8644/webhooks/inbox",
            "secret": "s3cret",
        }
    }
    cs.load_registry = lambda path: registry
    cs.deliver = lambda url, secret, message, timeout=30.0: _deliver(
        calls, url, door_down_then_up)
    cs.publish_wake = lambda target, reason, bus=None: calls["wake"].append(target)
    cs.wait_healthy = lambda url, timeout_s=90.0, interval_s=5.0: _healthy(
        calls, url)
    return calls


def _deliver(calls: dict, url: str, door_down_then_up: bool):
    calls["deliver"] += 1
    if calls["deliver"] == 1:
        if door_down_then_up:
            return None, "", "ConnectionRefusedError: refused"
        return 503, "unavailable", ""
    return 202, "accepted", ""


def _healthy(calls: dict, url: str) -> bool:
    calls["healthy_calls"] += 1
    return True


def test_send_wake_redeliver() -> None:
    calls = _fake_env(door_down_then_up=True)
    status, body = cs.send("developer", "hello", use_container=True)
    check("send: re-delivered after wake -> 202", (status, body), (202, "accepted"))
    check_true("send: woke once with derived target",
               calls["wake"] == ["dev-1-developer"])
    check_true("send: delivered twice (initial + re-delivery)",
               calls["deliver"] == 2)
    check_true("send: waited for health", calls["healthy_calls"] >= 1)


def test_send_5xx_wakes() -> None:
    calls = _fake_env(door_down_then_up=False)
    status, body = cs.send("developer", "hello", use_container=True)
    check("send: 5xx first -> wake -> re-deliver", (status, body), (202, "accepted"))
    check_true("send: 5xx woke once", calls["wake"] == ["dev-1-developer"])


def test_send_4xx_no_wake() -> None:
    calls = {"deliver": 0, "wake": [], "healthy_calls": 0}
    registry = {
        "developer": {
            "container_url": "http://dev-1-developer:8644/webhooks/inbox",
            "secret": "s3cret",
        }
    }
    cs.load_registry = lambda path: registry
    cs.deliver = lambda url, secret, message, timeout=30.0: (401, "bad sig", "")
    cs.publish_wake = lambda target, reason, bus=None: calls["wake"].append(target)
    try:
        cs.send("developer", "hello", use_container=True)
        check_true("send: 4xx raised CrewSendError", False)
    except cs.CrewSendError as e:
        check_true("send: 4xx raised CrewSendError", "401" in str(e))
        check_true("send: 4xx never woke", calls["wake"] == [])


def test_send_wake_timeout() -> None:
    calls = {"deliver": 0, "wake": [], "healthy_calls": 0}
    registry = {
        "developer": {
            "container_url": "http://dev-1-developer:8644/webhooks/inbox",
            "secret": "s3cret",
        }
    }
    cs.load_registry = lambda path: registry
    cs.deliver = lambda url, secret, message, timeout=30.0: (None, "", "refused")
    cs.publish_wake = lambda target, reason, bus=None: calls["wake"].append(target)
    cs.wait_healthy = lambda url, timeout_s=90.0, interval_s=5.0: False
    try:
        cs.send("developer", "hello", use_container=True)
        check_true("send: wake timeout raised CrewSendError", False)
    except cs.CrewSendError as e:
        msg = str(e)
        check_true("send: wake timeout names target", "dev-1-developer" in msg)
        check_true("send: wake timeout not silent",
                   "NOT delivered" in msg or "not delivered" in msg)


def test_send_redelivery_failure() -> None:
    calls = {"deliver": 0, "wake": [], "healthy_calls": 0}
    registry = {
        "developer": {
            "container_url": "http://dev-1-developer:8644/webhooks/inbox",
            "secret": "s3cret",
        }
    }
    cs.load_registry = lambda path: registry

    def deliver(url, secret, message, timeout=30.0):
        calls["deliver"] += 1
        if calls["deliver"] == 1:
            return None, "", "refused"
        return 500, "boom", ""

    cs.deliver = deliver
    cs.publish_wake = lambda target, reason, bus=None: calls["wake"].append(target)
    cs.wait_healthy = lambda url, timeout_s=90.0, interval_s=5.0: True
    try:
        cs.send("developer", "hello", use_container=True)
        check_true("send: re-delivery failure raised CrewSendError", False)
    except cs.CrewSendError as e:
        msg = str(e)
        check_true("send: re-delivery failure names target", "dev-1-developer" in msg)
        check_true("send: re-delivery failure not silent",
                   "NOT delivered" in msg or "not delivered" in msg)


def test_send_wake_hint_target() -> None:
    calls = {"deliver": 0, "wake": [], "healthy_calls": 0}
    registry = {
        "developer": {
            "container_url": "http://dev-1-developer:8644/webhooks/inbox",
            "secret": "s3cret",
            "wake_hint": "dev-1:developer",
        }
    }
    cs.load_registry = lambda path: registry
    cs.deliver = lambda url, secret, message, timeout=30.0: _deliver(
        calls, url, True)
    cs.publish_wake = lambda target, reason, bus=None: calls["wake"].append(target)
    cs.wait_healthy = lambda url, timeout_s=90.0, interval_s=5.0: True
    status, body = cs.send("developer", "hello", use_container=True)
    check_true("send: wake_hint normalized to controller id",
               calls["wake"] == ["dev-1-developer"])


def main() -> int:
    test_derive_wake_target()
    test_wake_decision()
    test_health_url()
    test_wait_healthy()
    test_publish_wake()
    test_send_wake_redeliver()
    test_send_5xx_wakes()
    test_send_4xx_no_wake()
    test_send_wake_timeout()
    test_send_redelivery_failure()
    test_send_wake_hint_target()
    print()
    if FAILURES:
        print(f"FAILURES ({len(FAILURES)}): {FAILURES}")
        return 1
    print("ALL PASS")
    return 0


if __name__ == "__main__":
    sys.exit(main())
