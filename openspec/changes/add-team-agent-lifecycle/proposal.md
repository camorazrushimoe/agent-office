# Change: team-agent lifecycle controller (idle stop + wake-on-demand)

## Why

Upstream `docs/mvp-scope.md` closed the v1 decision: **Office agents are
always-on** (only 4 agents, cheap). But the same doc lists the lifecycle
controller for **team agents** as still-to-implement, and
`openspec/specs/agent-lifecycle/spec.md` mandates idle stop + wake-on-demand
for *team factory* agent containers (40m default, wake is part of send,
busy-lock safety).

Team instances are where the economics bite: N dev-crews × 4–6 agents each,
mostly idle. Always-on teams defeat the purpose of the lifecycle spec.

## What Changes

- Add `office/lifecycle/docker_controller.py`: always-on controller for
  **team-instance** agent containers, scoped to a compose project label so
  it never touches Office shell containers or other projects.
- Bus contract per existing specs: consumes `agent.wake` on
  `office:inbox:{agent}`, publishes `agent.started` / `agent.stopped` /
  `agent.wake_failed` into the shared `office:events` stream (upstream's
  durable log) plus the live pub/sub topic.
- State keys on the Office bus: `office:state:{agent}`,
  `office:busy:{agent}` (renewable TTL lock),
  `office:last_active:{agent}` — any Office/team agent can read them.
- Config via env: `IDLE_TIMEOUT=40m`, `WAKE_TIMEOUT_S=90`,
  `STOP_CHECK_INTERVAL=120`, `COMPOSE_PROJECT=<team project>`.
- Office shell services stay always-on (`restart: unless-stopped`) — no
  change to upstream's phase-A decision.

## Impact

- Affected specs: `agent-lifecycle` (implemented for teams; office-shell
  exemption documented), `message-bus` (adds state-key conventions)
- Affected code: new controller module; no changes to upstream compose/doors/
  crew-send; deployable alongside any team instance compose.
