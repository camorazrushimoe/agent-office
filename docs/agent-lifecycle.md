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
- **Re-scan the durable event stream** (`office:events`) for `agent.wake` on
  startup and each scan interval, after a persisted high-water mark, so wakes
  published while the controller was down are re-processed (idempotently)
  rather than lost
- Publish bus events: `agent.started`, `agent.stopped`, `agent.wake_failed`, `agent.wake_ignored`

It talks to the local Docker engine (docker.sock) for the containers it owns.

### 2. Canonical door client (`crew/crew-send.py`)

There is **one** door client: `crew/crew-send.py` at the Office repo root. It is
delivered to every agent container as a read-only mount at
`/opt/crew/crew-send.py` (alongside the per-instance `crew/` mount containing
`FACTORY-STANDARD.md` + `agents.json`). Instances do not ship copies; a missing
or divergent client is a spec violation (SHA-256 checked at
instantiation/sync). The client implements the sender side of the wake
contract, so every send is wake-aware:

1. Resolve target agent in `crew/agents.json`
2. POST to the target door as today
3. If the door is **down** (connection refused, timeout, or 5xx) → **wake**:
   a. Publish `agent.wake` for the controller-recognized target id — durably
      (`publish_event` → `office:events`) and on the live inbox channel
      (`office:inbox:<target>`)
   b. Wait for the target door's `/health` to answer 200 (up to `WAKE_TIMEOUT_S`,
      default **90s**)
   c. Re-deliver the original message
4. **4xx answers never wake** — the door is up and rejected the message; waking
   cannot help
5. If the wake or the re-delivery fails → exit non-zero with a clear error
   naming the target; **the message is never silently dropped**

**Target derivation.** The wake envelope target is the controller-recognized
agent id: the **host of the entry's `container_url`** in `crew/agents.json`.
Per-instance registries are keyed by short role, so the `developer` entry in
team `dev-1` yields `dev-1-developer` — exactly the id/container
factory-control registers (`{instance}-{role}`). An entry MAY carry an
explicit `wake_hint`; if present it is used instead, normalized
`team:role` → `team-role` (colon → hyphen).

The lifecycle controller subscribes to `office:inbox:*` and handles
`agent.wake` by starting the target (idempotent — waking an already-running
agent is a no-op) and verifying health before treating it as ready.

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
  → crew-send POSTs to Developer door → connection refused (Developer stopped)
  → crew-send publishes agent.wake target=dev-1-developer (durable + inbox)
  → lifecycle controller: docker start → wait health
  → agent.started on bus
  → crew-send waits Developer /health → 200
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
| Controller down | Agents that are already running keep running; wakes published while down are re-processed from `office:events` on restart (durable re-scan, idempotent) |
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
