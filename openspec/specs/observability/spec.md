# Capability: observability

## Requirements

### CLI event log (mandatory in v1)

Agent Office SHALL provide a CLI-accessible event log that covers:

- Activity of all Office agents
- Activity of all connected teams visible on the shared bus
- Project-level and handoff events

Visual dashboard is explicitly out of scope for v1.

### Minimum CLI behaviour

A command-line interface SHALL support at least:

- Recent activity across the whole Office
- Filter by project
- Filter by team
- Follow / tail mode

Output MUST be human-readable and SHOULD be machine-parseable (e.g. JSON lines).

### Source

The shared Redis bus is the live signal layer. The event log is derived from it (exact durable storage is an implementation detail).

### Scrum Master use

Scrum Master SHALL be able to rely on this log (together with Linear / GitHub) to answer status questions without purely ad-hoc scraping.

### Team-level tools

Existing team-level observability (e.g. Dev Crew dashboard) may continue to exist inside a team. The Office CLI log is the cross-team and portfolio view.
