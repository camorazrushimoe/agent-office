# Agent Office

A personal take on how to run a factory of coding and research agents — not as a chat, but as a company with durable memory.

This repository is the **office shell**: a meta-factory that routes work to specialized crews. It does not ship product code itself. It decides *where* work happens, keeps a portfolio of projects coherent, and makes the whole thing observable.

It is one person's working model, not a claim that this is the only way. Agent loops are still brittle. The design assumes they will die mid-task, forget why they started, and need to pick the work back up from something that outlives the process.

---

## Talk to a Hermes agent first. The factory is downstream.

The human does not sit inside the factory loop. You work with a **separate Hermes / Grok agent** — the one you already use to think, write, and argue with a spec.

That agent is the partner for drafting. The factory is the partner for execution.

Typical conversation with Hermes:

- “Here is a new product spec. Hand it to the Dev crew for implementation.”
- “Here is an experiment design. Hand it to the Lab crew for analysis.”
- “This research package looks ready. Send it to Spec so they can turn it into an engineering spec.”

Hermes talks to the Office through **Office MCP** (planned always-on service on host port **8760**). Scrum Master is the recommended entry point; any office or team agent is addressable. See [`docs/office-mcp.md`](docs/office-mcp.md).

Assume you already have that outer agent. You do not start by poking containers. You start by writing a specification with someone who can push back — then you hand the spec to the factory.

---

## Why GitHub and Linear are not optional

Agent loops are not stable yet. They can stop at any moment: context window, crash, idle-stop, a bad tool call. When that happens, the only context that still exists is whatever was written **outside** the model.

So the factory treats two systems as durable memory:

| System | What it stores |
|--------|----------------|
| **GitHub** | The specification and the code. Issues, the repo itself, pull requests, review. |
| **Linear** | The work. Projects, tickets, status, blockers, who is doing what. |

The hard rules of the factory:

1. **No spec in → no work.** Agents always want a specification as input. A GitHub issue, a repo with an OpenSpec, or a written spec handed over from Hermes. Vague chat is not a ticket.
2. **Spec is always broken down into Linear tickets.** That split is not optional. It is how the factory survives a crashed loop: the next agent reads Linear, not the previous conversation.
3. **Code lands only as pull requests.** Factory agents open PRs against the target repo and log the work in Linear. Never push to `main`. Never self-merge.
4. **Linear must not lie.** Ticket state has to match reality, because that is how a human (or Scrum Master) answers “where is this project?” after a loop dies.

How work actually enters the factory:

```
You + Hermes agent
        │  write / review a specification
        ▼
GitHub issue or repo with the spec
        │  “hand this to Dev / Lab / Spec”
        ▼
     Agent Office (Architect, Scrum Master, Super DevOps, …)
        │
        ├── Lab crew   → research package
        ├── Spec crew  → product spec ready for engineering
        └── Dev crew   → tickets in Linear + PRs in GitHub
```

GitHub holds *what should exist*. Linear holds *what is being done*. The bus (Redis) is the live conversation. When the conversation vanishes, GitHub and Linear are what is left.

Details: [`docs/github-workflow.md`](docs/github-workflow.md) · [`docs/linear-workflow.md`](docs/linear-workflow.md).

---

## What the office is made of

This repo is the shell. Crews live in separate template repos and can be instantiated more than once:

| Template | Crew | Produces |
|----------|------|----------|
| [lab-crew](https://github.com/camorazrushimoe/lab-crew) | Lab | Research packages (hypothesis → experiment → verdict) |
| [product-factory](https://github.com/camorazrushimoe/product-factory) | Spec | Product specs ready for engineering |
| [dev-crew](https://github.com/camorazrushimoe/dev-crew) | Dev | Implemented, reviewed, deployed software |

```
  Idea / GitHub repo / spec from Hermes
        │
        ▼
   ┌─────────────┐     Research       ┌────────────────┐     Product        ┌───────────┐
   │  Lab team   │ ──── Package ────▶ │  Spec team      │ ──── Spec ──────▶ │  Dev team  │
   │ (lab-crew)  │                    │ (product-factory)│                    │ (dev-crew) │
   └─────────────┘                    └────────────────┘                    └──────┘─────
                                                                                    │
                                                                        PR → review → merge → deploy
                                                                                    ▼
                                                                           shared pre-prod (Super DevOps)
```

Office agents sit above the crews: **Architect**, **Staff Engineer**, **Scrum Master**, **Super DevOps**. They route work, keep the portfolio coherent, and own the shared pre-prod gate. Team agents idle after ~40 minutes and wake on demand.

---

## Quick start (Office shell)

```bash
git clone https://github.com/camorazrushimoe/agent-office.git
cd agent-office
cp tokens/tokens.example.yaml tokens/tokens.yaml   # fill in tokens (docs/secrets.md)
python3 office/manage_tokens.py check
python3 office/manage_tokens.py derive-agents

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
| office-mcp (spec, not running yet) | **8760** |
| architect | 8751 |
| staff-engineer | 8752 |
| scrum-master | 8753 |
| super-devops | 8754 |

**DevOps handoff:** read [HANDOFF-DEVOPS.md](HANDOFF-DEVOPS.md) end-to-end before deploying on hardware.

Full path: [docs/deploy.md](docs/deploy.md).

---

## Key decisions (v1)

| Decision | Choice |
|----------|--------|
| Multi-repo | Office shell + team templates |
| Composition | N× Lab + K× Spec + M× Dev from pinned template refs |
| Bus | Single Redis at Office (host **6380** in default compose) |
| External facade | Office MCP (always-on with compose; host **8760**) |
| Pre-prod | Shared network `agent-office-preprod`, global promotion lock |
| Durable context | Linear (Projects + tickets); GitHub (spec + PRs + review) |
| Office agents | Always-on in v1 |
| Team agents | Idle ~40m + wake-on-demand (implemented in team templates) |
| Human entry | Separate Hermes agent → Office MCP → Scrum Master (any-to-any allowed) |

---

## Documentation map

| Document | Purpose |
|----------|---------|
| [HANDOFF-DEVOPS.md](HANDOFF-DEVOPS.md) | **Give this to DevOps** |
| [docs/deploy.md](docs/deploy.md) | Deploy guide |
| [docs/secrets.md](docs/secrets.md) | **Secrets single-source + rotation runbook** |
| [docs/office-mcp.md](docs/office-mcp.md) | **External MCP facade** (spec; runtime follow-up) |
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
| [openspec/specs/office-mcp/spec.md](openspec/specs/office-mcp/spec.md) | Office MCP capability |
| [openspec/specs/foundation-smoke/spec.md](openspec/specs/foundation-smoke/spec.md) | Foundation smoke levels |
| `scripts/smoke.py` | Hierarchical foundation smoke CLI |

---

## Status

**Office shell + three team instances are running** (`dev-1`, `lab-1`, `spec-1`), each spawned from its template with role skills, SOULs, GitHub/Linear foundation, and doors on the shared bus. Team lifecycle (idle stop / wake) and the deterministic Linear completion watcher are the remaining wiring.

Office MCP is specified (`docs/office-mcp.md`, issue #18); the compose service is not running yet.

See also: [lab-crew](https://github.com/camorazrushimoe/lab-crew) · [product-factory](https://github.com/camorazrushimoe/product-factory) · [dev-crew](https://github.com/camorazrushimoe/dev-crew) · [plugins](https://github.com/camorazrushimoe/plugins)
