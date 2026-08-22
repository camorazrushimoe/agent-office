# Capability: team-onboarding

## Requirements

### New team admission

A new team (Lab or Dev style) SHALL only be considered part of Agent Office after it has been:

1. Adapted to Office rules (shared bus, no private Redis, required events, door conventions)
2. Registered in the Office team registry
3. Successfully smoke-tested for connectivity and basic handoff / event visibility

### Registry

The Office SHALL maintain a registry of known teams containing at least:

- name
- type (lab / dev / other)
- foundation reference
- door / health endpoints
- capacity or ownership notes

### Visibility

After successful onboarding, Scrum Master SHALL be able to discover and report on the new team without relying on undocumented tribal knowledge.

### Process owner

The onboarding process is described in `docs/onboarding-team.md`.  
Architect + Staff Engineer lead technical adaptation.  
Scrum Master confirms readiness for assignment.  
Super DevOps validates the promotion path for Dev teams.
