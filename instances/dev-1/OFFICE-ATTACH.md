# Dev Crew — Office-attach implementation (dev-1 reference instance)

Implements the template contract in `docs/office-template.md` so a dev-crew
instance can run attached to the Agent Office shared bus.

## What this change adds (in the dev-1 instance, not the template)

The Office spawns instances from pinned template refs. The **instance layer**
owns Office-attach glue so the upstream template stays thin:

```
instances/dev-1/
  docker-compose.yml     # agents restart:"no" + lifecycle controller
  .env                   # OFFICE_BUS_URL, TEAM_NAME, DOOR_SECRET_*
  crew/agents.json       # door registry with per-agent secrets
```

## Contract mapping

| Template contract item | Implementation |
|---|---|
| External Office Redis | `OFFICE_BUS_URL=redis://shared-memory:6379` on the `agent-office` external network; no local Redis service |
| Wake-aware send | `crew-send.py --wake` → publishes `agent.wake`, waits health, then POSTs |
| Lifecycle controller | Office's `office/lifecycle/docker_controller.py`, `COMPOSE_PROJECT=dev-1` |
| Agents controller-managed | `restart: "no"` on all four agent services |
| Team-qualified actors | envelopes use actor `dev-1/<role>` when `TEAM_NAME` is set |
| Doors | HMAC X-Hub-Signature-256, port 8644 in-container, host-mapped 8661–8664 |

## Env vars (Office attach)

| Var | Meaning |
|-----|---------|
| `OFFICE_BUS_URL` | Office shared Redis (required for bus events) |
| `TEAM_NAME` | Instance name (`dev-1`) — qualifies actors and container names |
| `DOOR_SECRET_*` | Per-agent door secrets |
| `OPENROUTER_API_KEY` | LLM key for all agents |

## Networks

- `agent-office` (external) — bus access + lifecycle control plane
- `dev-1-dev-env` / `dev-1-staging-env` — the team's private dev-cluster
  (project compose files attach via `external: true`)
