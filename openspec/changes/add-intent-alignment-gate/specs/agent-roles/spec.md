# agent-roles — intent alignment gate (Scrum Master stop authority)

## MODIFIED Requirements

### Requirement: Scrum Master

- SHALL be the primary convenient entry point for the human.
- SHALL be able to answer the current status of any known project by combining tickets, bus events and other signals.
- SHALL surface blockers, missing specifications and sequencing problems.
- SHALL be able to stop work and escalate to the customer when intent cannot be established (OFFICE-STANDARD rule 11; docs/intent-alignment-gate.md).

The fourth line is the delta. The stop authority is bounded by the
standard's guardrails (bias to release; no double-gating; a stop requires
named questions; a blocked series re-escalates to the human operator after
the 24 h window — "a stop must never be a parking lot"). The Scrum Master
gates its own Office tickets: verdict recorded on the ticket/PR,
`work.gate.passed` published; no exemption for being the gatekeeper.

Bus events added by this change: `work.gate.passed`, `work.gate.blocked`,
`work.gate.escalated` (docs/intent-alignment-gate.md, Observability).
