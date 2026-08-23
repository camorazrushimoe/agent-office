# Adversarial Architecture Review — PR #1 (feat/team-lifecycle-and-bus-hardening)

Lens: ARCHITECTURE — protocol coherence with bus/action-schema.json, coupling, layer separation, long-term risks.

VERDICT: needs-changes

## BLOCKING

**B1 — Wake delivery is architecturally broken: wildcard SUBSCRIBE.**
`docker_controller.run_forever()` subscribes with pattern `"office:inbox:*"` (line 232), but `BusClient.subscribe()` issues a plain Redis `SUBSCRIBE` (client.py:193), which matches exact channel names only. `PSUBSCRIBE` is required for a glob. As written, the controller will never receive a single `agent.wake` — the entire wake-on-demand feature is dead on arrival, and it fails silently (no error, just no messages). This is a protocol-contract violation between consumer and bus client.

**B2 — Lifecycle events bypass the durable stream, violating the stated contract.**
The proposal says events go "into the shared `office:events` stream … plus the live pub/sub topic." But `DockerLifecycle.emit()` calls raw `bus.publish(EVENTS_CHANNEL, ...)` (line 159), skipping `publish_event()` entirely — so `agent.started/stopped/wake_failed` never hit the `XADD office:events` durable log. The event recorder / `office-log.py` source of truth will silently miss every lifecycle transition. Two publish paths existing side-by-side is exactly the layering split the bus client was built to prevent ("this module is the ONLY place that knows the wire details").

**B3 — Claimed compose-project isolation does not exist; name collisions with Office containers.**
Docstring and proposal claim scoping "via COMPOSE_PROJECT label filter so it can never touch other projects' containers." The code never reads labels or uses `COMPOSE_PROJECT` for filtering — it addresses bare container names `agent-office-{agent_id}`. That prefix is identical to the Office shell (`agent-office-architect`, etc.). Any team instance whose registry contains an id colliding with an Office agent id means one team's idle reaper stops another factory's always-on Office agent — directly violating the v1 "Office agents are always-on" decision this PR claims to preserve. Either implement the label filter or fail loudly; don't ship the safety claim unimplemented.

## Non-blocking notes

- **TOCTOU in reap_idle:** busy-lock is checked, then stop happens up to seconds later; an agent that picks up work in between gets killed mid-task. A check-and-clear atomic op (or a post-stop busy re-check + emit of a `task.stale`) would narrow this. Also nothing clears `office:busy:{agent}` / stale state keys after an unclean stop — they'll linger forever (no TTL used).
- **`lifecycle.started` action** isn't among the schema's documented action examples. Schema is open-ended (no enum), so legal, but the schema doc should be updated alongside the spec delta since the PR adds new conventions anyway.
- **State truthfulness:** `get_state()` returns `"running"` as fallback when the container runs but no key exists — reasonable default, but combined with the missing key cleanup above, a crashed agent's last written state (e.g. `"stopping"`) can mislead readers indefinitely.
- **Config hygiene (adjacent):** `agents/architect/hermes-home/config.yaml` contains a plaintext webhook secret committed into the repo tree that is mounted read-only into every agent container via `.:/opt/repo:ro`. Not strictly this PR's scope, but worth an audit ticket — any team agent can read the Office webhook route secret.
- **Wake race:** two concurrent `agent.wake` messages for the same agent both enter the start/poll path; harmless today (idempotent-ish), but there's no per-agent serialization in the subscriber thread model to reason about once B1 is fixed.
