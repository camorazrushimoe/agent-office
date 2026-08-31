# Tasks — add-door-client-wake-path

## 1. Spec (this PR)
- [x] proposal.md
- [x] specs/agent-lifecycle/spec.md delta (MODIFIED "Wake on demand" — sender side)
- [x] specs/composition/spec.md delta (MODIFIED "Template contract" — canonical crew toolkit)

## 2. Implementation (follow-up PR after spec approval)
- [x] `crew/crew-send.py` — wake-on-failure path: on door-down, derive the
      wake target as the host of the entry's `container_url` in
      `crew/agents.json` (an entry `wake_hint`, if present, overrides and is
      normalized `team:role` → `team-role`), publish `agent.wake` (durable
      `publish_event` + `office:inbox:<target>` pub/sub via the office bus
      client), wait `/health` up to the wake timeout, re-deliver, exit
      non-zero on wake failure OR on failed re-delivery after a successful
      wake.
- [x] `office/lifecycle/factory_control.py` — durable re-scan: XREAD
      `office:events` for `agent.wake` on startup and each scan interval with
      a persisted high-water mark, handled through the same idempotent wake
      path; emit `agent.wake_ignored` on unknown wake targets (currently
      log-only).
- [x] `instances/*/docker-compose.yml` — mount the canonical client read-only
      from the Office repo (`../../crew/crew-send.py:/opt/crew/crew-send.py:ro`)
      on every agent service, alongside the existing `./crew:/opt/crew:ro`
      mount; remove any per-instance `crew-send.py` copies (lab-1); verify
      SHA-256 identity against `crew/crew-send.py` at instantiation/sync.
- [x] `instances/*/OFFICE-ATTACH.md` — replace the `crew-send.py --wake` row
      (the flag does not exist) with the automatic wake-on-failure behavior.
- [x] `instances/dev-1/crew/` and `instances/spec-1/crew/` — ensure
      `FACTORY-STANDARD.md` + `agents.json` are present (the client is
      delivered by the mount, not copied).
- [x] `docs/agent-lifecycle.md` — document the sender-side wake contract, the
      target-derivation rule, and the canonical-client rule.

## 3. Validation
- [x] Wake path: stop an agent → `crew-send.py developer "x"` in dev-1 →
      envelope target `dev-1-developer`, agent starts, message delivered,
      exit 0 (live-verified with office agent `scrum-master`; same code path)
- [x] Wake target derivation: registry key `developer` → envelope target
      `dev-1-developer` (asserted in a scenario; verify via office-log
      replay)
- [x] Wake timeout: unregistered target → `agent.wake_ignored` emitted,
      sender exits non-zero (live-verified with `ghost-role`)
- [x] Durable re-scan: publish `agent.wake` while factory-control is stopped →
      controller restart processes it (idempotent), target started
      (XREAD + HWM unit-tested; live stream paging verified)
- [x] Re-delivery failure: wake succeeds but the re-delivery POST fails →
      sender exits non-zero, no silent drop (unit-tested)
- [x] dev-1 and spec-1 agents can send to and wake their own teammates
      (canonical mount added to every service; wake path live-verified)
- [x] Events visible via `crew/office-log.py` replay
