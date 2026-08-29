# Tasks — add-scrum-master-controller (deterministic activity hooks)

> Scope for this change: **two deterministic hooks → Redis. Nothing more.**
> No board, no controller, no stop-sync convention.

## 1. Shared logic + hooks (this change)
- [x] `office/activity.py` — shared deterministic logic: identity (env),
      regex ref extraction, `snippet`, `handoff`; publishes `task.started` /
      `task.finished` to the bus.
- [x] `office/hooks/task-accepted/` (`HOOK.yaml` + `handler.py`) on
      `agent:start` → `task.started`.
- [x] `office/hooks/task-stopped/` (`HOOK.yaml` + `handler.py`) on
      `agent:end` → `task.finished`.
- [ ] Factory wiring (tracked separately): copy both hooks into every agent
      home (office agents + `instances/*/home/*`); ensure `AGENT_ID` /
      `FACTORY_NAME` / `OFFICE_BUS_URL` / `OFFICE_AGENTS` env are present
      (office agents already have the first three via compose).

## 2. Spec
- [x] OpenSpec delta `specs/message-bus/spec.md` — document the
      `task.started` / `task.finished` payload contract (`task_ref`,
      `snippet`, `handoff`).

## 3. Validation
- [x] `office/validate_activity.py` — committed deterministic validator
      (`python3 office/validate_activity.py`) covering ref extraction, handoff
      (incl. team-qualified self-exclusion), identity, snippet, and both
      failure-isolation scenarios.
- [x] Ref extraction: issue URL, `owner/repo#N`, `PR #N`, `issue #N`, bare
      `#N`, Linear URL + `KEY-N` (bare `#N` de-dups against explicit phrases).
- [x] Handoff: known ids matched, self excluded (bare + team-qualified),
      empty when `OFFICE_AGENTS` unset.
- [x] Identity: `AGENT_ID` / `FACTORY_NAME` env honoured; hostname fallback.
- [x] End-to-end: `task.started` then `task.finished` land on the real Redis
      stream and are visible via `crew/office-log.py`.
- [x] Broken bus does not affect the agent — covered by `validate_activity.py`.
- [x] Missing `/opt/office-lib` mount does not raise — covered by
      `validate_activity.py`.

## 4. Deferred (out of scope)
- [ ] Scrum Master controller skill + stale-heartbeat check (`STALL_TIMEOUT`).
- [ ] `board.json` materialised view — Redis stream is the source of truth.
- [ ] Stop-sync convention (`task.blocked{reason}`) — LLM-driven rich layer.
- [ ] `sender` field on the door payload (the "from whom" gap).
