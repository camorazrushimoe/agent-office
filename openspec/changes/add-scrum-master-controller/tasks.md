# Tasks — add-scrum-master-controller

## 1. Spec (this PR)
- [x] proposal.md
- [x] design.md
- [ ] specs/agent-activity/spec.md — new capability spec (hooks, board,
      stop-sync, stale heartbeat)
- [ ] specs/message-bus/spec.md — delta: `task.blocked` + payload contract
- [ ] specs/observability/spec.md — delta: board as Scrum Master input
- [ ] specs/agent-roles/spec.md — delta: Scrum Master = controller /
      escalation point

## 2. Hooks (deterministic layer)
- [ ] `office/hooks/task-accepted/` + `office/hooks/task-stopped/` canonical
      templates (`HOOK.yaml` + `handler.py`)
- [ ] `task-accepted` publishes `task.started` with best-effort `task_ref`
- [ ] `task-stopped` publishes `task.finished` with best-effort `status`
- [ ] factory generation writes both hooks into every agent home
      (office agents + `instances/*/home/*`) and sets `OFFICE_AGENT_ID` /
      `OFFICE_TEAM_ID`

## 3. Board writer (single writer)
- [ ] `office/scrum/board.py` — subscribe `office:events`, maintain
      `board.json` (current state + rolling `events` window capped at 1000)
- [ ] `docker-compose.yml` — always-on `scrum-board` service
      (`restart: unless-stopped`, repo + shared data mounts)
- [ ] gitignore `registry/scrum-master/board.json`
- [ ] `crew/board.py` CLI (or `crew/office-log.py --board`)

## 4. Stop-sync convention (rich layer)
- [ ] `crew/OFFICE-STANDARD.md` — mandatory terminal event before stopping
- [ ] agent SOULs — add the sync obligation (`task.finished{done}` /
      `task.blocked{reason}`)

## 5. Scrum Master controller (LLM layer)
- [ ] `agents/scrum-master/skills/scrum-controller/` — sweep skill:
      read board → flag stale/blocked/missing-ref/no-sync → act
- [ ] cron job on scrum-master (interval; STALL_TIMEOUT knob)

## 6. Validation
- [ ] Hook fires on a real task: `task.started` then `task.finished` visible
      via `crew/office-log.py` and reflected in `board.json`
- [ ] Broken bus does not affect the agent (hook fails silently, turn proceeds)
- [ ] Stale heartbeat: start with no stop → controller pings, then
      `task.stale`
- [ ] Blocked flow: agent publishes `task.blocked{reason}` → board shows
      `blocked` → controller routes/escalates
- [ ] 1000-line cap: window trims oldest, file stays bounded
- [ ] `board.json` stays valid under concurrent activity from many agents
      (single writer invariant)
