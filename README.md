# Agent Office — meta-factory of agent teams

Agent Office is a higher-level factory that orchestrates specialized agent teams (Lab Crew and Dev Crew instances).

It introduces a strategic layer of agents that manage a portfolio of projects, decide when research is needed, when implementation can start, keep the whole system transparent, and continuously improve the factories themselves.

---

## Core idea

```
You (via external Hermes agent)
        │
        ▼
┌─────────────────────────────────────────────────────────────┐
│                     Agent Office                            │
│                                                             │
│  Architect · Staff Engineer · Scrum Master · Super DevOps   │
│                                                             │
│  · single shared Redis bus                                  │
│  · shared pre-prod cluster                                  │
│  · portfolio view & routing                                 │
│  · continuous improvement of the factories                  │
└─────────────────────────────────────────────────────────────┘
        │
        ├── Lab Crew #1          (research & experimentation)
        ├── Dev Crew #1          (implementation)
        └── Dev Crew #2          (implementation)
```

- **Lab Crew** answers: *Is this idea real? What should we measure?*
- **Dev Crew** builds reliable software from validated understanding.
- **Agent Office** decides *which team*, *when*, keeps the big picture, and evolves the foundation.

---

## Key architectural decisions (v1)

| Decision | Choice |
|----------|--------|
| Team isolation | Each team is an isolated group of agents (own containers) |
| Private environments | Each team owns its own **dev-cluster** |
| Shared environments | One **pre-prod** cluster at Office level |
| Message bus | **Single Redis bus** at Office level (intra-team + inter-team) |
| Teams in v1 | 1 Lab + 2 Dev |
| Office agents | Architect, Staff Engineer, Scrum Master, Super DevOps |
| Primary human entry | Through Scrum Master (but any-to-any is allowed) |
| Observability | CLI event log (visual dashboard postponed) |
| External access | You work via an external Hermes agent that can address any internal agent |
| Foundation evolution | Architect + Staff Engineer own continuous improvement of the factories |

---

## Office agents

### Architect
Strong technical leader. Watches both the factory foundation and the projects it produces.  
Drives continuous improvement of Agent Office and the crew factories themselves.  
Consulted on architectural decisions and performs audits.

### Staff Engineer
Right hand of the Architect. Strong hands-on technical expert.  
Implements and reviews foundation-level changes, prototypes new factory capabilities, keeps the technical bar high.

### Scrum Master
Keeps work organized and transparent across all teams.  
Primary convenient entry point. Answers “what is happening with project X?”, suggests next work, surfaces blockers.

### Super DevOps (Pre-prod Owner)
Owns stability and reliability of the shared pre-prod cluster.  
Defines promotion rules from private team clusters and supports team-level DevOps agents.

---

## Relationship to existing factories

| Factory | Purpose | Status |
|---------|---------|--------|
| [lab-crew](https://github.com/camorazrushimoe/lab-crew) | Hypothesis-driven research → Research Package | Spec complete, implementation pending |
| [dev-crew](https://github.com/camorazrushimoe/dev-crew) | Spec-first software development | Working foundation |
| **agent-office** (this repo) | Portfolio + orchestration + foundation evolution | Specification in progress |

Teams remain separate repositories. Agent Office knows how to talk to them, how to route work, and how to onboard new ones.

---

## Documentation map

| Document | Purpose |
|----------|---------|
| [docs/architecture.md](docs/architecture.md) | Full architecture |
| [crew/OFFICE-STANDARD.md](crew/OFFICE-STANDARD.md) | Golden rules of the Office |
| [docs/roles.md](docs/roles.md) | Detailed Office agent roles |
| [docs/handoff-protocol.md](docs/handoff-protocol.md) | How work moves between Office ↔ Lab ↔ Dev |
| [docs/observability.md](docs/observability.md) | CLI event log contract |
| [docs/onboarding-team.md](docs/onboarding-team.md) | How to create / connect a new team |
| `openspec/` | Capability specs (to be filled) |

---

## Status

v0.2 — four Office roles, onboarding process, and foundation-evolution responsibility added.  
Next: OpenSpec capability specs, SOUL drafts, message schemas, minimal runnable skeleton.

---

See also:  
[lab-crew](https://github.com/camorazrushimoe/lab-crew) · [dev-crew](https://github.com/camorazrushimoe/dev-crew)
