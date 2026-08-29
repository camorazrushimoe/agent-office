# Why

Agent teams on the factory trigger each other through the shared bus and
doors, but there is **no deterministic, factory-wide record of what each agent
is doing right now**. When a handoff silently fails — an agent stops without
signalling, dies mid-task, or finishes without telling anyone — the chain of
work just stops, and nobody can see *where* or *why*.

Today the only signals are:

1. **Container lifecycle events** from `factory-control`
   (`agent.started` / `agent.stopped` = docker start/stop). These say nothing
   about whether the LLM is *working on a task* — only whether the container
   is up.
2. **Ad-hoc bus events** an agent happens to publish. These are rich but
   *optional* — nothing forces an agent to emit them, so the moment a handoff
   breaks, the signal goes dark with it.

Neither fires deterministically at the two moments that actually matter:
**when an agent accepted a task** and **when it finished (or stopped) working
on it**.

The fix is a **Scrum Master control plane**: two gateway hooks on every agent
that fire deterministically at task-start and task-stop, a single board that
projects them into one JSON view, and a Scrum Master controller that watches
that board, catches stalls, and is the escalation point for blockers.

# What Changes

- **Two Hermes gateway event hooks**, templated into every agent's
  `hermes-home/hooks/`:
  - `task-accepted` on `agent:start` → publishes `task.started`
  - `task-stopped` on `agent:end` → publishes `task.finished`
    (best-effort status classification from the response text)
- **A board writer** — always-on, single-writer service that subscribes to
  `office:events` and materialises `board.json` (current state per agent +
  rolling event window, capped). This is the Scrum Master's registry.
- **A Scrum Master controller** (cron job + skill) that reads `board.json` and:
  - detects agents stuck in `working` past a threshold → manual check
    (ping the agent, "are you alive / what's your status"),
  - surfaces agents in `blocked` awaiting response → resolves or routes,
  - flags tasks with no PR / issue / Linear reference (hygiene smell).
- **A stop-sync convention** (`crew/OFFICE-STANDARD.md` + agent SOULs): before
  stopping, every agent SHALL publish either
  `task.finished { status: done }` or `task.blocked { reason }`.
- **New event `task.blocked`** (explicit escalation: blocker vs question).
  Reuse `task.started` / `task.finished` / `task.stale` from the existing
  message-bus schema; keep `agent.started` / `agent.stopped` for container
  lifecycle (unchanged).

# Capabilities

### Modified
- `message-bus` — add `task.blocked`; document the `task.started` /
  `task.finished` payload contract (`task_ref`, `status`, `reason`).
- `observability` — `board.json` + `crew/board.py` CLI become the Scrum
  Master's first-class input (in addition to the event log).
- `agent-roles` — Scrum Master is the factory controller / escalation point.

### New
- `agent-activity` (working title) — deterministic per-agent activity
  heartbeat + board contract.

# Impact

- Affected specs: `message-bus`, `observability`, `agent-roles`; new
  `agent-activity` spec.
- Affected code:
  - NEW `agents/*/hermes-home/hooks/task-accepted/` + `task-stopped/`
    (templated at factory generation; also for `instances/*/home/*`)
  - NEW `office/scrum/board.py` (board writer; sibling of
    `office/bus/recorder.py`)
  - NEW compose service `scrum-board` (always-on, like `factory-control`)
  - NEW `registry/scrum-master/board.json` (materialised view; gitignored)
  - `crew/OFFICE-STANDARD.md` + agent SOULs — stop-sync convention
  - `agents/scrum-master/` — controller skill + cron
  - `crew/board.py` CLI (or extend `crew/office-log.py --board`)

# Non-goals (this change)

- No visual dashboard (explicitly out of scope, matches `observability`).
- No change to how work is *routed* — only visibility + stall recovery.
- Hooks are **observer-only**: they never block or alter the agent's turn.
