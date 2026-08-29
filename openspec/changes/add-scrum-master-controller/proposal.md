# Why

Agent teams on the factory trigger each other through the shared bus and
doors, but there is no deterministic, factory-wide record of when each agent
started and stopped working. When a handoff silently fails — an agent stops
without signalling, dies mid-task, or finishes without telling anyone — the
chain of work just stops, and nobody can see *where* or *why*.

Today the only deterministic signal is container lifecycle
(`agent.started` / `agent.stopped` from `factory-control`), which says whether
the container is up — not whether the LLM is actually working a task.

This change lays the foundation: two deterministic gateway hooks on every
agent that publish a `task.started` / `task.finished` heartbeat to the shared
Redis bus, with **no LLM anywhere in the hook path**.

# What Changes

- Two Hermes gateway event hooks, templated into every agent's
  `hermes-home/hooks/`:
  - `task-accepted` on `agent:start` → publishes `task.started`
  - `task-stopped`  on `agent:end`   → publishes `task.finished`
- Shared deterministic logic in `office/activity.py` (mounted at
  `/opt/office-lib/activity.py`), three jobs:
  - **who** — `agent` + `team` from env (`AGENT_ID` / `FACTORY_NAME`),
  - **what** — a cheap marker of the work:
    - `task_ref` — regex-extracted GitHub issue/PR + Linear refs,
    - `snippet` — first 200 chars (inbound message on start, response on stop),
    - `handoff` (stop only) — other known agent ids mentioned in the response.
- Events land on the durable Redis stream `office:events`, the same stream
  `crew/office-log.py` reads.

# Capabilities

### Modified
- `message-bus` — document the `task.started` / `task.finished` payload
  contract (`task_ref`, `snippet`, `handoff`).

# Impact

- Affected specs: `message-bus`.
- Affected code:
  - `office/activity.py` — shared deterministic hook logic.
  - `office/hooks/task-accepted/` + `office/hooks/task-stopped/` — the two
    hooks (`HOOK.yaml` + thin `handler.py`).
  - Factory wiring (copy hooks into agent homes; ensure `AGENT_ID` /
    `FACTORY_NAME` / `OFFICE_BUS_URL` / `OFFICE_AGENTS` env are present) —
    tracked separately in `tasks.md`.

# Non-goals (this change)

- No Scrum Master controller, stall detection, or escalation.
- No `board.json` materialised view.
- No stop-sync convention (`task.blocked` / rich `done` status).
- No visual dashboard.
- No change to how work is *routed* — hooks are **observer-only**: they never
  block or alter the agent's turn.
