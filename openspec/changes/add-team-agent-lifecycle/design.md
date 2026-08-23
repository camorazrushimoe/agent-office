# Design: team lifecycle controller

## Context

Upstream phase A ships the Office shell with always-on agents (closed v1
decision). The lifecycle spec (`openspec/specs/agent-lifecycle`) still
requires idle-stop/wake for team factories. This change implements that
piece natively against the Office bus.

## Decisions

1. **One controller per team instance**, scoped by Docker Compose project
   label (`com.docker.compose.project`). It filters containers by label, so
   it cannot stop the Office shell or sibling teams even with docker.sock.
2. **Bus is the coordination point** (per design principle 3 of
   docs/agent-lifecycle.md): wake requests arrive as `agent.wake`
   envelopes on `office:inbox:{agent}`; state/busy/last_active live in
   Redis keys readable by everyone.
3. **Events land in upstream's durable stream** `office:events` (XADD) so
   `crew/office-log.py --follow` shows lifecycle transitions without any
   new tooling; we also fan out on pub/sub for low-latency followers.
4. **Wake coalescing**: concurrent wakes collapse onto one starter via an
   in-process waiter set (idempotent-start requirement).
5. **Busy lock**: renewable key `office:busy:{agent}` (TTL 15m default);
   reaper skips busy agents regardless of wall-clock idle.

## Risks / Trade-offs

- [In-process coalescing] → single-controller assumption; acceptable for
  one instance per host in v1, noted in ops docs.
- [Pub/sub duplication] → two delivery paths (stream + topic); readers
  choose one; dedupe by envelope id if both are consumed.
