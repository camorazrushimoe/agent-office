# Migration: Lab / Dev crews → Office shared bus + lifecycle

How existing team factories (`lab-crew`, `dev-crew`) connect to Agent Office without becoming a permanent always-on tax.

## Goals

1. Drop **per-team Redis**; use the **Office shared Redis bus**.
2. Keep team private **dev-clusters** (Dev) and agent isolation.
3. Add **idle stop + wake-on-demand** for agent containers.
4. Remain compatible with existing doors (`crew-send` + HMAC webhook).

## Target end state (per team instance)

| Component | Was (standalone) | Becomes |
|-----------|------------------|--------|
| Redis | Local `shared-memory` service | External Office Redis (or single shared instance) |
| Agent containers | `restart: unless-stopped` | `restart: "no"`, managed by lifecycle controller |
| Lifecycle | None | Always-on `lifecycle` service in the team compose |
| Doors | Direct to agent ports | Same doors, but send path is wake-aware |
| Bus events | Team-local | Office-wide schema (`bus/action-schema.json`) |

## Steps (high level)

### A. Bus connection

1. Point team agents at Office Redis URL (env / instance config).
2. Stop creating a local Redis service in team compose (or keep only for emergency offline mode — not default).
3. Emit Office-compatible envelopes (actor/action/target/timestamp; optional team/project).
4. Qualify actor names when multiple team instances exist (`dev-crew-1/developer`).

### B. Lifecycle

1. Add `lifecycle` service with docker.sock access to the team’s agent containers only.
2. Set agent services to `restart: "no"`.
3. Implement stop-on-idle (default 40m) + wake API/bus action.
4. Make `crew-send` (host + in-container) wake-aware before POST.
5. Wire `task.started` / `task.finished` (or equivalent) to busy lock + `last_active`.

### C. Registry & onboarding

1. Register the team instance in Office team registry (endpoints, type, name).
2. Smoke-test: Office → wake team agent → message → event appears in Office CLI log.
3. For Dev teams: confirm promotion path to shared pre-prod still works with Super DevOps rules.

### D. Observability

1. Team-level dashboards may remain for deep local debug.
2. Cross-team truth is Office bus + CLI log (`agent.started` / `agent.stopped` included).

## Compatibility notes

- **dev-crew** already mounts docker.sock on developer/devops — lifecycle follows the same trust model, scoped to its compose project.
- **lab-crew** is still lighter; same lifecycle pattern applies once containers exist.
- Existing HMAC doors stay; only the client path gains “ensure up” behaviour.
- Do not wake the entire team on every message — wake **only the target agent**.

## Risks

- First message to a cold agent is slower (cold start). Acceptable; timeout must be explicit.
- Misconfigured busy lock → unwanted stops mid-work. Prefer renewable locks tied to real task hooks.
- Office Redis becomes a critical dependency for all teams — treat it as tier-0 infra.

## Checklist (copy into onboarding)

- [ ] No default local Redis
- [ ] Connected to Office bus
- [ ] Lifecycle controller present
- [ ] Agents `restart: "no"`
- [ ] Wake-aware send path
- [ ] Busy lock from task hooks
- [ ] Registered in Office
- [ ] Smoke wake + message + event log
- [ ] (Dev) Promotion path validated
