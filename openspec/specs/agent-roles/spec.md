# Capability: agent-roles

## Requirements

### Office agents

The Agent Office SHALL have exactly these permanent agents in v1:

- Architect
- Staff Engineer
- Scrum Master
- Super DevOps

Each agent SHALL have:

- A clear identity (SOUL.md)
- A defined set of responsibilities (see docs/roles.md)
- A webhook door
- Connection to the shared Redis bus

### Architect

- SHALL own the technical roadmap of the factory foundation (Agent Office + crew templates).
- SHALL be the primary source of architectural advice for complex projects and for the factories themselves.
- SHALL be able to initiate and lead foundation-level changes.

### Staff Engineer

- SHALL act as the primary hands-on implementation partner of the Architect for foundation work.
- SHALL be able to write and review code that improves the factories.
- SHALL support deep technical reviews when escalated by the Architect.

### Scrum Master

- SHALL be the primary convenient entry point for the human.
- SHALL be able to answer the current status of any known project by combining tickets, bus events and other signals.
- SHALL surface blockers, missing specifications and sequencing problems.
- SHALL be able to stop work and escalate to the customer when intent cannot be established (OFFICE-STANDARD rule 11; docs/intent-alignment-gate.md).

### Super DevOps

- SHALL own the shared pre-prod cluster.
- SHALL define and enforce the promotion path from team private clusters into pre-prod.

### Interaction

- Any agent MAY address any other agent.
- The external Hermes agent used by the human SHALL have the same addressing rights as Office agents.
