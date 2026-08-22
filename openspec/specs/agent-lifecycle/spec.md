# Capability: agent-lifecycle

## Requirements

### Idle stop

Agent containers in a team factory SHALL be eligible to stop after a configurable idle period (default 40 minutes) when:

- No recent activity has been recorded for that agent, and
- The agent does not hold an active busy/task lock.

Stopping SHALL be performed by a lifecycle controller, not by the agent process itself.

### Wake on demand

Any attempt to deliver a message to an agent door SHALL ensure the target agent is running and healthy before the message is accepted as delivered.

If the target is stopped (or not yet healthy):

1. A wake SHALL be requested
2. The system SHALL wait up to a configured wake timeout for the agent to become healthy
3. Only then SHALL the original message be delivered to the door
4. If wake fails within the timeout, the send SHALL fail with a clear error (no silent drop)

### Always-on vs ephemeral

- Shared Redis (Office bus), lifecycle controller(s), and shared pre-prod infrastructure SHALL remain always-on as required by their role.
- Individual agent containers MAY be stopped when idle and restarted on demand.

### Observability

Lifecycle transitions SHALL emit bus events at least:

- `agent.started`
- `agent.stopped`
- `agent.wake_failed` (when applicable)

These events MUST be visible to the Office event log / Scrum Master status paths.

### Safety

- Concurrent wake requests for the same agent MUST be safe (idempotent start).
- An agent with an active busy/task lock MUST NOT be stopped by the idle policy.
- Health MUST be verified after start before treating the agent as ready for messages.

### Configuration

Idle timeout, wake timeout, and scan interval SHALL be configurable. Defaults suitable for v1: idle 40m, wake wait ≤ 90s.
