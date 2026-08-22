# Agent Office — meta-factory of agent teams

Agent Office is a higher-level factory that orchestrates specialized agent teams (Lab Crew and Dev Crew instances).

**Multi-repo system:** this repository is the **shell**. Team factories live in separate template repos (`dev-crew`, `lab-crew`) and are instantiated as many times as you need.

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
        ├── Lab instances   (lab-crew template)
        └── Dev instances   (dev-crew template)
              team agents: idle stop + wake on demand
```

---

## Key decisions (v1)

| Decision | Choice |
|----------|--------|
| Multi-repo | Office shell + team templates |
| Composition | N× Dev + M× Lab from pinned template refs |
| Bus | Single Redis at Office (host **6380** in default compose) |
| Pre-prod | Shared network `agent-office-preprod`, global promotion lock |
| Office agents | Always-on in v1 |
| Team agents | Idle ~40m + wake-on-demand (implemented in team templates) |
| Human entry | Scrum Master (any-to-any allowed) |

---

## Documentation map

| Document | Purpose |
|----------|---------|
| [HANDOFF-DEVOPS.md](HANDOFF-DEVOPS.md) | **Give this to DevOps** |
| [docs/deploy.md](docs/deploy.md) | Deploy guide |
| [docs/mvp-scope.md](docs/mvp-scope.md) | Spec vs code |
| [docs/composition.md](docs/composition.md) | Multi-repo composition |
| [docs/team-registry.md](docs/team-registry.md) | Registry schema |
| [docs/preprod.md](docs/preprod.md) | Promotion lock |
| [docs/agent-lifecycle.md](docs/agent-lifecycle.md) | Idle / wake |
| [crew/OFFICE-STANDARD.md](crew/OFFICE-STANDARD.md) | Golden rules |
| [docs/roles.md](docs/roles.md) | Roles |
| `openspec/` | Capability specs |

---

## Status

**Office shell is runnable** (compose + doors + bus log).  
Team attach still depends on `dev-crew` / `lab-crew` Office-compatible implementation.

See also: [lab-crew](https://github.com/camorazrushimoe/lab-crew) · [dev-crew](https://github.com/camorazrushimoe/dev-crew)
