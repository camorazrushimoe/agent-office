# Delta: message-bus — deterministic activity heartbeats

## MODIFIED Requirements

### Requirement: Deterministic activity heartbeats

Every Office and team agent SHALL publish two deterministic (no-LLM) gateway
hook events to the shared bus:

- `task.started` on `agent:start` — the agent began processing an inbound
  message;
- `task.finished` on `agent:end` — the agent finished a turn.

Both events SHALL use the standard bus envelope with `actor` = agent and
`team` = `FACTORY_NAME`, resolved from env, and SHALL carry in `payload`:

| field | `task.started` | `task.finished` | meaning |
|-------|:---:|:---:|---------|
| `snippet`  | ✓ | ✓ | first 200 chars of message (start) / response (stop) — a cheap "what is it doing" marker |
| `task_ref` | ✓ | ✓ | `{issues[], prs[], linear[]}` regex-extracted from text |
| `handoff`  | — | ✓ | other known agent ids mentioned in the response (possibly empty) |

#### Scenario: hook publishes on start

- **WHEN** an agent begins processing an inbound message
- **THEN** the gateway publishes a `task.started` envelope to `office:events`
  carrying `snippet` and `task_ref`, and no `handoff`.

#### Scenario: hook publishes on finish

- **WHEN** an agent finishes a turn
- **THEN** the gateway publishes a `task.finished` envelope carrying
  `snippet` (of the response), `task_ref`, and `handoff` (possibly empty).

#### Scenario: hook failure is isolated

- **WHEN** the bus is unreachable or the office lib mount is missing
- **THEN** the hook SHALL NOT raise into the agent's turn.
