#!/usr/bin/env python3
"""Deterministic validation for office/lifecycle/factory_control.py.

Run:  python3 office/lifecycle/validate_factory_control.py
Exit: 0 on success, 1 on any failed check.

Covers the two lifecycle fixes folded into PR #26:
  - 2a: wake target normalization (colon-form 'team:role' -> registry id
    'team-role') and the agent.wake_ignored observability contract
  - 2b: idle reaper anchored to container start time (effective_idle), so a
    freshly started agent with stale pre-wake log lines is not reaped
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


# ---- 3: durable re-scan of office:events for agent.wake -------------------

class FakeBus:
    """Records XREAD/get/set; returns queued XREAD results (then empty)."""

    def __init__(self, xread_results=None, hwm: str = ""):
        self.xread_results = list(xread_results or [])
        self.hwm = hwm
        self.sets: dict[str, str] = {}
        self.cmds: list[tuple] = []

    def get_key(self, key: str) -> str | None:
        return self.hwm or None

    def set_key(self, key: str, value: str) -> None:
        self.sets[key] = value

    def cmd(self, *args):
        self.cmds.append(args)
        if args and args[0] == "XREAD":
            return self.xread_results.pop(0) if self.xread_results else []
        return None


def _xread_row(entry_id: str, action: str, target: str) -> list:
    fields = ["action", action, "target", target]
    return [entry_id, fields]


def _registry_with_dev() -> list[dict]:
    return [{
        "id": "dev-1-developer",
        "container": "dev-1-developer",
        "log_path": "instances/dev-1/home/developer",
    }]


def test_parse_stream_entries() -> None:
    raw = [
        ["office:events", [
            _xread_row("1-0", "agent.wake", "dev-1-developer"),
            _xread_row("2-0", "agent.started", "dev-1-developer"),
        ]]
    ]
    got = fc.parse_stream_entries(raw)
    check("parse_stream_entries count", len(got), 2)
    check("parse_stream_entries entry id", got[0][0], "1-0")
    check("parse_stream_entries fields action", got[0][1]["action"],
          "agent.wake")
    check("parse_stream_entries fields target", got[0][1]["target"],
          "dev-1-developer")
    check("parse_stream_entries empty", fc.parse_stream_entries([]), [])
    check("parse_stream_entries malformed row skipped",
          fc.parse_stream_entries([["office:events", [["x"]]]]), [])


def test_rescan_wakes() -> None:
    emitted: list[tuple] = []
    started: list[str] = []
    fc.emit = lambda action, target, summary, extra=None: emitted.append(
        (action, target, summary))

    # 3a: wake envelope replayed -> target started, hwm advanced past all rows
    bus = FakeBus(xread_results=[
        [["office:events", [
            _xread_row("1-0", "agent.wake", "dev-1-developer"),
            _xread_row("2-0", "agent.started", "dev-1-developer"),
        ]]],
    ], hwm="0-0")
    fc.running_containers = lambda: set()
    fc.docker_start = lambda name: started.append(name) or (True, "door ready")
    handled = fc.rescan_wakes(bus, _registry_with_dev())
    check("rescan: handled only agent.wake envelopes", handled, 1)
    check("rescan: started the woken target", started, ["dev-1-developer"])
    check("rescan: emitted agent.started",
          any(a == "agent.started" and t == "dev-1-developer"
              for a, t, _ in emitted), True)
    check("rescan: hwm persisted past last row",
          bus.sets.get(fc.WAKE_HWM_KEY), "2-0")

    # 3b: idempotent — already-running target is a no-op, hwm still advances
    bus = FakeBus(xread_results=[
        [["office:events", [
            _xread_row("3-0", "agent.wake", "dev-1-developer"),
        ]]],
    ], hwm="2-0")
    fc.running_containers = lambda: {"dev-1-developer"}
    fc.docker_start = lambda name: started.append(name) or (True, "door ready")
    handled = fc.rescan_wakes(bus, _registry_with_dev())
    check("rescan: idempotent no-op count", handled, 1)
    check("rescan: running target NOT restarted", started, ["dev-1-developer"])
    check("rescan: hwm advanced on no-op",
          bus.sets.get(fc.WAKE_HWM_KEY), "3-0")

    # 3c: unknown target -> agent.wake_ignored emitted, no start
    emitted.clear()
    bus = FakeBus(xread_results=[
        [["office:events", [
            _xread_row("4-0", "agent.wake", "dev-1-develop"),  # wrong form
        ]]],
    ], hwm="3-0")
    fc.running_containers = lambda: set()
    fc.docker_start = lambda name: started.append(name) or (True, "door ready")
    handled = fc.rescan_wakes(bus, _registry_with_dev())
    check("rescan: unknown target still handled (ignored)", handled, 1)
    check("rescan: unknown target not started",
          started, ["dev-1-developer"])
    check("rescan: agent.wake_ignored emitted",
          any(a == "agent.wake_ignored" for a, _, _ in emitted), True)

    # 3d: XREAD resumes after the persisted hwm
    bus = FakeBus(xread_results=[
        [["office:events", [
            _xread_row("9-0", "agent.wake", "dev-1-developer"),
        ]]],
    ], hwm="7-0")
    fc.running_containers = lambda: {"dev-1-developer"}
    fc.docker_start = lambda name: started.append(name) or (True, "door ready")
    fc.rescan_wakes(bus, _registry_with_dev())
    xreads = [c for c in bus.cmds if c[0] == "XREAD"]
    check_true("rescan: XREAD uses persisted hwm as lower bound",
               bool(xreads) and xreads[0][-1] == "7-0")

    # 3e: bus down -> no crash, no hwm move (retried next scan)
    class DownBus(FakeBus):
        def cmd(self, *args):
            self.cmds.append(args)
            raise RuntimeError("connection closed")

    down = DownBus(hwm="9-0")
    handled = fc.rescan_wakes(down, _registry_with_dev())
    check("rescan: XREAD failure returns 0 handled", handled, 0)
    check("rescan: XREAD failure leaves hwm unchanged",
          down.sets.get(fc.WAKE_HWM_KEY), None)


def check_true(name: str, cond: bool) -> None:
    print(f"{'PASS' if cond else 'FAIL'}  {name}")
    if not cond:
        FAILURES.append(name)


def main() -> int:
    test_normalize_target()
    test_effective_idle()
    test_seconds_idle()
    test_parse_stream_entries()
    test_rescan_wakes()
    print()
    if FAILURES:
        print(f"FAILURES ({len(FAILURES)}): {FAILURES}")
        return 1
    print("ALL PASS")
    return 0


if __name__ == "__main__":
    sys.exit(main())
