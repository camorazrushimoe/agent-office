# Design: Office MCP

## Facade, not a bus

```
External agent (Hermes / Grok / other MCP client)
        |
        |  MCP (tools + resources)
        v
┌─────────────────────────────────────────┐
│ office-mcp  (always-on compose service) │
└─────────────────────────────────────────┘
        |
        +-- team-registry.yaml
        +-- factory-agents.json / doors.json
        +-- wake-aware send (crew-send + factory-control)
        +-- manage_tokens.py check/derive (no secret ingress)
        +-- scripts/smoke.py
        +-- Redis only as an event tail for get_events / wait_for
```

Clients never receive Redis URLs or door HMAC secrets through MCP.

## Transport

Primary: Streamable HTTP / SSE bound on the Office `crew` network,
published to the host as **8760** (implementation PR).

Optional later: stdio wrapper `python -m office.mcp` for a host-side
client that prefers not to use HTTP. Same tool/resource contract.

## Resources vs tools

Resources carry orientation (cheap, cacheable, no side effects).
Tools mutate or query live state.

An external agent SHOULD read `office://manifest` first, then
`check_readiness` / `office_status`.

## Addressing

One string, three levels:

- Office role: `scrum-master`, `architect`, `staff-engineer`, `super-devops`
- Team: `dev-1`, `lab-1`, `spec-1` → lead role of that type
- Agent: `dev-1/developer`

Lead map:

| type | lead |
|------|------|
| dev  | tech-pm |
| lab  | research-lead |
| spec | technical-product-manager |

Team send is not fan-out.

## Send + wait

`send_message` always:

1. Resolves the address
2. Wakes the target if needed (existing lifecycle)
3. Posts to the door
4. Returns `{status: accepted, message_id, to, woke}`

If `wait_for` is set (seconds, cap 15), MCP tails the bus for a matching
event (`agent.started`, inbound ack, `task.started`, …) and attaches it.
Timeout is not a send failure — status stays `accepted` with
`wait: timed_out`.

## Onboarding

Two-phase so "4 dev teams" cannot silently half-apply.

1. `plan_onboard({items: [{type, count, ref?}]})` → plan_id + names +
   ports + missing readiness + token_policy.
2. `apply_onboard({plan_id})` only if readiness for that plan is green.

Token policy on the plan: `inherit_office` | `per_team` | `per_agent`.
Values stay in `tokens/tokens.yaml`.

## Error model

Stable `code` strings: `not_found`, `not_ready`, `plan_expired`,
`wake_failed`, `send_failed`, `invalid_address`, `secret_refused`,
`conflict`.
