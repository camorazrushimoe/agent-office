# Why

The idle-stop half of `agent-lifecycle` exists only on paper. The lifecycle
controller (`office/lifecycle/docker_controller.py`) is not run anywhere (not
in compose, no host process), and nothing writes the `office:last_active:{agent}`
keys it depends on — so no agent has ever been stopped for idleness. Today all
16 agent containers stay up 24/7, contradicting the cold-start policy.

A temporary host-side `idle_reaper.py` proved the model works (it reaped six
idle agents within minutes), but a process living inside an operator's shell
session is not factory infrastructure: it dies silently and cannot be part of
the reviewed spec.

# What Changes

- **New always-on service `factory-control`** in the Office compose project:
  a small container that runs the lifecycle supervisor and is the ONLY
  component allowed to start/stop agent containers.
  - Always-on like shared-memory (`restart: unless-stopped`); it comes up
    with the factory (`docker compose up -d`) and goes down with it.
  - Mounts `/var/run/docker.sock` (scoped by an ownership allowlist — it
    manages only containers named in its agent registry) and reads agents'
    `logs/agent.log` via a read-only repo mount for activity detection.
  - Runs two loops:
    - **Idle reaper** — every CHECK_INTERVAL (default 120s): stops any
      registered agent container whose last meaningful activity
      (fresh task-work lines in `logs/agent.log`) is older than
      IDLE_TIMEOUT (default **40m**, per existing spec). Containers with no
      readable activity signal are left alone (fail-open).
    - **Wake listener** — subscribes to `office:inbox:*`; handles
      `agent.wake` envelopes by starting the target container.
  - Publishes `agent.started` / `agent.stopped` / `agent.wake_failed`
    through `publish_event()` (durable stream), per observability spec.
- **Activity signal**: "the agent is working" = recent task-work lines
  (`conversation_loop`, `tool_executor`, inbound message, response ready)
  in that agent's Hermes log. This replaces the never-implemented
  `last_active` Redis key contract.
- The legacy `docker_controller.py` is superseded by this service; removal is
  tracked in `tasks.md` and happens in the implementation PR.
- Operator ergonomics: the supervisor runs headless; dashboards (e.g.
  factory-dashboard skill) read docker state directly and need no changes.
- Config knobs (`.env.example`): `IDLE_TIMEOUT=40m`, `CHECK_INTERVAL=120s`,
  `WAKE_TIMEOUT=90s`.

# Capabilities

### Modified Capability
- `agent-lifecycle` — runtime home for the controller + activity-signal contract

# Impact

- Affected specs: `specs/agent-lifecycle/spec.md`
- Affected code:
  - NEW `office/lifecycle/factory_control.py` (supervisor, adapted from the
    proven `idle_reaper.py`)
  - `docker-compose.yml` — new always-on `factory-control` service
  - `.env.example` — IDLE_TIMEOUT, CHECK_INTERVAL knobs
