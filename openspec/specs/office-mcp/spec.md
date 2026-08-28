# Capability: office-mcp

Office MCP is the external facade for Agent Office. An MCP client talks to
the factory through this capability. Internal coordination stays on the
shared Redis bus, HMAC doors, and factory-control.

## Requirements

### Always-on with the factory

Agent Office SHALL run Office MCP as an always-on service of the Office
compose project (`restart: unless-stopped`).

- MCP SHALL start on `docker compose up -d` together with Redis and
  `factory-control`.
- MCP SHALL depend on a healthy shared bus.
- Planned host port: **8760** (implementation PR).
- MCP SHALL use the same tool and resource contract regardless of transport
  (HTTP/SSE in compose; optional stdio later).

### Facade, not a second bus

MCP SHALL wrap existing sources of truth:

- `config/team-registry.yaml`
- `office/registry/factory-agents.json`
- `registry/doors.json`
- wake-aware send (`crew-send` + factory-control)
- `office/manage_tokens.py`
- `scripts/smoke.py`
- bus event tail (read-only)

MCP SHALL NOT expose raw Redis publish, door HMAC secrets, or a Docker API.
MCP SHALL NOT perform Linear or GitHub CRUD; those remain connectors and
team-agent work.

### Default entry

The recommended human/external entry point SHALL be `scrum-master`.
Any-to-any addressing remains allowed.

### Addressing

Addresses SHALL be strings of one of these forms:

| Form | Example | Resolves to |
|------|---------|-------------|
| Office role | `scrum-master` | that Office agent's door |
| Team id | `dev-1` | lead role of the team type |
| Team role | `dev-1/developer` | that instance agent |

Lead roles SHALL be:

- `dev` → `tech-pm`
- `lab` → `research-lead`
- `spec` → `technical-product-manager`

A team-level send SHALL NOT fan out to every agent in the instance.
Unknown addresses SHALL fail with `invalid_address` or `not_found`.

### Resources (orientation)

MCP SHALL expose at least these resources:

| URI | Content |
|-----|---------|
| `office://manifest` | shell identity, version/ref, entrypoint, transports, status summary |
| `office://roles/{id}` | role card: does / does not, skills, typical questions |
| `office://teams` | registry projection: name, type, status, agents, capacity notes |
| `office://templates` | lab-crew / product-factory / dev-crew + roles inside each |
| `office://onboarding-guide` | how a team joins, idle/wake, Lab → Spec → Dev |
| `office://secrets-checklist` | required secrets by scope; presence only, never values |
| `office://workflow` | pipeline + which bus events matter |

Resources SHALL be read-only and MUST NOT wake agents as a side effect.

### Tools (v1)

MCP SHALL implement at least:

| Tool | Contract |
|------|----------|
| `office_status` | health of bus, office agents, registered teams |
| `list_teams` | filter by `type` / `status` |
| `list_agents` | office + team agents; include idle/running if known |
| `describe_agent` | role, skills, alive/idle, last event if known |
| `send_message` | see Send |
| `list_templates` | spawnable templates and default role sets |
| `plan_onboard` | see Onboarding |
| `apply_onboard` | see Onboarding |
| `check_readiness` | secrets + deps for `office` \| `team` \| `agent` \| a plan |
| `run_smoke` | wrap `scripts/smoke.py`; return level + pass/fail |
| `get_events` | recent bus events, optional actor/category filter |

### Send

`send_message` input SHALL include:

- `to` (address)
- `body` (string)
- optional `ticket` (Linear id, stored on the envelope if present)
- optional `wait_for` (seconds, maximum 15)

Behaviour:

1. Resolve `to`.
2. Wake the target if the lifecycle controller marks it stopped.
3. Deliver via the existing door path.
4. Return `status=accepted` with `message_id`, resolved `to`, and `woke`.

If `wait_for` is set, MCP MAY attach the first matching bus event.
A wait timeout SHALL NOT convert an accepted send into a failure
(`wait: timed_out` is allowed).

Send MUST be wake-aware. Delivering to a stopped agent without wake is a spec
violation (`wake_failed` / `send_failed`).

### Onboarding

Onboarding SHALL be two-phase.

`plan_onboard`:

- Input: one or more `{type: lab\|spec\|dev, count: N, ref?: string}` plus
  optional `token_policy` (`inherit_office` \| `per_team` \| `per_agent`).
- Effect: none on registry or compose.
- Output: `plan_id`, proposed instance names, port/name allocations,
  missing readiness items, token policy that will apply.

`apply_onboard`:

- Input: `plan_id`.
- SHALL refuse with `not_ready` if `check_readiness` for that plan is red.
- SHALL refuse with `plan_expired` if the plan no longer matches current
  registry/ports.
- On success: instances on disk, registry entries, derived agent tokens
  per policy, foundation smoke for the new teams.

`count > 1` for a type is allowed (e.g. four Dev teams in one plan).

### Secrets and readiness

`check_readiness` SHALL report at least:

- GitHub token (office / team / agent)
- Linear token
- inference / model credentials
- database credential if the target template requires one

Each item SHALL include `scope`, `present` (boolean), and a short hint
pointing at `docs/secrets.md` / `tokens/tokens.example.yaml`.

MCP tools MUST reject payloads that contain raw secret values
(`secret_refused`). Operators write `tokens/tokens.yaml`; MCP only checks
and asks `manage_tokens.py` to derive agent views.

### Errors

Tool errors SHALL use a stable `code`:

`not_found`, `not_ready`, `plan_expired`, `wake_failed`, `send_failed`,
`invalid_address`, `secret_refused`, `conflict`.

### Observability

MCP SHALL publish bus events for its own mutations at least:

- `mcp.plan_created`
- `mcp.onboard_applied`
- `mcp.send_accepted`

Reads (`office_status`, resource fetch, `get_events`) NEED NOT emit events.
