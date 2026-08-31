# Tasks — add-door-client-wake-path

## 1. Spec (this PR)
- [x] proposal.md
- [x] specs/agent-lifecycle/spec.md delta (MODIFIED "Wake on demand" — sender side)
- [x] specs/composition/spec.md delta (MODIFIED "Template contract" — canonical crew toolkit)

## 2. Implementation (follow-up PR after spec approval)
- [ ] `crew/crew-send.py` — wake-on-failure path: on door-down, publish
      `agent.wake` (durable `publish_event` + `office:inbox:<target>` pub/sub
      via the office bus client), wait `/health` up to the wake timeout,
      re-deliver, non-zero exit on wake failure. Normalize `team:role` →
      `team-role`.
- [ ] `instances/dev-1/crew/` — add canonical `crew-send.py` + `FACTORY-STANDARD.md`
- [ ] `instances/spec-1/crew/` — add canonical `crew-send.py` + `FACTORY-STANDARD.md`
- [ ] `instances/*/docker-compose.yml` — verify `./crew:/opt/crew:ro` mount on
      every agent service
- [ ] `docs/agent-lifecycle.md` — document the sender-side wake contract and
      the canonical-client rule
- [ ] Remove any per-instance copy-paste `crew-send.py` variants that remain;
      keep one canonical file referenced by all instances

## 3. Validation
- [ ] Wake path: stop an agent → `crew-send.py <agent> "x"` → agent starts,
      message delivered, exit 0
- [ ] Wake timeout: unregistered target → `agent.wake_ignored` emitted,
      sender exits non-zero
- [ ] dev-1 and spec-1 agents can send to and wake their own teammates
- [ ] Events visible via `crew/office-log.py` replay
