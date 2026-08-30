#!/usr/bin/env python3
"""Deterministic validation for office/activity.py (no LLM, no pytest).

Run:  python3 office/validate_activity.py
Exit: 0 on success, 1 on any failed check.

Covers the payload contract the two gateway hooks must guarantee:
  - ref extraction (GitHub issue/PR URL, owner/repo#N, PR #N, issue #N,
    bare #N, Linear URL + KEY-N with allowlist gating)
  - handoff (known-id matching; self-exclusion incl. team-qualified ids)
  - identity (env -> hostname fallback)
  - snippet truncation
  - failure isolation (bus down / office-lib mount missing -> no raise)
"""
from __future__ import annotations

import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
if HERE not in sys.path:
    sys.path.insert(0, HERE)

import activity  # noqa: E402

FAILURES: list[str] = []


def check(name: str, got, want) -> None:
    ok = got == want
    print(f"{'PASS' if ok else 'FAIL'}  {name}: {got!r}"
          + ("" if ok else f"  (want {want!r})"))
    if not ok:
        FAILURES.append(name)


def _save_env() -> dict:
    return {k: os.environ.get(k) for k in
            ("AGENT_ID", "FACTORY_NAME", "TEAM_NAME", "OFFICE_AGENTS",
             "LINEAR_TEAM_KEYS", "OFFICE_BUS_URL")}


def _restore_env(saved: dict) -> None:
    for k, v in saved.items():
        if v is None:
            os.environ.pop(k, None)
        else:
            os.environ[k] = v


def test_refs() -> None:
    check("issue URL", activity.extract_refs(
        "https://github.com/camorazrushimoe/agent-office/issues/28"),
        {"issues": ["camorazrushimoe/agent-office#28"], "prs": [], "linear": []})
    check("repo#N", activity.extract_refs("camorazrushimoe/agent-office#28"),
        {"issues": ["camorazrushimoe/agent-office#28"], "prs": [], "linear": []})
    check("PR #N", activity.extract_refs("PR #42"),
        {"issues": [], "prs": ["#42"], "linear": []})
    check("issue #N", activity.extract_refs("issue #7"),
        {"issues": ["#7"], "prs": [], "linear": []})
    check("bare #N", activity.extract_refs("#99"),
        {"issues": ["#99"], "prs": [], "linear": []})
    check("PR + bare dedup", activity.extract_refs("PR #42 and #99"),
        {"issues": ["#99"], "prs": ["#42"], "linear": []})
    check("Linear URL", activity.extract_refs(
        "https://linear.app/acme/issue/DEV-123"),
        {"issues": [], "prs": [], "linear": ["DEV-123"]})
    os.environ["LINEAR_TEAM_KEYS"] = "DEV"
    check("Linear key allowlisted", activity.extract_refs("see DEV-123"),
        {"issues": [], "prs": [], "linear": ["DEV-123"]})
    check("Linear false-positive gated", activity.extract_refs("GPT-4 is great"),
        {"issues": [], "prs": [], "linear": []})
    os.environ.pop("LINEAR_TEAM_KEYS", None)


def test_handoff() -> None:
    os.environ["OFFICE_AGENTS"] = \
        "architect,staff-engineer,scrum-master,super-devops"
    check("handoff match", activity.extract_handoff(
        "handed off to staff-engineer and scrum-master", "architect"),
        ["staff-engineer", "scrum-master"])
    check("handoff excludes bare self", activity.extract_handoff(
        "architect will review this", "architect"), [])

    # B1 regression: team-qualified self must be excluded too.
    os.environ["OFFICE_AGENTS"] = "dev-1/developer,dev-1/qa"
    check("handoff excludes qualified self (B1)", activity.extract_handoff(
        "Handing off to developer", "dev-1/developer"), [])
    check("handoff still matches others (qualified)", activity.extract_handoff(
        "ask qa to verify", "dev-1/developer"), ["dev-1/qa"])

    os.environ.pop("OFFICE_AGENTS", None)
    check("handoff empty without OFFICE_AGENTS", activity.extract_handoff(
        "scrum-master did it", "architect"), [])


def test_identity() -> None:
    os.environ["AGENT_ID"] = "architect"
    os.environ["FACTORY_NAME"] = "office"
    check("identity from env (office)", activity.identity(),
          ("architect", "office"))
    # instance agents: TEAM_NAME (running instance) wins over FACTORY_NAME
    # (template) — the activity event must carry the real team, not the
    # template name.
    os.environ["AGENT_ID"] = "developer"
    os.environ["FACTORY_NAME"] = "dev-crew"
    os.environ["TEAM_NAME"] = "dev-1"
    check("identity prefers TEAM_NAME (instance)", activity.identity(),
          ("developer", "dev-1"))
    os.environ.pop("AGENT_ID", None)
    os.environ.pop("FACTORY_NAME", None)
    os.environ.pop("TEAM_NAME", None)
    # hostname fallback: returns *something* non-empty, not a lossy parse
    agent, _team = activity.identity()
    check("identity hostname fallback non-empty", bool(agent), True)


def test_snippet() -> None:
    check("snippet truncates", activity.snippet("x" * 500), "x" * 200)
    check("snippet empty-safe", activity.snippet(None), "")


def test_failure_isolation() -> None:
    # Bus down: point at a closed port; the hook must swallow and return.
    os.environ["OFFICE_BUS_URL"] = "redis://127.0.0.1:1"
    try:
        activity.on_start({"message": "x", "session_id": "s"})
        activity.on_stop({"message": "x", "response": "y", "session_id": "s"})
        check("bus down -> no raise", True, True)
    except Exception as exc:  # pragma: no cover
        check("bus down -> no raise", f"raised {exc!r}", True)

    # Mount missing: hide the office dir from sys.path so the lazy
    # `from bus.client import ...` inside _publish cannot resolve.
    saved = list(sys.path)
    try:
        sys.path[:] = [p for p in sys.path if p != HERE]
        os.environ.pop("OFFICE_BUS_URL", None)
        activity.on_start({"message": "x"})
        activity.on_stop({"message": "x", "response": "y"})
        check("mount missing -> no raise", True, True)
    except Exception as exc:  # pragma: no cover
        check("mount missing -> no raise", f"raised {exc!r}", True)
    finally:
        sys.path[:] = saved


def main() -> int:
    saved = _save_env()
    try:
        test_refs()
        test_handoff()
        test_identity()
        test_snippet()
        test_failure_isolation()
    finally:
        _restore_env(saved)

    print()
    if FAILURES:
        print(f"FAILURES ({len(FAILURES)}): {FAILURES}")
        return 1
    print("ALL PASS")
    return 0


if __name__ == "__main__":
    sys.exit(main())
