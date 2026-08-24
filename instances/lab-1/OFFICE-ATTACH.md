# lab-crew — Office-attach implementation (lab-1 reference instance)

Implements the template contract in the lab-crew repo's
`docs/office-template.md` so a lab team instance runs attached to the
Agent Office shared bus.

## Instance layer (not the template)

```
instances/lab-1/
  docker-compose.yml     # agents restart:"no", Office bus network
  .env                   # OFFICE_BUS_URL, TEAM_NAME, DOOR_SECRET_*
  crew/agents.json       # door registry with per-agent secrets
```

## Contract mapping

| Template contract item | Implementation |
|---|---|
| External Office Redis | `OFFICE_BUS_URL=redis://shared-memory:6379` on the `agent-office-crew` external network; no local Redis service |
| Wake-aware send | `crew-send.py --wake` → publishes `agent.wake`, waits health, then POSTs |
| Lifecycle controller | Office's `office/lifecycle/docker_controller.py`, `COMPOSE_PROJECT=lab-1` |
| Agents controller-managed | `restart: "no"` on all agent services |
| Team-qualified actors | envelopes use actor `lab-1/<role>` when `TEAM_NAME` is set |
| Doors | HMAC X-Hub-Signature-256, port 8644 in-container, host-mapped below |

## Env vars (Office attach)

| Var | Meaning |
|-----|---------|
| `OFFICE_BUS_URL` | Office shared Redis (required for bus events) |
| `TEAM_NAME` | Instance name (`lab-1`) — qualifies actors and container names |
| `DOOR_SECRET_*` | Per-agent door secrets |
| `OPENROUTER_API_KEY` | LLM key for all agents |

## Networks

- `agent-office-crew` (external) — bus access + lifecycle control plane
- (no private dev-cluster: lab team artifacts are documents/workspace, not running systems)

## Doors

| Role | Host door | Container |
|---|---|---|
| research-lead | 127.0.0.1:8671 | dev: lab-1-research-lead |
| research-engineer | 127.0.0.1:8672 | dev: lab-1-research-engineer |
| evaluation | 127.0.0.1:8673 | dev: lab-1-evaluation |
