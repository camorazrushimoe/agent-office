# Agent Office — Architecture

> Living document. Refined as the system is implemented.

## Overview

Agent Office is a **meta-factory**: a higher-level orchestration layer that sits above specialized agent teams (Lab Crew and Dev Crew instances).

```text
External Hermes agent (you)
          │
          ▼
┌──────────────────────────────────────────────────────────────┐
│                        Agent Office                          │
│                                                              │
│   Architect          Scrum Master         Super DevOps       │
│                                                              │
│   · shared Redis bus (single)                                │
│   · shared pre-prod cluster                                  │
│   · portfolio & routing logic                                │
└──────────────────────────────────────────────────────────────┘
          │
          ├── Lab Crew #1
          │     └── private agents + (usually lightweight workspace)
          │
          ├── Dev Crew #1
          │     └── private agents + private dev-cluster
          │
          └── Dev Crew #2
                └── private agents + private dev-cluster
```

## Layers

### 1. Office layer (this repository)

- Three permanent agents: Architect, Scrum Master, Super DevOps
- Single shared Redis bus
- Shared pre-prod cluster
- Registry of available teams
- Portfolio of projects and their current stage

### 2. Team layer (external repositories)

- Lab Crew and Dev Crew remain separate, versioned factories
- Each running instance of a team is an independent Docker Compose project
- Teams keep their internal agent isolation (one container per agent)
- Teams **do not** run their own Redis — they connect to the Office bus

### 3. Project work

- Lives outside both the Office and the team foundations
- Code, data, Linear projects, OpenSpec of the product itself

## Environments

| Environment | Scope | Owner | Purpose |
|-------------|-------|-------|---------|
| Private dev-cluster | Per Dev team | The team’s own DevOps + developer | Sandbox for feature work, experimentation, breaking changes |
| Shared pre-prod | Office | Super DevOps | Integration point and release-candidate gate |
| (future) production | Outside | — | Not part of the factory yet |

**Promotion path (Dev teams):**

1. Develop & verify inside the team’s private dev-cluster
2. When ready → promote to shared pre-prod (coordinated by team DevOps + Super DevOps)
3. Further gates (QA, approval) happen against pre-prod

Lab teams usually do not need a full private cluster; they work primarily with temporary workspace artifacts.

## Communication

### Single Redis bus

There is **one** Redis instance at the Office level.

- All Office agents connect to it
- All team agents connect to it
- Both intra-team and inter-team messages go through this bus
- Office agents can observe activity of every team in real time

### Webhook doors

Every agent (Office + teams) still exposes a signed webhook door (`POST /webhooks/inbox`).

- External Hermes agent → any internal agent
- Any agent → any other agent
- Primary human convenience path: talk to Scrum Master first

### Message principles

- High-level events are published on the bus (`project.started`, `research.ready`, `capacity.changed`, `task.finished`, …)
- Detailed discussion stays in Linear / structured artifacts
- Redis is the signal layer, not the long-term record of decisions

## Separation of concerns

| Layer | What lives there |
|-------|------------------|
| Foundation (this repo) | Office agent identities, skills, Office rules, bus schema, pre-prod definition |
| Instance config | Secrets, tokens, door registry, real endpoints of teams (gitignored) |
| Team foundations | lab-crew / dev-crew repositories |
| Project work | Product code, product OpenSpec, Linear projects, data |

Office never mixes project code into its own foundation. Teams never mix Office concerns into their foundations.

## Team registry

Office maintains a registry of known teams:

- identity (name, type: lab / dev)
- endpoints (doors, health)
- current capacity / active projects
- how to reach their private environments (if needed)

In v1 the registry is static/config-driven. Later it can become dynamic.

## Open questions (to resolve during implementation)

- Exact ownership / locking protocol when multiple teams promote to the same pre-prod
- How much of the existing dev-crew / lab-crew docker-compose needs to change to drop their local Redis
- Minimal set of bus events that Office agents must understand
- Whether Lab teams ever need a private cluster of their own
