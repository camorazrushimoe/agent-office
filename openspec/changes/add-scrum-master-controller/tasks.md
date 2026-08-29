# Tasks — add-scrum-master-controller

> Direction update (agreed in review): hooks publish straight to the Redis
> bus; the Scrum Master reads the bus **directly** via a skill — no
> materialised `board.json` needed. The board is dropped (Redis stream is the
> durable store). Scope for this iteration: **hooks only**.

## 1. Hooks (this iteration — deterministic, no LLM)
- [x] `office/activity.py` — shared logic: identity (env) + regex ref
      extraction (GitHub issue / PR, Linear) + `task.started` /
      `task.finished` publish to the bus
- [x] `office/hooks/task-accepted/` (`HOOK.yaml` + `handler.py`) on
      `agent:start`
- [x] `office/hooks/task-stopped/` (`HOOK.yaml` + `handler.py`) on `agent:end`
- [ ] Factory generation: copy both hooks into every agent home
      (office agents + `instances/*/home/*`); ensure `AGENT_ID` /
      `FACTORY_NAME` / `OFFICE_BUS_URL` env are present (office agents
      already have them via compose)
- [ ] `crew-send.py` + door path: add a `sender` field so "от кого задача"
      is deterministically visible to the hook (currently only `{message}`)

## 2. Spec (fold in alongside implementation)
- [ ] `specs/message-bus/spec.md` — document `task.started` /
      `task.finished` payload contract (`task_ref`, `status`, `session_id`)
- [ ] `specs/observability/spec.md` — note these heartbeats are first-class
      Scrum Master input
- [ ] `specs/agent-roles/spec.md` — Scrum Master = controller / escalation
      point (deferred behaviour, spec the role now)

## 3. Scrum Master read skill (next iteration)
- [ ] `agents/scrum-master/skills/scrum-controller/` — read `office:events`
      via `crew/office-log.py --follow` (or bus client `subscribe`), build a
      live picture: which agents are `working`/`stopped`, which stopped
      without a terminal status, which tasks lack refs
- [ ] stale-heartbeat check: `task.started` with no `task.finished` within
      `STALL_TIMEOUT` → ping the agent (door) → `task.stale` + escalate

## 4. Deferred (not in scope now)
- [ ] `board.json` materialised view — dropped; Redis stream is the source
- [ ] Stop-sync convention (`task.blocked{reason}`) — LLM-driven rich layer,
      builds on top of these deterministic hooks

## 5. Validation
- [ ] Hook fires on a real task: `task.started` then `task.finished` visible
      via `crew/office-log.py`
- [ ] Ref extraction: issue URL, `owner/repo#N`, `PR #N`, `issue #N`, bare
      `#N`, Linear URL + `KEY-N` (covered by unit-style run)
- [ ] Broken bus does not affect the agent (hook fails silently, turn proceeds)
- [ ] Missing `/opt/office-lib` mount does not raise into the agent
