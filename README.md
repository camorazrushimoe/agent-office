# Agent Office — meta-factory of agent teams

Agent Office is a higher-level factory that orchestrates specialized agent teams (Lab Crew and Dev Crew instances).

It introduces a strategic layer of agents that manage a portfolio of projects, decide when research is needed, when implementation can start, and keep the whole system transparent and coordinated.

---

## Core idea

```
You (via external Hermes agent)
        │
        ▼
┌─────────────────────────────────────────────────────────────┐
│                     Agent Office                            │
│                                                             │
│  Architect  ·  Scrum Master  ·  Super DevOps                │
│                                                             │
│  · single shared Redis bus                                  │
│  · shared pre-prod cluster                                  │
│  · portfolio view & routing                                 │
└─────────────────────────────────────────────────────────────┘
        │
        ├── Lab Crew #1          (research & experimentation)
        ├── Dev Crew #1          (implementation)
        └── Dev Crew #2          (implementation)
```

- **Lab Crew** answers: *Is this idea real? What should we measure?*
- **Dev Crew** builds reliable software from validated understanding.
- **Agent Office** decides *which team*, *when*, and keeps the big picture.

---

## Key architectural decisions (v1)

| Decision | Choice |
|----------|--------|
| Team isolation | Each team is an isolated group of agents (own containers) |
| Private environments | Each team owns its own **dev-cluster** |
| Shared environments | One **pre-prod** cluster at Office level |
| Message bus | **Single Redis bus** at Office level (intra-team + inter-team) |
| Teams in v1 | 1 Lab + 2 Dev |
| Office agents | Architect, Scrum Master, Super DevOps |
| Primary human entry | Through Scrum Master (but any-to-any is allowed) |
| Observability | CLI event log (visual dashboard postponed) |
| External access | You work via an external Hermes agent that can address any internal agent |

---

## Office agents

### Architect
Strong technical leader. Watches both the factory itself and the projects it produces.  
Consulted on architectural decisions (sometimes even before a full specification).  
Performs audits of projects and factory configurations over time.

### Scrum Master
Keeps work organized and transparent across all teams.  
Can answer “what is happening with project X?”, suggest next pieces of work, detect missing specs, oversized tasks and blockers.  
Talks to business at epic/feature level while knowing the underlying stories.

### Super DevOps (Pre-prod Owner)
Owns stability and reliability of the shared pre-prod cluster.  
Can configure and fix it.  
Consults the DevOps agents that live inside individual Dev teams.

---

## Relationship to existing factories

| Factory | Purpose | Status |
|---------|---------|--------|
| [lab-crew](https://github.com/camorazrushimoe/lab-crew) | Hypothesis-driven research → Research Package | Spec complete, implementation pending |
| [dev-crew](https://github.com/camorazrushimoe/dev-crew) | Spec-first software development | Working foundation |
| **agent-office** (this repo) | Portfolio + orchestration of the above | Specification in progress |

Teams remain separate repositories. Agent Office knows how to talk to them and how to route work.

---

## Documentation map

| Document | Purpose |
|----------|---------|
| [docs/architecture.md](docs/architecture.md) | Full architecture |
| [crew/OFFICE-STANDARD.md](crew/OFFICE-STANDARD.md) | Golden rules of the Office |
| [docs/roles.md](docs/roles.md) | Detailed Office agent roles |
| [docs/handoff-protocol.md](docs/handoff-protocol.md) | How work moves between Office ↔ Lab ↔ Dev |
| [docs/observability.md](docs/observability.md) | CLI event log contract |
| `openspec/` | Capability specs (to be filled) |

---

## Status

v0.1 — core architecture and roles agreed.  
Next: flesh out OpenSpec, SOULs, message schemas, and the minimal runnable skeleton.

---

See also:  
[lab-crew](https://github.com/camorazrushimoe/lab-crew) · [dev-crew](https://github.com/camorazrushimoe/dev-crew)
