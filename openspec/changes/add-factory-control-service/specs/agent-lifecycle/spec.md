# agent-lifecycle — factory-control service

## MODIFIED Requirements

### Requirement: Idle stop

Agent containers in a team factory SHALL be eligible to stop after a
configurable idle period (default 40 minutes) when:

- No recent activity has been recorded for that agent, and
- The agent does not hold an active busy/task lock.

Stopping SHALL be performed by the **factory-control service** (see below),
not by the agent process itself.

**Runtime home.** The lifecycle supervisor SHALL run inside the always-on
`factory-control` container of the Office compose project. It SHALL start
with the factory (`restart: unless-stopped`) and SHALL be the ONLY component
permitted to start or stop registered agent containers. Enforcement:
- The registry is a mounted file (`office/registry/factory-agents.json`),
  exhaustive-by-construction: it lists exactly the agent containers the
  service may manage. Anything not listed is untouchable — bus/Redis,
  pre-prod, and all other containers are excluded by construction rather
  than by deny-list.
- Agent containers themselves SHALL have no docker socket and no docker
  access; only factory-control mounts `/var/run/docker.sock`.

**Activity signal.** "The agent is working" SHALL mean: the agent's Hermes
log contains task-work lines (`conversation_loop`, `tool_executor`,
inbound message, response ready) newer than the idle timeout.
- Registry entries map each agent to its log path
  (`agents/<role>/hermes-home` or `instances/<team>/home/<role>`); the
  service reads `<repo>/<log-path>/logs/agent.log`.
- Clock source: timestamps parsed from log lines (UTC). After log rotation,
  if the surviving log contains no task-work line at all, the reaper SHALL
  fall back to the log file's mtime as a secondary signal before deciding.
- If no activity signal can be read for an agent, the reaper SHALL NOT stop
  that container (fail-open). This replaces the previously specified
  `last_active` Redis-key contract, which was never implemented by any
  producer.

#### Scenario: idle agent is stopped

- **WHEN** an agent container holds no busy/task lock AND has no task-work
  log lines newer than IDLE_TIMEOUT
- **THEN** the factory-control service stops the container
- **AND** publishes `agent.stopped` with payload field `idle_seconds`

#### Scenario: busy agent is protected

- **WHEN** an agent holds an active busy/task lock
- **THEN** the reaper SHALL NOT stop that container regardless of idle time

#### Scenario: unknown-activity agents are safe

- **WHEN** an agent's log cannot be read or contains no recognizable signal
- **THEN** the service SHALL NOT stop that container

### Requirement: Wake on demand

Any attempt to deliver a message to an agent door SHALL ensure the target
agent is running and healthy before delivery.

The factory-control service SHALL subscribe to `office:inbox:*` and handle
`agent.wake` envelopes by starting the target registered container. Wake
handling SHALL be idempotent: waking an already-running agent is a no-op and
MUST NOT restart it. Health MUST be verified after start (door responds /
gateway ready) before treating the agent as ready for messages.

**Subscribe gap.** Wake envelopes published while factory-control is down or
restarting are NOT queued; they are lost. In that case the sender's wake-wait
times out and the send fails with a clear error (no silent drop). Senders MAY
publish `agent.wake` durably to make the gap self-healing on the next scan.

#### Scenario: wake starts a sleeping agent

- **WHEN** an `agent.wake` envelope names a stopped, registered agent
- **THEN** the factory-control service starts the container, waits for
  health within the wake timeout
- **AND** publishes `agent.started`; on timeout publishes `agent.wake_failed`

#### Scenario: wake of a running agent is a no-op

- **WHEN** an `agent.wake` envelope names an already-running registered agent
- **THEN** the service SHALL NOT restart it; it refreshes activity and
  returns success

#### Scenario: wake of an unknown target

- **WHEN** an `agent.wake` envelope names an unregistered container
- **THEN** the service ignores it and logs locally (no side effects)

### Requirement: Always-on vs ephemeral

- Shared Redis (Office bus), the `factory-control` service, and shared
  pre-prod infrastructure SHALL remain always-on (`restart: unless-stopped`).
- Individual agent containers MAY be stopped when idle and restarted on
  demand; their compose services use `restart: "no"` so ONLY the
  factory-control service decides their start/stop.

### Requirement: Observability

Lifecycle transitions SHALL emit bus events at least:
`agent.started`, `agent.stopped`, `agent.wake_failed`.

Events MUST go through the durable publish path (`publish_event`) so they are
visible in the Office event log replay, not only to live subscribers.

### Requirement: Safety

- Concurrent wake requests for the same agent MUST be safe (idempotent).
- An agent with an active busy/task lock MUST NOT be stopped by the idle
  policy.
- The service SHALL manage only containers in its registry; it MUST NOT
  touch shared infrastructure containers (bus/Redis, pre-prod).

### Requirement: Configuration

Idle timeout (default 40m), scan interval (default 120s), and wake wait
(default ≤ 90s) SHALL be configurable via environment variables documented in
`.env.example`.
