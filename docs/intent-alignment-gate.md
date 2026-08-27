# Agent Office — Intent Alignment Gate (foundation)

**Status:** foundation standard. Applies to every team (Lab / Spec / Dev) and every agent.
**Owner of the check:** Scrum Master. Skill: `agents/scrum-master/skills/intent-alignment-gate/`.
**Golden rule:** OFFICE-STANDARD rule 11.

---

## Why this exists

Work changes shape as it passes through hands.

```
human states a goal
    → Office routes it
        → tickets are written
            → an agent picks one up
                → work begins
```

Every step is locally reasonable. The drift is only visible **end to end**, and no single agent sees end to end — the team sees its ticket, the human sees the original ask. Only Scrum Master sits at both ends.

The failure this prevents is not a team working badly. It is a team working **well on the wrong thing**, which is more expensive, because it looks like progress the whole way.

## The rule

> **Before any agent moves a Linear ticket (or a series) to `In Progress`, it MUST ask Scrum Master to confirm the work still serves the stated business goal, and MUST wait for the verdict.**

- Ask about a **series**, not each ticket. One gate for a phase is the norm.
- The gate is expected to take minutes. If it becomes slow, that is a defect in the gate, not a reason to skip it.
- No verdict yet is **not** permission to start.
- The gate is not a quality review of the plan. Method belongs to the team.

## Verdicts

| Verdict | Meaning | Effect |
|---------|---------|--------|
| **ALIGNED** | Work serves a goal Scrum Master can name in the customer's terms | Team starts. The goal line is recorded on the ticket. |
| **DRIFTED, fix obvious** | Named drift with a clear correction | Tickets adjusted, drift logged, team starts |
| **DRIFTED, fix unclear** | Drift with no obvious correction | **Work stops. Escalate to the customer.** |
| **UNCLEAR** | Cannot establish whether this should be done at all | **Work stops. Escalate to the customer.** |

"Well-formed" is not "aligned". A well-planned answer to the wrong question is exactly what this gate catches.

## Authority to stop

Scrum Master **may stop work** and escalate. This is expected behaviour, not an incident.

An idle factory is cheaper than a factory building the wrong thing. The gate is the one place where stopping is the correct output.

A stop requires:

- affected tickets moved to `Blocked` with a reason
- an explicit instruction to the team: stop, do not start, wait
- a `work.gate.blocked` event on the bus — rule 1, no silent work
- an escalation to the customer containing **specific answerable questions** and a recommendation

A stop with no questions attached is obstruction, not escalation.

While blocked, the team does **not** iterate on the plan. That turns a stop into a loop.

## Escalation asks for goals, not specs

When intent cannot be established, ask the customer in business terms:

- What decision will this let you make?
- What would make this a waste of money?
- If we could only deliver one thing here, what would it be?

Do not ask for a technical specification. A specification is what caused the drift; more of it will not recover the intent.

## Drift patterns to check for

- **Scope inflation** — tickets cover more than the intake asked, each addition individually sensible
- **Proxy substitution** — measuring something adjacent because the real thing is hard
- **Means became the end** — building the tool instead of answering the question
- **Stale premise** — the intake's assumption has since been disproved, sometimes by our own findings
- **Inherited assumption** — a decision from an earlier hand, now treated as a requirement nobody can source
- **Unbounded exploration** — lots of activity, no stated finish line
- **Orphan work** — a ticket that traces back to no stated goal

## Observability

Every verdict is an event, so the whole chain is auditable:

```bash
python3 crew/publish-event.py work.gate.passed  scrum-master "<series>: aligned — serves <goal>" --target <team>
python3 crew/publish-event.py work.gate.blocked scrum-master "<series>: blocked — <gap>"        --target <team>
```

`ALIGNED` verdicts record **the goal the work serves, in one line**, on the ticket or thread. That line is what the team checks its own output against, and what Scrum Master re-checks if the work drifts later.

## Guardrails

- Scrum Master is **not a second planner**. Gate intent, not method.
- Do not gate the same series twice without new information — the anti-loop rules apply to Scrum Master too.
- **Bias to release.** Stop on genuine inability to connect work to goal, not on style disagreement.
- Log every verdict, including the fast passes.

## Team factories must inherit this

This is Office-level, and it binds every team. The team factory templates each need the matching change so new instances inherit it:

- [ ] `lab-crew` — team standard + research-lead pulls the gate before Phase start
- [ ] `dev-crew` — `FACTORY-STANDARD.md` + `tech-pm` task-dispatch skill
- [ ] `product-factory` — team standard + `tech-pm`

Until those land, Scrum Master enforces the gate from the Office side.

## Escape hatch

The human may override the gate. Every override is recorded as an explicit event, and if it creates risk or debt, as a tracked item.
