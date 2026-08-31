# Why

The wake-on-demand contract in `agent-lifecycle` has a controller side but no
sender side. The spec says *"any attempt to deliver a message SHALL ensure the
target agent is running and healthy"* and factory-control subscribes to
`office:inbox:*` to start the target on an `agent.wake` envelope — but nothing
specifies **who publishes `agent.wake`**. The canonical door client
(`crew/crew-send.py`) does not implement it: it POSTs to the door and exits on
connection-refused. The result is that when an agent is idle-reaped, any
agent→agent delivery fails with "connection refused" and work stalls until a
human manually restarts the target.

Observed in the field (2026-08-31): dev-1's tech-pm could not reach its
developer/QA after they were idle-reaped — *"door delivery impossible,
connection refused on dev-1-developer:8644 / dev-1-qa:8644"*. Two root causes:

1. `crew-send.py` never publishes `agent.wake` when the door is down — the
   sender side of the wake contract does not exist in code.
2. `instances/dev-1/crew/` and `instances/spec-1/crew/` do not ship
   `crew-send.py` at all (dev-1 has only `FACTORY-STANDARD.md` + `agents.json`;
   spec-1 has only `agents.json`), so those teams cannot send — let alone wake —
   their own teammates.

`send_wake()` already exists in the bus client, and factory-control already has
the wake listener + target normalization — the missing piece is the door
client's obligation to invoke the wake path, and the composition guarantee that
every instance actually ships that client.

# What Changes

- Pin the **sender side** of the wake contract into `agent-lifecycle`: the
  canonical door client SHALL, when a delivery hits a stopped/unhealthy door,
  publish `agent.wake` (durably), wait for health up to the wake timeout,
  re-deliver, and fail loudly (non-zero, no silent drop) if wake fails.
- Pin the **canonical client** into `composition`: every team instance SHALL
  ship `crew-send.py` + `FACTORY-STANDARD.md` + `agents.json` in its `crew/`
  directory, mounted into every agent container at `/opt/crew`. A missing or
  copy-paste-divergent client is a spec violation. There is exactly one door
  client; instances reference it, they do not fork it.

# Capabilities

### Modified Capability
- `agent-lifecycle` — sender side of wake-on-delivery (door client)
- `composition` — template contract ships the canonical door client

# Impact

- Affected specs: `specs/agent-lifecycle/spec.md`, `specs/composition/spec.md`
- Affected code (implementation PR, after this spec is approved):
  - `crew/crew-send.py` — wake-on-failure: publish `agent.wake` (durable
    `publish_event` + `office:inbox:<target>` pub/sub), wait `/health` up to
    the wake timeout, re-deliver, non-zero exit on wake failure
  - `instances/dev-1/crew/` — add canonical `crew-send.py` + `FACTORY-STANDARD.md`
  - `instances/spec-1/crew/` — add canonical `crew-send.py` + `FACTORY-STANDARD.md`
  - `instances/*/docker-compose.yml` — verify `./crew:/opt/crew:ro` mount
  - `docs/agent-lifecycle.md` — document the sender-side wake contract
