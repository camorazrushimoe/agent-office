# Capability: message-bus

## Requirements

### Single shared bus

Agent Office SHALL provide exactly one Redis-based message bus at the Office level.

- All Office agents SHALL connect to this bus.
- All agents of every connected team (Lab and Dev) SHALL connect to this same bus.
- Teams SHALL NOT run their own private message bus for inter-agent communication.

### Purpose

The bus is the signal and notification layer. It is used for:

- High-level lifecycle and handoff events
- Status and capacity signals
- Cross-team and Office-wide observability
- Intra-team coordination (same bus, different logical channels or topics as needed)

Long-term records of decisions live in Linear, GitHub, and structured artifacts — not only on the bus.

### Event contract (minimum)

The system SHALL support at least these event categories (exact schema to be refined under `bus/`):

| Category | Examples |
|----------|----------|
| Project lifecycle | `project.created`, `project.assigned` |
| Research | `research.started`, `research.ready` |
| Implementation | `implementation.started` |
| Handoff | `handoff.requested`, `handoff.accepted`, `handoff.rejected` |
| Environment | `promotion.requested`, `promotion.completed`, `preprod.health` |
| Work signals | `task.started`, `task.finished`, `task.stale`, `project.blocked` |
| Office | `agent.online`, `agent.offline`, `override.recorded`, `audit.started` |

Every event SHOULD carry: timestamp, actor, optional project id, short human-readable summary, optional structured payload.

### Observability

Events published on the bus SHALL be consumable by the Office CLI event log and by Scrum Master (and other agents) for status reconstruction.
