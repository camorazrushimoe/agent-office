# Agent Office — meta-factory of agent teams

Agent Office is a higher-level factory that orchestrates specialized agent teams:
**Lab** (research), **Spec** (product specs), and **Dev** (implementation).

It does not build products itself. It decides *where* work happens, keeps the
portfolio coherent, and makes the whole system observable.

**Multi-repo system:** this repository is the **shell**. Team factories live in
separate template repos and are instantiated as many times as you need:

| Template | Team type | Produces |
|----------|-----------|----------|
| [lab-crew](https://github.com/camorazrushimoe/lab-crew) | Lab | Research Packages (hypothesis → experiment → verdict) |
| [product-factory](https://github.com/camorazrushimoe/product-factory) | Spec | Product Specs ready for engineering |
| [dev-crew](https://github.com/camorazrushimoe/dev-crew) | Dev | Implemented + reviewed + deployed software |

---

## How work flows (the pipeline)

```
  Idea / GitHub repo
        │
        ▼
   ┌─────────────┐     Research       ┌──────────────────┐     Product        ┌─────────────┐
   │  Lab team   │ ──── Package ────▶ │  Spec team        │ ──── Spec ───────▶ │  Dev team   │
   │ (lab-crew)  │                    │ (product-factory) │                    │ (dev-crew)  │
   └─────────────┘                    └──────────────────┘                    └──────┬──────┘
                                                                                    │ PR → review → merge → deploy
                                                                                    ▼
                                                                           shared pre-prod (Super DevOps)
```

The **Office agents** (Architect, Staff Engineer, Scrum Master, Super DevOps)
sit above this: they route work between teams, keep the portfolio coherent, and
own the shared pre-prod gate. The **human** talks to the Office through an
external Hermes agent; Scrum Master is the recommended entry point.

**Foundation (applies to every team):**

- **GitHub** — feature branch → PR → review → merge, never push to `main`,
  never self-merge. See [`docs/github-workflow.md`](docs/github-workflow.md).
- **Linear** — the source of truth for work tracking (Projects + tickets).
  See [`docs/linear-workflow.md`](docs/linear-workflow.md).

---

## Quick start (Office shell)

```bash
git clone https://github.com/camorazrushimoe/agent-office.git
cd agent-office
cp .env.example .env                    # set CUSTOM_API_KEY=
cp crew/agents.example.json crew/agents.json

docker compose build
docker compose up -d

python3 crew/publish-event.py agent.online system "office shell up"
python3 crew/office-log.py --count 5
python3 crew/crew-send.py scrum-master "ping: hello from host"

# Foundation smoke (static → infra → bus → doors+wake). Exit 0 = foundation ok.
python3 scripts/smoke.py
# or: ./scripts/smoke.sh --level 2
```

| Service | Host port |
|---------|-----------|
| Redis bus | **6380** |
| architect | 8751 |
| staff-engineer | 8752 |
| scrum-master | 8753 |
| super-devops | 8754 |

**DevOps handoff:** read [HANDOFF-DEVOPS.md](HANDOFF-DEVOPS.md) end-to-end before deploying on hardware.

Full path: [docs/deploy.md](docs/deploy.md).

---

## Core idea

```
You (via external Hermes agent)
        │
        ▼
┌─────────────────────────────────────────────────────────────┐
│                     Agent Office                            │
│  Architect · Staff Engineer · Scrum Master · Super DevOps   │
│  · shared Redis bus · shared pre-prod network               │
└─────────────────────────────────────────────────────────────┘
        │
        ├── Lab instances   (lab-crew template)       → research
        ├── Spec instances  (product-factory template) → product specs
        └── Dev instances   (dev-crew template)       → implementation
              team agents: idle stop + wake on demand
```

---

## Key decisions (v1)

| Decision | Choice |
|----------|--------|
| Multi-repo | Office shell + team templates |
| Composition | N× Lab + K× Spec + M× Dev from pinned template refs |
| Bus | Single Redis at Office (host **6380** in default compose) |
| Pre-prod | Shared network `agent-office-preprod`, global promotion lock |
| Work tracking | Linear (Projects + tickets); GitHub for code (PR + review) |
| Office agents | Always-on in v1 |
| Team agents | Idle ~40m + wake-on-demand (implemented in team templates) |
| Human entry | Scrum Master (any-to-any allowed) |

---

## Documentation map

| Document | Purpose |
|----------|---------|
| [HANDOFF-DEVOPS.md](HANDOFF-DEVOPS.md) | **Give this to DevOps** |
| [docs/deploy.md](docs/deploy.md) | Deploy guide |
| [docs/composition.md](docs/composition.md) | Multi-repo composition |
| [docs/architecture.md](docs/architecture.md) | System architecture |
| [docs/roles.md](docs/roles.md) | Roles |
| [docs/handoff-protocol.md](docs/handoff-protocol.md) | How work moves between teams |
| [docs/linear-workflow.md](docs/linear-workflow.md) | **Linear standard** (all teams) |
| [docs/github-workflow.md](docs/github-workflow.md) | **GitHub standard** (all teams) |
| [docs/team-registry.md](docs/team-registry.md) | Registry schema |
| [docs/onboarding-team.md](docs/onboarding-team.md) | How to add a new team |
| [docs/preprod.md](docs/preprod.md) | Promotion lock |
| [docs/agent-lifecycle.md](docs/agent-lifecycle.md) | Idle / wake |
| [docs/mvp-scope.md](docs/mvp-scope.md) | Spec vs code |
| [crew/OFFICE-STANDARD.md](crew/OFFICE-STANDARD.md) | Golden rules |
| `openspec/` | Capability specs |
| [openspec/specs/foundation-smoke/spec.md](openspec/specs/foundation-smoke/spec.md) | Foundation smoke levels |
| `scripts/smoke.py` | Hierarchical foundation smoke CLI |

---

## Status

**Office shell + three team instances are running** (`dev-1`, `lab-1`, `spec-1`),
each spawned from its template with role skills, SOULs, GitHub/Linear foundation,
and doors on the shared bus. Team lifecycle (idle stop / wake) and the
deterministic Linear completion watcher are the remaining wiring.

See also: [lab-crew](https://github.com/camorazrushimoe/lab-crew) · [product-factory](https://github.com/camorazrushimoe/product-factory) · [dev-crew](https://github.com/camorazrushimoe/dev-crew)
