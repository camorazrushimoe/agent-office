# product-factory — Office-attach implementation (spec-1 reference instance)

Implements the template contract in the product-factory repo's
`docs/office-template.md` so a spec team instance runs attached to the
Agent Office shared bus.

## Instance layer (not the template)

```
instances/spec-1/
  docker-compose.yml     # agents restart:"no", Office bus network
  .env                   # OFFICE_BUS_URL, TEAM_NAME, DOOR_SECRET_*
  crew/agents.json       # door registry with per-agent secrets
```

## Contract mapping

| Template contract item | Implementation |
|---|---|
| External Office Redis | `OFFICE_BUS_URL=redis://shared-memory:6379` on the `agent-office-crew` external network; no local Redis service |
| Wake-aware send | canonical `crew-send.py` auto-wakes on door-down: publishes `agent.wake` (target = `container_url` host or `wake_hint`), waits `/health`, re-delivers; non-zero on wake/re-delivery failure; no wake on 4xx |
| Lifecycle controller | Office's always-on `factory-control` service (office/lifecycle/factory_control.py) |
| Agents controller-managed | `restart: "no"` on all agent services |
| Team-qualified actors | envelopes use actor `spec-1/<role>` when `TEAM_NAME` is set |
| Doors | HMAC X-Hub-Signature-256, port 8644 in-container, host-mapped below |

## Env vars (Office attach)

| Var | Meaning |
|-----|---------|
| `OFFICE_BUS_URL` | Office shared Redis (required for bus events) |
| `TEAM_NAME` | Instance name (`spec-1`) — qualifies actors and container names |
| `DOOR_SECRET_*` | Per-agent door secrets |
| `OPENROUTER_API_KEY` | LLM key for all agents |

## Networks

- `agent-office-crew` (external) — bus access + lifecycle control plane
- (no private dev-cluster: spec team artifacts are documents/workspace, not running systems)

## Doors

| Role | Host door | Container |
|---|---|---|
| technical-product-manager | 127.0.0.1:8681 | dev: spec-1-technical-product-manager |
| product-researcher | 127.0.0.1:8682 | dev: spec-1-product-researcher |
| system-domain-analyst | 127.0.0.1:8683 | dev: spec-1-system-domain-analyst |
| adversarial-reviewer | 127.0.0.1:8684 | dev: spec-1-adversarial-reviewer |
