# Adversarial Review — PR #1 (feat/team-lifecycle-and-bus-hardening)

Lens: ENGINEERING — is the implementation minimal/unambiguous/resource-efficient? Simpler approaches within existing spec? Underspecified behavior? Risks/gaps only, no redesigns.

VERDICT: needs-changes

## BLOCKING

**1. `COMPOSE_PROJECT` is dead code — the documented isolation guarantee is not implemented.**
`docker_controller.py:27` reads `COMPOSE_PROJECT` and the module docstring promises containers are "scoped to this compose project (COMPOSE_PROJECT label filter)". It is never used again. All Docker calls go through `container_name()` = `agent-office-{agent_id}` — a plain name lookup with no label filter and no `/containers/json?filters=` scoping. Any other compose project on the host with a colliding name (`agent-office-scrum-master` is quite generic) will be inspected/started/stopped by this controller. Either implement the filter or delete the claim and the env var; right now the safety property exists only in the docstring.

**2. Wake/reap concurrency is uncoordinated; wake also serializes all inbox traffic.**
- `wake()` runs on the subscriber thread and polls up to `WAKE_TIMEOUT_S` (default 90s). During that time *no other wake messages are processed* — one slow start head-of-line-blocks every queued wake.
- The main thread's `reap_idle()` can stop the very container `wake()` is polling into "running" — there is no shared lock, and `wake()` never sets `office:busy:{agent}`. A wake followed by >40m without the agent touching `last_active` gets reaped mid-work; nothing in these files defines who owns `BUSY_KEY`, so the invariant "busy ⇒ not reaped" is underspecified.
- No dedup/idempotency: two `agent.wake` envelopes for the same target produce two sequential full start/poll cycles (the second is saved only by the `is_running` fast path — but during the first wake's poll window both will run `start_agent`, which errors on an already-starting container and emits a spurious `agent.wake_failed`).

**3. Lifecycle events bypass the durable event log.**
`emit()` publishes directly to the pub/sub topic (`EVENTS_CHANNEL`) via raw `bus.publish`. Every other producer is expected to go through `publish_event()` (XADD to `office:events` + fanout), which `bus/client.py` documents as the "event log source of truth" and which `office-log.py` reads. Result: `agent.started` / `agent.stopped` / `agent.wake_failed` / `lifecycle.started` are visible only to live `--follow` followers and vanish on replay. This breaks the stated bus contract for exactly the events the team-lifecycle feature exists to produce.

## NON-BLOCKING NOTES

- **Resource efficiency:** `BusClient.cmd()` opens a fresh TCP connection per command; `reap_idle()` therefore makes ~2–4 connect/auth/select round trips per agent per 120s cycle, and `publish_event` uses a pipeline per call. Fine at N=4, worth a persistent command connection later.
- **Dead code:** `docker_controller.py:56–63` builds a `urllib.request.Request` and defines a `UnixConnection` subclass that are never used — the actual transport is the `UnixHTTPConnection` below. Also `IDLE_TIMEOUT` is assigned twice (lines 24, 43).
- **Stop-failure handling:** `reap_idle` sets state to `"stopped"` even when `stop_agent` raised (line 213); a container that ignored SIGKILL-timeout leaves a misleading `stopped` state key behind (`get_state` prefers live Docker status anyway).
- **Stuck transient states:** if the controller crashes between `set_state("starting")` and the poll loop, the state key stays `"starting"` forever; nothing reconciles it against Docker truth on restart.
- **Compose gap:** neither `docker-compose.yml` nor any profile runs the lifecycle controller itself — it must be launched out-of-band. If intentional (host-side supervisor), document it; otherwise the feature has no runtime home.
- `parse_duration` raises at import time on malformed `IDLE_TIMEOUT` — fail-fast is arguably correct, but the error is a bare `ValueError` with no mention of the env var.
- `keys()` exposes Redis `KEYS` in a shared client — O(N) hazard if anyone ever calls it against a populated bus.
