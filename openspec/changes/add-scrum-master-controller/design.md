# Design — deterministic per-agent activity hooks

## 1. The core insight

Hermes **already has** the two hooks we need. Every agent's
`hermes-home/hooks/` directory exists and is empty; it is the home for
*gateway event hooks* (`HOOK.yaml` + `handler.py`). Two lifecycle events map
1:1 onto the two moments we care about:

| Hook | Hermes event | Meaning | Fires when |
|------|-------------|---------|------------|
| `task-accepted` | `agent:start` | agent got a task and went to work | the model begins processing an inbound message |
| `task-stopped`  | `agent:end`   | the model stopped working | the model finishes and returns a response |

So **no new core plumbing is needed** — this is config + a thin handler per
agent, not a runtime change.

### Handler context (what we get for free)

- `agent:start`: `platform`, `user_id`, `chat_id`, `thread_id`, `chat_type`,
  `session_id`, `message` (truncated to 500 chars).
- `agent:end`: same keys + `response` (truncated to 500 chars), `model`,
  `provider`.

## 2. Architecture

```text
each agent (gateway process)
  hooks/task-accepted  -> task.started   (agent:start)
  hooks/task-stopped   -> task.finished  (agent:end)
        |  publish_event()  (fire-and-forget)
        v
Redis bus — office:events (durable stream)
```

Hooks publish envelopes; there is no board, no controller, no materialised
view in this change. The Redis stream is the durable store, read directly by
`crew/office-log.py` (and, later, the Scrum Master).

## 3. Payload contract

Both events use the standard bus envelope (`id` / `actor` / `action` /
`target` / `timestamp` / `team`). `actor` = agent, `target` = agent (the
event is self-reported), `team` = `FACTORY_NAME`.

| field | `task.started` | `task.finished` | meaning |
|-------|:---:|:---:|---------|
| `summary`     | ✓ | ✓ | `"<agent> accepted work"` / `"<agent> stopped"` |
| `session_id`  | ✓ | ✓ | correlates a turn |
| `snippet`     | ✓ | ✓ | first 200 chars of message (start) / response (stop) — the "what is it doing" marker |
| `task_ref`    | ✓ | ✓ | `{issues[], prs[], linear[]}` regex-extracted; on stop, message+response merged |
| `handoff`     | — | ✓ | other known agent ids mentioned in the response |

The keyword-based `status` from the earlier draft is **dropped**: a regex
guess of done/blocked from free text produces false positives (e.g.
"not blocked, all done" → `blocked`), and a false `blocked` from the
deterministic layer is worse than no status. Status semantics belong to the
deferred stop-sync layer, not here.

## 4. Determinism, identity, refs, handoff

- **Identity** — `AGENT_ID` + `FACTORY_NAME` env (already set per container
  in `docker-compose.yml`), aliases `OFFICE_AGENT_ID` / `OFFICE_TEAM_ID`,
  hostname fallback. No parsing of the container name (fragile).
- **Refs** — regex only: GitHub issue/PR URLs, `owner/repo#N`, `PR #N`,
  `issue #N`, bare `#N` (de-duplicated against explicit phrases), Linear URL
  and `KEY-N` (gated by optional `LINEAR_TEAM_KEYS` allowlist).
- **Handoff** — a word-boundary regex match of each id in `OFFICE_AGENTS`
  (comma list, optional) against the response; team-qualified ids match their
  bare part; the agent itself is always excluded. Empty when `OFFICE_AGENTS`
  is unset — deterministic and precise, no guessing.

## 5. Failure isolation and honest limits

- Every step is wrapped: a down bus or a missing `/opt/office-lib` mount is
  swallowed and never raises into the agent's turn.
- Hooks fire on the **normal** start/stop path only. A container OOM-killed
  or `docker stop`ped mid-turn fires neither hook — that gap is *out of scope*
  here (it is the future stale-heartbeat check's job).
- Gateway hooks fire only in **gateway mode**; all Office + team agents are
  always-on gateway processes, so this holds. One-shot CLI runs show no event
  (documented, acceptable).
- `snippet` / `task_ref` / `handoff` are best-effort markers of a 500-char
  turn context — a *signal*, not an authoritative record.

## 6. Deferred (explicitly out of scope)

- Scrum Master controller, stale-heartbeat check, escalation.
- `board.json` materialised view / `crew/board.py`.
- Stop-sync convention (`task.finished{done}` / `task.blocked{reason}`).
- `sender` field on the door payload (the "from whom" gap).
