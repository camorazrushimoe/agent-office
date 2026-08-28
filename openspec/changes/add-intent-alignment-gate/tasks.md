# Tasks: add-intent-alignment-gate

## 1. Standard

- [x] 1.1 OFFICE-STANDARD golden rule 11 — intent check before `In Progress`; SM stop authority
- [x] 1.2 `docs/intent-alignment-gate.md` — rule, verdicts, authority to stop, escalation shape, drift patterns, guardrails
- [x] 1.3 Timeouts and unblock path — 24 h re-escalation to human operator (`work.gate.escalated`); SM self-gating with verdict recorded
- [x] 1.4 Observability — `work.gate.passed` / `work.gate.blocked` / `work.gate.escalated` named; container and host forms

## 2. Procedure

- [x] 2.1 `agents/scrum-master/skills/intent-alignment-gate/SKILL.md` — four questions, drift patterns, verdicts, stop/escalate
- [x] 2.2 Commands runnable inside the SM container — `/opt/crew/office-log.py`, `/opt/crew/publish-event.py` via `OFFICE_BUS_URL`; no docker, no `~/agent-office`

## 3. Spec delta

- [x] 3.1 `openspec/specs/agent-roles/spec.md` — Scrum Master stop-authority line
- [x] 3.2 `openspec/changes/add-intent-alignment-gate/` record (this change)

## 4. Review gate

- [x] 4.1 PR #20 opened; Architect review (B1–B3) addressed in the fix pass on the same branch
- [ ] 4.2 Team factory templates inherit the gate (`lab-crew`, `dev-crew`, `product-factory`) — tracked separately; see doc checklist
