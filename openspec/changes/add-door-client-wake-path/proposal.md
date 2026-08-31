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
the wake listener + idempotent start (matching registered id/container) — the
missing piece is the door client's obligation to invoke the wake path, and the
composition guarantee that every instance actually has that client.

# What Changes

- Pin the **sender side** of the wake contract into `agent-lifecycle`: the
  canonical door client SHALL, when a delivery hits a stopped/unhealthy door,
  publish `agent.wake` (durably), targeting the controller-recognized id
  derived from the entry's `container_url` host (short role key →
  instance-prefixed id, e.g. `developer` → `dev-1-developer`; an optional
  `wake_hint` overrides, normalized `team:role` → `team-role`), wait for health
  up to the wake timeout, re-deliver, and fail loudly (non-zero, no silent
  drop) if wake or re-delivery fails.
- Close the **subscribe gap** in `agent-lifecycle`: factory-control SHALL
  re-scan the durable event stream (`office:events`) for `agent.wake` on
  startup and each scan interval, so wakes published during a controller
  outage are re-processed rather than lost.
- Pin the **canonical client** into `composition`: the door client is the
  single canonical `crew/crew-send.py` at the Office repo root, delivered to
  every instance container by a read-only file mount at
  `/opt/crew/crew-send.py`. Instances do not ship copies; `crew/` carries only
  per-instance `agents.json` + `FACTORY-STANDARD.md`. A missing or divergent
  client is a spec violation (SHA-256 checked at instantiation/sync while
  copies remain).

# Capabilities

### Modified Capability
- `agent-lifecycle` — sender side of wake-on-delivery (door client)
- `composition` — template contract delivers the canonical door client

# Impact

- Affected specs: `specs/agent-lifecycle/spec.md`, `specs/composition/spec.md`
- Affected code (implementation PR, after this spec is approved):
  - `crew/crew-send.py` — wake-on-failure: derive the wake target from
    `container_url` host (or `wake_hint`), publish `agent.wake` (durable
    `publish_event` + `office:inbox:<target>` pub/sub), wait `/health` up to
    the wake timeout, re-deliver, non-zero exit on wake or re-delivery failure
  - `office/bus/client.py` — `BusClient.xread()` / `xrevrange_tail()` stream
    helpers; `send_wake()` accepts an `actor` (door client publishes as
    `<team>/crew-send`)
  - `office/lifecycle/factory_control.py` — durable re-scan of `office:events`
    for `agent.wake` (startup + interval, persisted high-water mark,
    tail-seeded first boot); emit `agent.wake_ignored` on unknown targets
    (currently log-only)
  - `office/manage_tokens.py` — `derive-agents` verifies the canonical-client
    rule (SHA-256) at sync time
  - `crew/validate_crew_send.py`, `office/lifecycle/validate_factory_control.py`,
    `scripts/smoke.py` — deterministic validation of the wake path, the
    durable re-scan, and the canonical-client rule
  - `instances/dev-1/crew/` + `instances/spec-1/crew/` — ensure
    `FACTORY-STANDARD.md` + `agents.json` are present (client arrives by
    read-only mount, not copy)
  - `instances/lab-1/crew/` — remove the shipped `crew-send.py` copy
  - `instances/*/docker-compose.yml` — add the canonical client mount
    (`../../crew/crew-send.py:/opt/crew/crew-send.py:ro`) to every agent
    service; keep `./crew:/opt/crew:ro`
  - `instances/*/OFFICE-ATTACH.md` — drop the non-existent `--wake` flag row;
    document automatic wake-on-failure
  - `docs/agent-lifecycle.md` — document the sender-side wake contract, the
    target-derivation rule, and the canonical-client rule

# Implementation notes (recorded during the implementation PR)

- **Wake trigger is 5xx / connection-level, not "any non-success"** (merged
  wording tightened in `e6872c4`): a 4xx answer means the door is UP and
  rejected the message — waking the container cannot help and must not be
  attempted. The narrowing was decided during review (pre-merge ruling: "Do
  NOT trigger wake on 4xx") and matches the proposal's "stopped/unhealthy
  door" intent.
- **First-ever boot of the durable re-scan seeds from the stream tail**, a
  concrete id rather than `0`, so the full `office:events` history is not
  replayed and reaper-stopped agents are not resurrected; restarts resume
  from the persisted high-water mark.
- **Plain (non-`--container`) invocation degrades to `container_url`** when an
  entry has no `host_url` — instance registries generated by `derive-agents`
  carry only `container_url` + `secret`.
