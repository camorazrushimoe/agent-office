# Why

Agent Office is a multi-container meta-factory: shared Redis bus, four Office
agents, factory-control lifecycle, webhook doors, and attached team instances.
Local foundation changes (skills, SOULs, bus client, compose, factory-control,
config render) regularly risk silent breakage that only shows up much later
when an agent tries to talk to another agent or when a human runs a real task.

There is no fast, deterministic check that the **shell foundation** still
works after a change. Full pipeline / LLM-driven tests are too slow and too
expensive for the "I just fixed something locally — is the factory still
alive?" loop that every agent and human needs.

# What Changes

- **New capability `foundation-smoke`**: a hierarchical, levels-based smoke
  test for the Office shell. Goal: < 90s for a full run, exit 0 means
  "foundation is coherent enough to keep working".
- **CLI entrypoint** `scripts/smoke.py` (and thin `scripts/smoke.sh` wrapper):
  runnable from the host after `docker compose up -d` (or when agents are
  already idle-stopped). Levels can be selected independently.
- **Levels** (each higher level includes the lower ones):
  - **0 Static** — required files present, action-schema JSON valid,
    agents registry present (or clear guidance to copy example).
  - **1 Infra** — compose project services reachable; Redis PING on the
    shared bus (host port 6380 by default); factory-control container exists.
  - **2 Bus** — durable roundtrip: publish a known event to `office:events`,
    read it back (same path `crew/office-log.py` / XREVRANGE uses).
  - **3 Doors + lifecycle** — for each Office agent door: if the container
    is stopped, request wake; wait until Running; POST a signed smoke ping
    via the existing door client path; assert HTTP 2xx. **Does not wait for
    an LLM reply** — acceptance of the message is enough.
- Smoke publishes its own start/ok events so the run is visible in
  `crew/office-log.py`.
- Out of scope for v1: team-instance smokes (lab-1/dev-1/spec-1), Linear/
  GitHub live calls, full pipeline, waiting on LLM output.

# Capabilities

### Added Capability
- `foundation-smoke` — hierarchical foundation health check for the Office shell

# Impact

- Affected specs: new `openspec/specs/foundation-smoke/spec.md`
- Affected code:
  - NEW `scripts/smoke.py`
  - NEW `scripts/smoke.sh`
  - README quick-start pointer (optional, light)
- No change to runtime agent behaviour, compose topology, or bus schema.
- Future agents and humans can read the permanent spec to know what is
  covered by the foundation gate.
