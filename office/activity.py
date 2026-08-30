"""Deterministic per-agent activity hooks (no LLM anywhere in this path).

Two gateway event hooks, copied into every agent's hermes-home/hooks/ (factory
wiring):

  task-accepted  (agent:start) -> task.started
  task-stopped   (agent:end)   -> task.finished

Each hook does three jobs, all deterministic:

  1. WHO      — resolve (agent_id, team_id) from env: AGENT_ID + TEAM_NAME
                (falling back to FACTORY_NAME for office agents, which carry
                no TEAM_NAME), set per container by docker-compose; hostname
                fallback.
  2. WHAT     — a cheap marker of "what the agent is working on":
                  * task_ref — regex-extracted GitHub issue/PR + Linear refs
                  * snippet  — first N chars of the inbound message
                and, on stop only:
                  * handoff  — other known agent ids mentioned in the response
  3. PUBLISH  — write a task.started / task.finished envelope to the shared
                Redis stream office:events (the same durable stream
                crew/office-log.py reads).

No model call anywhere. Failure-isolation: every step is wrapped so a down
bus or a missing mount never raises into the agent's turn (the hooks
framework also swallows errors).

Mounted into every agent at /opt/office-lib/activity.py (office repo ->
/opt/office-lib). The thin handlers in office/hooks/*/handler.py import it.
"""

from __future__ import annotations

import os
import re
import socket

# Marker size: keep it short — "what is it doing", not the whole prompt.
SNIPPET_LEN = 200

# ---------------------------------------------------------------------------
# 1. Identity
# ---------------------------------------------------------------------------

def identity() -> tuple[str, str]:
    """Return (agent_id, team_id) deterministically from env, then hostname.

    agent = AGENT_ID (bare role, set per container by docker-compose).
    team  = TEAM_NAME (the running instance, e.g. "dev-1") when present;
            office agents carry no TEAM_NAME, so they fall back to
            FACTORY_NAME ("office"). OFFICE_AGENT_ID / OFFICE_TEAM_ID are
            accepted aliases; hostname is the last-resort agent fallback.
    """
    agent = (os.environ.get("AGENT_ID")
             or os.environ.get("OFFICE_AGENT_ID")
             or socket.gethostname()
             or "unknown")
    team = (os.environ.get("TEAM_NAME")
            or os.environ.get("FACTORY_NAME")
            or os.environ.get("OFFICE_TEAM_ID")
            or "")
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


def _merge_refs(a: dict, b: dict) -> dict:
    return {
        "issues": _uniq(list(a.get("issues", [])) + list(b.get("issues", []))),
        "prs": _uniq(list(a.get("prs", [])) + list(b.get("prs", []))),
        "linear": _uniq(list(a.get("linear", [])) + list(b.get("linear", []))),
    }


# ---------------------------------------------------------------------------
# 3. Snippet + handoff (best-effort markers)
# ---------------------------------------------------------------------------

def snippet(text: str, n: int = SNIPPET_LEN) -> str:
    """First N chars of the text — the cheap 'what is it doing' marker."""
    return (text or "").strip()[:n]


def _known_agents() -> list[str]:
    """Known agent ids from OFFICE_AGENTS (comma list). Empty when unset."""
    raw = os.environ.get("OFFICE_AGENTS", "")
    return [a.strip() for a in raw.split(",") if a.strip()]


def extract_handoff(text: str, self_agent: str) -> list[str]:
    """Other known agent ids mentioned in text (best-effort, regex only).

    Matches each id from OFFICE_AGENTS as a word in the text. A
    team-qualified id "dev-1/developer" matches its bare part "developer".
    The agent itself is always excluded.
    """
    if not text:
        return []
    out: list[str] = []
    for a in _known_agents():
        bare = a.split("/", 1)[-1]
        if bare.lower() == (self_agent or "").split("/", 1)[-1].lower():
            continue
        if re.search(rf"\b{re.escape(bare)}\b", text, re.I):
            out.append(a)
    return _uniq(out)


# ---------------------------------------------------------------------------
# 4. Publish
# ---------------------------------------------------------------------------

def _publish(action: str, context: dict, *,
             use_response: bool = False) -> None:
    try:
        import sys
        sys.path.insert(0, "/opt/office-lib")
        from bus.client import BusClient, make_envelope, publish_event
    except Exception:
        return  # office lib not mounted -> nothing to do, never raise

    agent, team = identity()
    message = context.get("message") or ""
    payload: dict = {
        "summary": context.get("summary") or "",
        "session_id": context.get("session_id"),
        "snippet": snippet(message),
        "task_ref": extract_refs(message),
    }
    if use_response:
        response = context.get("response") or ""
        payload["snippet"] = snippet(response)
        payload["task_ref"] = _merge_refs(payload["task_ref"],
                                          extract_refs(response))
        payload["handoff"] = extract_handoff(response, agent)

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
    _publish("task.finished", {**context, "summary": f"{agent} stopped"},
             use_response=True)
