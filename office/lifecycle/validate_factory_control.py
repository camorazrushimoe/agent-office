#!/usr/bin/env python3
"""Deterministic validation for office/lifecycle/factory_control.py.

Run:  python3 office/lifecycle/validate_factory_control.py
Exit: 0 on success, 1 on any failed check.

Covers the lifecycle fixes folded into PR #26:
  - 2a: wake target normalization (colon-form 'team:role' -> registry id
    'team-role') and the agent.wake_ignored observability contract
  - 2b: idle reaper anchored to container start time (effective_idle), so a
    freshly started agent with stale pre-wake log lines is not reaped

And the wake-path implementation (spec: add-door-client-wake-path):
  - durable re-scan (scan_wake_events): XREAD office:events after the
    persisted high-water mark, agent.wake envelopes handled through the same
    idempotent wake path, HWM advanced and persisted, re-scan idempotent
"""
from __future__ import annotations

import os
import sys
import tempfile
from datetime import datetime, timedelta, timezone
from pathlib import Path

HERE = os.path.dirname(os.path.abspath(__file__))   # office/lifecycle
OFFICE = os.path.dirname(HERE)                      # office
if OFFICE not in sys.path:
    sys.path.insert(0, OFFICE)   # makes `bus.client` importable
if HERE not in sys.path:
    sys.path.insert(0, HERE)     # makes `factory_control` importable

import factory_control as fc  # noqa: E402

FAILURES: list[str] = []


def check(name: str, got, want) -> None:
    ok = got == want
    print(f"{'PASS' if ok else 'FAIL'}  {name}: {got!r}"
          + ("" if ok else f"  (want {want!r})"))
    if not ok:
        FAILURES.append(name)


def log_ts(dt: datetime) -> str:
    """Timestamp in the agent.log line format (millisecond precision)."""
    return dt.strftime("%Y-%m-%d %H:%M:%S,") + f"{dt.microsecond // 1000:03d}"


def test_normalize_target() -> None:
    check("2a: team:role -> team-role", fc.normalize_target("lab-1:evaluation"),
          "lab-1-evaluation")
    check("2a: dev-1:developer", fc.normalize_target("dev-1:developer"),
          "dev-1-developer")
    check("2a: already hyphenated passthrough",
          fc.normalize_target("lab-1-evaluation"), "lab-1-evaluation")
    check("2a: bare office id passthrough", fc.normalize_target("architect"),
          "architect")


def test_effective_idle() -> None:
    now = datetime.now(timezone.utc)

    # 2b regression: stale pre-wake log lines (45 min) + freshly started
    # container (30 s ago) -> effective idle is 30 s, NOT 45 min.
    idle = fc.effective_idle(45 * 60, now - timedelta(seconds=30), now)
    check("2b: fresh start not reaped on stale log", 0 <= idle <= 31, True)

    # genuine idleness: log idle (5 min) + long-started (1 h) -> 5 min wins.
    idle = fc.effective_idle(5 * 60, now - timedelta(hours=1), now)
    check("2b: genuine idle wins when started long ago", 299 <= idle <= 301, True)

    # no log signal + fresh start -> idle = time since start.
    idle = fc.effective_idle(None, now - timedelta(seconds=30), now)
    check("2b: no signal -> bounded by start time", 0 <= idle <= 31, True)

    # no start time available -> fall back to log signal untouched.
    check("2b: no start time -> log idle unchanged",
          fc.effective_idle(45 * 60, None, now), 45 * 60)


def test_seconds_idle() -> None:
    with tempfile.TemporaryDirectory() as d:
        log = Path(d) / "agent.log"
        now = datetime.now(timezone.utc)
        old = log_ts(now - timedelta(minutes=5))
        fresh = log_ts(now - timedelta(seconds=10))
        log.write_text(
            f"{old} conversation_loop: stale pre-wake line\n"
            f"{fresh} tool_executor: fresh line\n", encoding="utf-8")
        idle = fc.seconds_idle(log)
        check("seconds_idle picks newest activity line", 0 <= idle <= 30, True)

    with tempfile.TemporaryDirectory() as d:
        log = Path(d) / "agent.log"
        # no activity lines at all -> mtime fallback returns something >= 0
        log.write_text("no marks here\n", encoding="utf-8")
        idle = fc.seconds_idle(log)
        check("seconds_idle mtime fallback", idle is not None and idle >= 0, True)

    check("seconds_idle missing file -> None", fc.seconds_idle(
        Path(tempfile.gettempdir()) / "does-not-exist-agent.log"), None)


class FakeBus:
    """Deterministic stand-in for BusClient: memory key/value + canned XREAD."""

    def __init__(self, hwm: str | None = None, pages: list[list[tuple[str, dict]]] | None = None):
        self._hwm = hwm
        self._pages = pages or []
        self.sets: list[tuple[str, str]] = []

    def get_key(self, key: str) -> str | None:
        return self._hwm

    def set_key(self, key: str, value: str) -> None:
        self._hwm = value
        self.sets.append((key, value))

    def xread(self, key: str, last_id: str, count: int = 100) -> list[tuple[str, dict]]:
        # Return the next page; caller advances the HWM after each page.
        if not self._pages:
            return []
        return self._pages.pop(0)


def test_scan_wake_events() -> None:
    registry = [{"id": "dev-1-developer", "container": "dev-1-developer"}]
    woken: list[str] = []
    fc.wake = lambda target, _reg: woken.append(target)   # noqa: E731

    # Two pages: one agent.wake + one unrelated event, then a second wake.
    bus = FakeBus(hwm=None, pages=[
        [("1680000000000-0", {"action": "agent.wake", "target": "dev-1-developer"}),
         ("1680000000001-0", {"action": "agent.stopped", "target": "dev-1-developer"})],
        [("1680000000002-0", {"action": "agent.wake", "target": "lab-1-evaluation"})],
        [],
    ])
    fc.scan_wake_events(bus, registry)
    check("re-scan wakes only agent.wake targets", woken,
          ["dev-1-developer", "lab-1-evaluation"])
    check("re-scan persists HWM after last read", bus._hwm, "1680000000002-0")
    check("HWM key written to Redis state",
          bus.sets[-1], (fc.HWM_KEY, "1680000000002-0"))

    # Idempotency: a fresh controller starts from the persisted mark, so the
    # same envelopes are NOT re-processed (wake path itself is also a no-op
    # for running containers).
    bus2 = FakeBus(hwm="1680000000001-0", pages=[
        [("1680000000002-0", {"action": "agent.wake", "target": "lab-1-evaluation"})],
        [],
    ])
    woken2: list[str] = []
    fc.wake = lambda target, _reg: woken2.append(target)   # noqa: E731
    fc.scan_wake_events(bus2, registry)
    check("re-scan from persisted HWM skips already-seen entries",
          woken2, ["lab-1-evaluation"])


def main() -> int:
    test_normalize_target()
    test_effective_idle()
    test_seconds_idle()
    test_scan_wake_events()
    print()
    if FAILURES:
        print(f"FAILURES ({len(FAILURES)}): {FAILURES}")
        return 1
    print("ALL PASS")
    return 0


if __name__ == "__main__":
    sys.exit(main())
