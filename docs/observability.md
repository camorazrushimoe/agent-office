# Observability (v1)

Visual dashboard is **postponed**.

What is mandatory from day one: a **CLI-accessible event log** that covers the whole Agent Office and all connected teams.

## Goals

- Any human or agent can answer “what is happening right now?” and “what happened with project X?”
- Scrum Master can rely on a structured stream instead of only ad-hoc inspection
- The log is the primary transparency mechanism until a richer UI appears

## Source of truth

The single shared Redis bus is the live signal layer.

A durable (or at least queryable) event log is derived from it. Exact storage (Redis streams, append-only file, lightweight DB, etc.) is an implementation detail; the contract below is what matters.

## Minimum event categories

| Category | Examples |
|----------|----------|
| Lifecycle | project.created, project.assigned, research.started, research.ready, implementation.started |
| Handoff | handoff.requested, handoff.accepted, handoff.rejected |
| Environment | promotion.requested, promotion.completed, preprod.health |
| Work signals | task.started, task.finished, task.stale, project.blocked |
| Office | agent.online, agent.offline, audit.started, override.recorded |

Events should carry at least:

- timestamp
- actor (which agent / team)
- project identifier (when applicable)
- short human-readable summary
- optional structured payload

## CLI requirements (v1)

A simple command-line tool (or set of commands) must support:

```bash
# recent activity across the whole office
office log

# activity for one project
office log --project <id>

# activity of one team
office log --team <name>

# follow mode
office log --follow
```

Output should be readable by humans and still parseable (JSON lines or similar is fine).

Inspiration can be taken from CrewAI’s tracing / event and checkpoint CLIs, but the implementation stays native to this factory.

## What is explicitly out of scope for v1

- Fancy web UI / live dashboard
- Cost / token analytics UI
- Complex filtering UI

These can be added later on top of the same event stream.

## Relationship to existing team observability

Dev Crew already has a dashboard and completion watcher.  
In the Agent Office world those team-level tools remain useful *inside* a team, but the Office-level CLI log is the cross-team and portfolio view.
