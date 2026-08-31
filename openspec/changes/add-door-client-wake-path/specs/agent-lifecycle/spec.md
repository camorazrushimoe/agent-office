# agent-lifecycle — door client wake path

## MODIFIED Requirements

### Requirement: Wake on demand

Any attempt to deliver a message to an agent door SHALL ensure the target
agent is running and healthy before the message is accepted as delivered.

**Sender side (door client).** The canonical door client (`crew-send.py`) SHALL
be the component that guarantees this contract on the sender's behalf. When
the target door is unreachable (connection refused, timeout, or a non-success
HTTP status), the client SHALL, in order:

1. Publish an `agent.wake` envelope for the target, durably
   (`publish_event`) and on the live inbox channel
   (`office:inbox:<target>`), naming the target in canonical registry form
   (`team-role`), normalizing the `team:role` wake-hint form when present.
2. Wait up to the configured wake timeout (default 90s) for the target door
   to answer `/health` with 200.
3. Re-deliver the original message once the target is healthy.
4. If the target never becomes healthy within the wake timeout, FAIL with a
   clear, non-zero error — the message SHALL NOT be silently dropped.

The factory-control service SHALL subscribe to `office:inbox:*` and handle
`agent.wake` envelopes by starting the target registered container. Wake
handling SHALL be idempotent: waking an already-running agent is a no-op and
MUST NOT restart it. Health MUST be verified after start (door responds /
gateway ready) before treating the agent as ready for messages.

**Subscribe gap.** Wake envelopes published while factory-control is down or
restarting are NOT queued; they are lost. The door client's wake-wait then
times out and the send fails with a clear error (no silent drop). Because the
client publishes `agent.wake` durably, a wake that raced a controller restart
is still visible on the durable stream and MAY be re-processed on the next
scan.

#### Scenario: door client wakes a sleeping agent

- **WHEN** the canonical door client attempts delivery to a stopped agent door
- **THEN** it publishes `agent.wake`, waits for `/health`, re-delivers, and
  returns success once the message is accepted

#### Scenario: wake fails within the timeout

- **WHEN** the target never becomes healthy within the wake timeout
- **THEN** the door client exits non-zero with a clear error naming the target
- **AND** the message is not silently dropped

#### Scenario: wake target is unknown

- **WHEN** `agent.wake` names an unregistered container
- **THEN** factory-control ignores it and emits `agent.wake_ignored`
- **AND** the door client's wake-wait times out and fails non-zero
