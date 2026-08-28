# Change: intent alignment gate

## Why

Work changes shape as it passes through hands: the human states a goal, Office
routes it, tickets are written, an agent picks one up. By the time work starts,
what is being built can quietly stop being what was asked for — and the drift
is only visible end to end, where only Scrum Master sits.

`crew/OFFICE-STANDARD.md` golden rule 11 makes the pre-start intent check
mandatory, but the gate had no foundation record: no capability-spec delta for
the Scrum Master's new stop authority, no change record, no unblock path when
the customer is absent. This change records the gate as a foundation standard
and closes those gaps.

## What Changes

- `crew/OFFICE-STANDARD.md` — golden rule 11: no work starts without an intent
  check; Scrum Master MAY stop work and escalate when intent cannot be
  established.
- `docs/intent-alignment-gate.md` — foundation standard: the rule, verdicts
  (ALIGNED / DRIFTED / UNCLEAR), authority to stop, escalation shape, drift
  patterns, guardrails, timeouts/unblock path (24 h re-escalation window,
  self-gating).
- `agents/scrum-master/skills/intent-alignment-gate/SKILL.md` — Scrum Master's
  procedure: reconstruct the intent chain, four questions, drift patterns,
  verdicts, stop/escalate. Commands run inside the SM container
  (`/opt/crew/office-log.py`, `/opt/crew/publish-event.py` over `OFFICE_BUS_URL`
  — no docker, no host repo path).
- `openspec/specs/agent-roles/spec.md` — Scrum Master gains: SHALL be able to
  stop work and escalate to the customer when intent cannot be established.
- Bus events: `work.gate.passed`, `work.gate.blocked`, `work.gate.escalated`.

## Impact

- Affected specs: `agent-roles` (Scrum Master capability delta)
- Affected code: none — standard + skill only; no changes to compose, doors, or
  crew-send.
