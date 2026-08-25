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
permitted to start or stop registered agent containers. It SHALL manage only
containers listed in its agent registry (ownership allowlist); shared
infrastructure (bus/Redis, pre-prod) SHALL be excluded from idle-stop.

**Activity signal.** "The agent is working" SHALL mean: the agent's Hermes
log contains task-work lines (`conversation_loop`, `tool_executor`,
inbound message, response ready) newer than the idle timeout. If no activity
signal can be read for an agent, the reaper SHALL NOT stop that container
(fail-open). This replaces the previously specified `last_active` Redis-key
contract, which was never implemented by any producer.

#### Scenario: idle agent is stopped

- **WHEN** an agent container has no task-work log lines newer than
  IDLE_TIMEOUT
- **THEN** the factory-control service stops the container
- **AND** publishes `agent.stopped` with the idle duration

#### Scenario: unknown-activity agents are safe

- **WHEN** an agent's log cannot be read or contains no recognizable signal
- **THEN** the service SHALL NOT stop that container

### Requirement: Wake on demand

Any attempt to deliver a message to an agent door SHALL ensure the target
agent is running before delivery.

The factory-control service SHALL subscribe to `office:inbox:*` and handle
`agent.wake` envelopes by starting the target registered container. Wake
handling SHALL be idempotent (starting an already-running agent is a no-op).
Wake failures within the timeout SHALL emit `agent.wake_failed`; sends are
not silently dropped.

#### Scenario: wake starts a sleeping agent

- **WHEN** an `agent.wake` envelope names a stopped, registered agent
- **THEN** the factory-control service starts the container
- **AND** publishes `agent.started`

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
