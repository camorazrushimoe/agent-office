# Office MCP

External agents talk to Agent Office through MCP. Internal agents keep using
the shared Redis bus and doors.

Spec: [`openspec/specs/office-mcp/spec.md`](../openspec/specs/office-mcp/spec.md).
Issue: [#18](https://github.com/camorazrushimoe/agent-office/issues/18).

This document is the operator/agent guide. Runtime code lands in a follow-up.

## Why MCP exists

Clone the shell → `docker compose up -d` → attach Hermes/Grok to Office MCP
→ the client can discover the office, talk to Scrum Master or any agent,
and onboard more teams without reading compose files.

MCP is a facade over:

- team registry
- doors + wake-aware send
- token check/derive
- foundation smoke
- a short event tail

It is not a second Redis and not a Linear/GitHub client.

## Starts with the factory

Office MCP is an always-on compose service (same class as `factory-control`).

| Service | Host port (planned) |
|---------|---------------------|
| Redis bus | 6380 |
| office-mcp | **8760** |

Until the implementation PR, this port is reserved in the README only.

## First moves for a newly attached client

1. Read `office://manifest` and `office://onboarding-guide`.
2. Call `office_status` and `check_readiness`.
3. If secrets are missing, tell the human to fill `tokens/tokens.yaml`
   ([docs/secrets.md](secrets.md)). Do not paste tokens into tool calls.
4. If no teams: `list_templates` → `plan_onboard` → `apply_onboard`.
5. Otherwise `send_message` to `scrum-master`.

## Addressing

```
scrum-master              Office Scrum Master (default entry)
architect                 Office Architect
dev-1                     lead of that team (tech-pm)
dev-1/developer           that agent, woken if idle
lab-1/research-lead
spec-1/technical-product-manager
```

`send_message(to="dev-1")` goes to the team lead, not to every container.

## Tools (v1)

| Tool | Use |
|------|-----|
| `office_status` | Is the shell up? |
| `list_teams` / `list_agents` / `describe_agent` | Who exists, idle or running |
| `send_message` | Talk. Ack + optional `wait_for` ≤ 15s |
| `list_templates` | lab / spec / dev templates |
| `plan_onboard` | Dry-run: e.g. 4× dev + 1× spec |
| `apply_onboard` | Apply a green plan |
| `check_readiness` | GitHub, Linear, inference, DB — presence only |
| `run_smoke` | Foundation smoke |
| `get_events` | Recent bus events |

## Onboarding sketch

```
plan_onboard({
  items: [
    {type: "dev", count: 4},
    {type: "spec", count: 1}
  ],
  token_policy: "inherit_office"
})
→ plan_id, names dev-2..dev-5 / spec-2, missing secrets

check_readiness({plan_id})
apply_onboard({plan_id})     # refused if not_ready
```

Token policy:

- `inherit_office` — one GitHub / Linear / model for everyone
- `per_team`
- `per_agent` — `manage_tokens.py derive-agents`

## What stays out of MCP v1

- Raw Redis commands
- docker compose / socket
- Creating Linear tickets or GitHub PRs
- "Implement this feature and return the PR" as one blocking tool call
- Accepting API keys in tool arguments

Work happens inside team cycles. MCP routes and reports.

## Implementation note

Code is expected at `office/mcp/` with a compose service `office-mcp`.
This spec PR does not add that service yet.
