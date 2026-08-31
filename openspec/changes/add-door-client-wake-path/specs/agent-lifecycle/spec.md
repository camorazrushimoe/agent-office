# agent-lifecycle — door client wake path

## MODIFIED Requirements

### Requirement: Wake on demand

Any attempt to deliver a message to an agent door SHALL ensure the target
agent is running and healthy before the message is accepted as delivered.

**Sender side (door client).** The canonical door client (`crew-send.py`) SHALL
be the component that guarantees this contract on the sender's behalf. When
the target door is unreachable (connection refused, timeout, or a 5xx
HTTP status), the client SHALL, in order:

1. Publish an `agent.wake` envelope for the target, durably
   (`publish_event`) and on the live inbox channel
   (`office:inbox:<target>`). The envelope target SHALL be the
   controller-recognized agent id: the host of the target entry's
   `container_url` in `crew/agents.json`. Per-instance registries are keyed by
   short role, so the `developer` entry in team `dev-1` yields
   `dev-1-developer` — exactly the id/container factory-control registers
   (`{instance}-{role}`). An entry MAY carry an explicit `wake_hint`; if
   present it SHALL be used instead, normalizing `team:role` → `team-role`
   (colon → hyphen).
2. Wait up to the configured wake timeout (default 90s) for the target door
   to answer `/health` with 200.
3. Re-deliver the original message once the target is healthy.
4. If the target never becomes healthy within the wake timeout, FAIL with a
   clear, non-zero error — the message SHALL NOT be silently dropped.
5. If re-delivery fails after a successful wake (door unreachable again or a
   non-success HTTP status), the client SHALL also FAIL with a clear,
   non-zero error — the message SHALL NOT be silently dropped.

The factory-control service SHALL subscribe to `office:inbox:*` and handle
`agent.wake` envelopes by starting the target registered container. Wake
handling SHALL be idempotent: waking an already-running agent is a no-op and
MUST NOT restart it. Health MUST be verified after start (door responds /
gateway ready) before treating the agent as ready for messages.

**Subscribe gap.** Wake envelopes published while factory-control is down or
restarting are not delivered on the live channel. To make wakes self-healing
rather than lost, factory-control SHALL also scan the durable event stream
(`office:events`) for `agent.wake` envelopes: on startup and at each scan
interval it SHALL XREAD envelopes after its last processed position (persisted
high-water mark) and handle them through the same idempotent wake path.
Re-processing is safe because waking an already-running agent is a no-op. On
first-ever boot (no persisted mark) the scan SHALL seed from the stream tail —
a concrete id, not `0` — so the full history is not replayed and
reaper-stopped agents are not resurrected; restarts resume from the persisted
mark. The door client's wake-wait still times out and the send fails loudly if
the controller cannot process the wake in time; the scan may still start the
target for subsequent deliveries.

#### Scenario: door client wakes a sleeping agent

- **WHEN** the canonical door client attempts delivery to a stopped agent door
- **THEN** it publishes `agent.wake`, waits for `/health`, re-delivers, and
  returns success once the message is accepted

#### Scenario: envelope target is the controller-recognized id

- **WHEN** the client sends to the `developer` entry in team `dev-1`'s
  `crew/agents.json` (registry key `developer`)
- **THEN** the `agent.wake` envelope target is `dev-1-developer`, derived from
  the entry's `container_url` host
- **AND** factory-control starts `dev-1-developer` (no silent
  `agent.wake_ignored`)

#### Scenario: wake fails within the timeout

- **WHEN** the target never becomes healthy within the wake timeout
- **THEN** the door client exits non-zero with a clear error naming the target
- **AND** the message is not silently dropped

#### Scenario: re-delivery fails after a successful wake

- **WHEN** the target becomes healthy but the re-delivery POST fails
- **THEN** the door client exits non-zero with a clear error naming the target
- **AND** the message is not silently dropped

#### Scenario: wake target is unknown

- **WHEN** `agent.wake` names a container not in the controller registry
  (for example, a wrong-form id sent without the instance prefix)
- **THEN** factory-control ignores it and emits `agent.wake_ignored`
- **AND** the door client's wake-wait times out and fails non-zero
