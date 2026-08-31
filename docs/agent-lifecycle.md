# Agent Container Lifecycle (idle stop + wake-on-demand)

## Problem

By default every agent container runs continuously (`restart: unless-stopped`).  
When a factory has many agents and several team instances, most of them are idle most of the time and still consume RAM/CPU.

We want:

- An agent with **no work for ~40 minutes** is stopped.
- When another agent (or the human) needs it, the target is **woken**, becomes healthy, and only then receives the message.
- Long multi-step work is safe: if QA works for an hour and then messages Developer, Developer may already be stopped — QA must wake it first, then deliver the task.

## Design principles

1. **Always-on only what must be always-on**  
   Shared Redis bus, shared pre-prod, and a small **lifecycle controller** stay up.  
   Individual agent containers are ephemeral.

2. **Wake is part of send**  
   Sending a message to an agent is responsible for ensuring the agent is reachable.  
   Callers do not manually manage Docker in normal flow.

3. **Redis is the coordination point**  
   Last activity, desired state, and active-task locks live on the shared bus/Redis so any agent in the Office can reason about others.

4. **Idempotent and race-safe**  
   Concurrent wakes of the same agent must not break; stop must not kill an agent that still has an active task.

## Components

### 1. Lifecycle controller (per team / factory instance)

A small always-on service (one container per team compose is enough for v1).

Responsibilities:

- Track agent state: `running | starting | stopping | stopped`
- Record `last_active` timestamps
- **Stop** agents that exceeded `IDLE_TIMEOUT` (default **40 minutes**) and have no active task
- **Start** agents on wake request
- Wait for health before reporting success
- Publish bus events: `agent.started`, `agent.stopped`, `agent.wake_failed`, `agent.wake_ignored`

It talks to the local Docker engine (docker.sock) for the containers it owns.

### 2. Smart door client (`crew/crew-send.py`)

**Canonical client rule:** there is exactly one door client — `crew/crew-send.py`
at the Office repo root. Every instance mounts that file read-only into every
agent container at `/opt/crew/crew-send.py` (alongside the per-instance
`crew/` mount); instances do NOT ship their own copy. A missing client, or a
per-instance copy that diverges from the canonical file, is a spec violation.

The client delivers a message to an agent's webhook door. Delivery is
wake-aware (**sender-side wake contract**):

1. **POST** the signed message to the door (container URL when `--container`
   is used, host URL otherwise).
2. **On door-down** (connection refused / timeout / 5xx) the client publishes
   an `agent.wake` envelope for the target, durably (`publish_event` on
   `office:events`) and on the live inbox channel (`office:inbox:<target>`).
3. **Wait** up to the wake timeout (default **90s**, `WAKE_TIMEOUT_S`) for the
   target door to answer `/health` with 200.
4. **Re-deliver** the original message once the target is healthy.
5. **Fail loudly** — exit non-zero — if the wake times out OR if the
   re-delivery fails after a successful wake. The message is never silently
   dropped.

4xx responses (bad signature, unknown target, ...) are client errors and do
**not** trigger a wake — restarting the container would not fix them.

**Target derivation rule:** the `agent.wake` envelope target is the
controller-recognized agent id — the **host of the target entry's
`container_url`** in `crew/agents.json`. Per-instance registries are keyed by
short role, so the `developer` entry in team `dev-1` (container URL
`http://dev-1-developer:8644/webhooks/inbox`) yields target `dev-1-developer` —
exactly the id/container factory-control registers (`{instance}-{role}`). An
entry MAY carry an explicit `wake_hint`; if present it is used instead,
normalized `team:role` → `team-role` (colon → hyphen).

If wake fails → return a clear error; do not silently drop the message.

### 3. Activity signals

Anything that means “this agent is working” refreshes `last_active`:

- Inbound door message accepted
- `task.started` / meaningful work heartbeat
- Optional periodic heartbeat while an LLM session is open

**Active task lock:** while an agent has an in-flight task it should set a short-lived / renewable lock (`agent:{id}:busy`). The stopper must not stop a busy agent even if wall-clock idle heuristics are wrong.

## Sequence examples

### Idle stop

```text
Developer finishes work → task.finished → last_active updated
… 40 minutes with no new inbound / no busy lock …
Lifecycle controller → docker stop developer → agent.stopped on bus
```

### Wake then message (QA → Developer)

```text
QA wants to send work to Developer
  → crew-send / internal client checks Developer health
  → not healthy → agent.wake (Developer)
  → lifecycle controller: docker start → wait health
  → agent.started on bus
  → original message POSTed to Developer door
  → last_active(Developer) updated
```

If Developer was already up, wake is a no-op and the message goes through immediately.

### Long QA session then back to Developer

```text
Developer stopped after idle
QA works 60+ minutes (its own last_active keeps QA alive)
QA finally needs Developer again
  → same wake-then-send path as above
```

## Configuration (suggested defaults)

| Setting | Default | Notes |
|---------|---------|--------|
| `IDLE_TIMEOUT` | 40m | No activity + not busy → eligible to stop |
| `WAKE_TIMEOUT` | 90s | Max wait for container to become healthy |
| `STOP_CHECK_INTERVAL` | 2–5m | How often the controller scans for idle agents |
| `BUSY_LOCK_TTL` | renewable, e.g. 15m | Prevents stop during long tasks |

Always-on services (Redis, lifecycle controller, later pre-prod helpers) use `restart: unless-stopped`.  
Agent services use `restart: "no"` so only the controller decides start/stop.

## Compose sketch (per team)

```yaml
services:
  shared-memory:        # or external Office Redis
    ...
    restart: unless-stopped

  lifecycle:
    ...
    restart: unless-stopped
    volumes:
      - /var/run/docker.sock:/var/run/docker.sock
    environment:
      - IDLE_TIMEOUT=40m
      - WAKE_TIMEOUT=90s

  developer:
    ...
    restart: "no"          # controller-managed
    # no depends_on that forces permanent up

  qa:
    ...
    restart: "no"
```

(Exact service names and networks follow the existing team templates.)

## Failure modes and mitigations

| Risk | Mitigation |
|------|------------|
| Wake timeout | Fail the send with explicit error; caller can retry |
| Double wake | Redis lock / idempotent start |
| Stop during work | `busy` lock + only stop when idle and not busy |
| Controller down | Agents that are already running keep running; wakes published while the controller is down are picked up by the durable re-scan (XREAD `office:events` on startup + scan interval) and processed idempotently once it is back |
| Docker sock permission | Same pattern already used by devops/developer images in dev-crew |
| Storm of starts | Rate-limit wakes per agent; coalesce concurrent requests |

## What stays always on

- Office shared Redis bus
- Lifecycle controller(s)
- Shared pre-prod (when the Office brings it up)
- Optional thin always-on metrics/CLI helpers

Agents sleep. Infrastructure that coordinates them does not.

## Relation to Agent Office

- This capability applies to **team factories** (Lab/Dev instances) first.
- Office agents (Architect, Staff Engineer, …) can use the same pattern later; in early Office they may stay always-on if few.
- Bus events (`agent.started` / `agent.stopped`) feed the Office CLI log and Scrum Master status views.

## Out of scope for v1

- Kubernetes scale-to-zero / Knative
- Migrating containers across hosts
- Predictive pre-warm based on ML
- Stopping the lifecycle controller itself

## Implementation order (suggested)

1. Spec + Redis state keys + bus events
2. Lifecycle controller MVP (stop idle + start on request)
3. Wake-aware `crew-send`
4. Busy lock from task start/finish hooks
5. Wire into lab-crew / dev-crew templates and Office onboarding checklist
