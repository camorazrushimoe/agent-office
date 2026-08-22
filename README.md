# Agent Office — meta-factory of agent teams

Agent Office is a higher-level factory that orchestrates specialized agent teams (Lab Crew and Dev Crew instances).

It introduces a strategic layer of agents that manage a portfolio of projects, decide when research is needed, when implementation can start, keep the whole system transparent, and continuously improve the factories themselves.

**Multi-repo system:** this repository is the shell. Team factories live in separate template repos (`dev-crew`, `lab-crew`) and are instantiated as many times as you need.

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
        ├── Lab Crew #1          (from lab-crew template)
        ├── Dev Crew #1          (from dev-crew template)
        └── Dev Crew #2          (from dev-crew template)
              agents sleep when idle · wake on demand
```

- **Lab Crew** answers: *Is this idea real? What should we measure?*
- **Dev Crew** builds reliable software from validated understanding.
- **Agent Office** decides *which team*, *when*, keeps the big picture, and evolves the foundation.

Clone Office → configure how many Lab/Dev instances you want → spawn from template refs. See [docs/composition.md](docs/composition.md).

---

## Key architectural decisions (v1)

| Decision | Choice |
|----------|--------|
| Multi-repo | Office shell + separate **team templates** (`dev-crew`, `lab-crew`) |
| Composition | Operator chooses N× Dev and M× Lab instances from pinned template refs |
| Team isolation | Each instance is an isolated group of agents (own containers) |
| Private environments | Each Dev instance owns its own **dev-cluster** |
| Shared environments | One **pre-prod** cluster at Office level |
| Message bus | **Single Redis bus** at Office level (intra-team + inter-team) |
| Agent containers | **Idle stop (~40m) + wake-on-demand** via lifecycle controller |
| Teams in reference v1 | 1 Lab + 2 Dev (other shapes allowed) |
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

## Relationship to team templates

| Repository | Purpose | Role under Office |
|------------|---------|-------------------|
| [lab-crew](https://github.com/camorazrushimoe/lab-crew) | Hypothesis-driven research → Research Package | **Template** for Lab instances |
| [dev-crew](https://github.com/camorazrushimoe/dev-crew) | Spec-first software development | **Template** for Dev instances |
| **agent-office** (this repo) | Portfolio + orchestration + shared infra | **Shell** |

Team craft evolves in team repos. Shell, bus protocol, pre-prod, and composition evolve here.

---

## Documentation map

| Document | Purpose |
|----------|---------|
| [docs/architecture.md](docs/architecture.md) | Full architecture |
| [docs/composition.md](docs/composition.md) | Multi-repo composition and deploy shape |
| [crew/OFFICE-STANDARD.md](crew/OFFICE-STANDARD.md) | Golden rules of the Office |
| [docs/roles.md](docs/roles.md) | Detailed Office agent roles |
| [docs/handoff-protocol.md](docs/handoff-protocol.md) | How work moves between Office ↔ Lab ↔ Dev |
| [docs/observability.md](docs/observability.md) | CLI event log contract |
| [docs/onboarding-team.md](docs/onboarding-team.md) | How to create / connect a new team |
| [docs/agent-lifecycle.md](docs/agent-lifecycle.md) | Idle stop + wake-on-demand for agent containers |
| [docs/migration-teams-to-office-bus.md](docs/migration-teams-to-office-bus.md) | Connect lab/dev crews to Office bus + lifecycle |
| `bus/action-schema.json` | Shared bus envelope |
| `openspec/` | Capability specs |

---

## Status

v0.4 — multi-repo **composition** model documented; team templates remain separate and instantiable.  
Next: minimal runnable skeleton (Office agents + shared Redis + lifecycle + CLI log).

---

See also:  
[lab-crew](https://github.com/camorazrushimoe/lab-crew) · [dev-crew](https://github.com/camorazrushimoe/dev-crew)
