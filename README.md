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

Clone Office → configure how many Lab/Dev instances you want → spawn from template refs. See [docs/composition.md](docs/composition.md) and [docs/deploy.md](docs/deploy.md).

---

## Key architectural decisions (v1)

| Decision | Choice |
|----------|--------|
| Multi-repo | Office shell + separate **team templates** (`dev-crew`, `lab-crew`) |
| Composition | Operator chooses N× Dev and M× Lab instances from pinned template refs |
| Team isolation | Each instance is an isolated group of agents (own containers) |
| Private environments | Each Dev instance owns its own **dev-cluster** |
| Shared environments | One **pre-prod** cluster at Office level (global promotion lock) |
| Message bus | **Single Redis bus** at Office level (intra-team + inter-team) |
| Agent containers | **Team agents:** idle stop + wake; **Office agents:** always-on in v1 |
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

### Staff Engineer
Right hand of the Architect. Implements and reviews foundation-level changes.

### Scrum Master
Primary convenient entry point. Portfolio transparency and sequencing.

### Super DevOps (Pre-prod Owner)
Owns shared pre-prod and promotion rules.

---

## Relationship to team templates

| Repository | Purpose | Role under Office |
|------------|---------|-------------------|
| [lab-crew](https://github.com/camorazrushimoe/lab-crew) | Research → Research Package | **Template** for Lab instances |
| [dev-crew](https://github.com/camorazrushimoe/dev-crew) | Spec-first software development | **Template** for Dev instances |
| **agent-office** (this repo) | Portfolio + orchestration + shared infra | **Shell** |

---

## Documentation map

| Document | Purpose |
|----------|---------|
| [docs/mvp-scope.md](docs/mvp-scope.md) | What is done vs still code |
| [docs/deploy.md](docs/deploy.md) | How to bring Office up |
| [docs/architecture.md](docs/architecture.md) | Full architecture |
| [docs/composition.md](docs/composition.md) | Multi-repo composition |
| [docs/team-registry.md](docs/team-registry.md) | Registry schema |
| [docs/preprod.md](docs/preprod.md) | Promotion + lock protocol |
| [docs/agent-lifecycle.md](docs/agent-lifecycle.md) | Idle stop + wake |
| [docs/onboarding-team.md](docs/onboarding-team.md) | Admit a new team |
| [docs/handoff-protocol.md](docs/handoff-protocol.md) | Office ↔ Lab ↔ Dev |
| [docs/observability.md](docs/observability.md) | CLI event log |
| [crew/OFFICE-STANDARD.md](crew/OFFICE-STANDARD.md) | Golden rules |
| [docs/roles.md](docs/roles.md) | Roles in detail |
| `bus/action-schema.json` | Bus envelope |
| `openspec/` | Capability specs |

---

## Status

**Specification for deployable Office shell is complete** (see `docs/mvp-scope.md`).  
Next work is **implementation**: `docker-compose.yml`, doors client, event log, Hermes configs — then Office-attach in team templates.

---

See also:  
[lab-crew](https://github.com/camorazrushimoe/lab-crew) · [dev-crew](https://github.com/camorazrushimoe/dev-crew)
