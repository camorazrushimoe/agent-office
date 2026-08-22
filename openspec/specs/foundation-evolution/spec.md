# Capability: foundation-evolution

## Requirements

### Ownership

Architect SHALL own the technical roadmap and evolution of:

- Agent Office itself
- The Lab Crew and Dev Crew foundation templates
- Shared protocols (bus events, handoff, doors, observability)

Staff Engineer SHALL be the primary implementer of non-trivial foundation changes.

### Scope of foundation work

Foundation work includes (non-exhaustive):

- New capabilities of the Office or of the crew templates
- Protocol upgrades
- Structural improvements
- Tooling that improves the factories for all teams
- Audits that result in concrete foundation changes

It does **not** include ordinary product (customer project) feature work.

### Discipline

Non-trivial foundation changes SHALL:

- Have clear intent
- Be visible on the event log / bus
- Receive appropriate review (Architect + Staff Engineer as minimum for significant changes)
- Be documented so future teams inherit the improvement

### Separation

Foundation evolution work lives in the foundation repositories (agent-office, lab-crew, dev-crew).  
It MUST NOT be mixed into product project repositories.
