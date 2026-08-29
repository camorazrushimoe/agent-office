"""Deterministic per-agent activity hooks (no LLM anywhere in this path).

Shared logic behind the two gateway event hooks:
  task-accepted  (agent:start) -> task.started
  task-stopped   (agent:end)   -> task.finished

Three jobs, all deterministic:

  1. WHO    — resolve this agent's identity from env (AGENT_ID / FACTORY_NAME,
              already set per container by docker-compose) with hostname
              fallback.
  2. WHAT   — regex-extract task references (GitHub issue / PR, Linear ticket)
              from the inbound message. No model call.
  3. PUBLISH— write a task.started / task.finished envelope to the shared
              Redis bus (office:events), the same durable stream the Office
              CLI (crew/office-log.py) and the Scrum Master read.

Failure-isolation: every step is wrapped so a down bus or a missing mount
never raises into the agent's turn (the hooks framework also swallows errors).

Mounted into every agent at /opt/office-lib/activity.py (office repo ->
/opt/office-lib). The thin handlers in office/hooks/*/handler.py import it.
"""

from __future__ import annotations

import os
import re
import socket

# ---------------------------------------------------------------------------
# 1. Identity
# ---------------------------------------------------------------------------

def identity() -> tuple[str, str]:
    """Return (agent_id, team_id) deterministically from env, then hostname."""
    agent = os.environ.get("AGENT_ID") or ""
    team = (os.environ.get("FACTORY_NAME")
            or os.environ.get("OFFICE_TEAM_ID") or "")
    host = socket.gethostname() or ""

    if not agent and "-" in host:
        # container-name fallback: "agent-office-scrum-master" -> "scrum-master",
        # "dev-1-developer" -> "developer".
        agent = host.rsplit("-", 1)[-1]
    if not agent:
        agent = host or "unknown"
    if not team:
        team = "office"
    return agent, team


# ---------------------------------------------------------------------------
# 2. Task-reference extraction (regex only, no LLM)
# ---------------------------------------------------------------------------

_GH_ISSUE_URL = re.compile(
    r"github\.com/(?P<owner>[\w.-]+)/(?P<repo>[\w.-]+)/issues/(?P<num>\d+)", re.I)
_GH_PR_URL = re.compile(
    r"github\.com/(?P<owner>[\w.-]+)/(?P<repo>[\w.-]+)/pull/(?P<num>\d+)", re.I)
_GH_REPO_REF = re.compile(r"(?P<owner>[\w.-]+)/(?P<repo>[\w.-]+)#(?P<num>\d+)")
_GH_PR_PHRASE = re.compile(r"\bPR\s*#?(?P<num>\d+)\b", re.I)
_GH_ISSUE_PHRASE = re.compile(r"\bissue\s*#?(?P<num>\d+)\b", re.I)
_GH_BARE = re.compile(r"(?<![A-Za-z0-9/])#(?P<num>\d+)\b")

_LINEAR_URL = re.compile(
    r"linear\.app/(?P<team>[\w-]+)/issue/(?P<key>[A-Z0-9]+-\d+)", re.I)
# Shorthand KEY-num is best-effort: it can false-positive on tokens like
# "GPT-4". Gate it behind LINEAR_TEAM_KEYS (comma list) when precision matters.
_LINEAR_KEY = re.compile(r"\b(?P<key>[A-Z]{1,5}-\d{1,6})\b")

# Keyword scan for a *best-effort* stop status (deterministic, replaceable).
# The authoritative done/blocked + reason is the agent's own stop-sync event
# (next iteration); this is only a cheap first signal.
_BLOCKED_WORDS = ("blocked", "блокер", "нужен токен", "need token",
                  "permission", "waiting for", "cannot proceed", "stuck")
_DONE_WORDS = ("done", "completed", "finished", "готово", "выполнено")


def _uniq(items: list[str]) -> list[str]:
    out: list[str] = []
    seen: set[str] = set()
    for it in items:
        if it and it not in seen:
            seen.add(it)
            out.append(it)
    return out


def extract_refs(text: str) -> dict:
    """Deterministically pull GitHub issue / PR and Linear refs out of text."""
    if not text:
        text = ""
    issues: list[str] = []
    prs: list[str] = []
    linear: list[str] = []

    for m in _GH_ISSUE_URL.finditer(text):
        issues.append(f"{m['owner']}/{m['repo']}#{m['num']}")
    for m in _GH_PR_URL.finditer(text):
        prs.append(f"{m['owner']}/{m['repo']}#{m['num']}")
    for m in _GH_REPO_REF.finditer(text):
        issues.append(f"{m['owner']}/{m['repo']}#{m['num']}")
    for m in _GH_ISSUE_PHRASE.finditer(text):
        issues.append(f"#{m['num']}")
    for m in _GH_PR_PHRASE.finditer(text):
        prs.append(f"#{m['num']}")

    # Bare #N — but skip numbers already claimed by an explicit
    # "PR #N" / "issue #N" phrase so they don't double-count.
    pr_phrase_nums = {m["num"] for m in _GH_PR_PHRASE.finditer(text)}
    issue_phrase_nums = {m["num"] for m in _GH_ISSUE_PHRASE.finditer(text)}
    for m in _GH_BARE.finditer(text):
        n = m["num"]
        if n not in pr_phrase_nums and n not in issue_phrase_nums:
            issues.append(f"#{n}")

    for m in _LINEAR_URL.finditer(text):
        linear.append(m["key"])
    allow = {k.strip().upper() for k in
             os.environ.get("LINEAR_TEAM_KEYS", "").split(",") if k.strip()}
    for m in _LINEAR_KEY.finditer(text):
        key = m["key"]
        if not allow or key.split("-", 1)[0].upper() in allow:
            linear.append(key)

    return {"issues": _uniq(issues), "prs": _uniq(prs), "linear": _uniq(linear)}


def _classify_stop(response: str) -> str:
    """Best-effort deterministic stop status from the response text."""
    low = (response or "").lower()
    if any(w in low for w in _BLOCKED_WORDS):
        return "blocked"
    if any(w in low for w in _DONE_WORDS):
        return "done"
    return "unknown"


# ---------------------------------------------------------------------------
# 3. Publish
# ---------------------------------------------------------------------------

def _publish(action: str, context: dict, *, status: str | None = None) -> None:
    try:
        import sys
        sys.path.insert(0, "/opt/office-lib")
        from bus.client import BusClient, make_envelope, publish_event
    except Exception:
        return  # office lib not mounted -> nothing to do, never raise

    agent, team = identity()
    message = (context.get("message") or "")[:500]
    payload: dict = {
        "summary": context.get("summary") or "",
        "session_id": context.get("session_id"),
        "message": message,
        "task_ref": extract_refs(message),
    }
    if action == "task.finished":
        payload["response"] = (context.get("response") or "")[:500]
        payload["status"] = status or "unknown"

    try:
        publish_event(BusClient(), make_envelope(
            actor=agent, action=action, target=agent,
            team=team or None, payload=payload))
    except Exception:
        return  # bus down -> swallow; the agent's turn is unaffected


def on_start(context: dict) -> None:
    """agent:start — the agent began processing a message (deterministic)."""
    agent, _team = identity()
    _publish("task.started", {**context, "summary": f"{agent} accepted work"})


def on_stop(context: dict) -> None:
    """agent:end — the agent finished a turn (deterministic)."""
    agent, _team = identity()
    status = _classify_stop(context.get("response") or "")
    _publish("task.finished",
             {**context, "summary": f"{agent} stopped ({status})"},
             status=status)
