# Adversarial Architecture Review — PR #20 (foundation: intent alignment gate)

> ## ⚠️ CORRECTION (Architect, 2026-08-28) — verdict below is SUPERSEDED
>
> The review body below is a point-in-time snapshot of `02b0719` (pre-rebase). It
> remains valid as the audit trail of what was found, but **all three blocking
> items have been fixed and independently re-verified** on the rebased head
> `3fce132` (fix pass `8d3c8bb` + `3fce132`, base `main` @ `5586974`):
>
> - **B1 resolved** — SKILL.md ships only container-runnable commands
>   (`python3 /opt/crew/office-log.py --count 50 --project …`,
>   `python3 /opt/crew/publish-event.py … --target …`); no docker, no
>   `~/agent-office`. Verified against the SM compose volumes
>   (`./crew:/opt/crew:ro`, `OFFICE_BUS_URL=redis://shared-memory:6379`) and the
>   actual script CLIs.
> - **B2 resolved** — `openspec/specs/agent-roles/spec.md` Scrum Master section
>   carries the stop-authority line; `openspec/changes/add-intent-alignment-gate/`
>   (proposal + delta + tasks) exists, delta format matches repo convention and
>   its requirement bullets are identical to the live spec section.
> - **B3 resolved** — 24 h re-escalation window to the human operator
>   (`work.gate.escalated`) + defined SM self-gating, in both the doc and the
>   SKILL. The "silent stalemate / parking lot" deadlock mode is closed.
>
> **MERGED** to main as `9581530` (2026-08-28, oversight; re-check confirmed
> B1 container form, B2 capability line, B3 24 h window present on `3fce132`).
>
> **Current verdict: APPROVE** — posted as the Architect review on head
> `3fce132967432e1c908880250c9b1aa9e8dc0f63` (2026-08-28 10:48 UTC).
>
> Non-blocking notes still open at approval (tracked, not gating):
> N1 (team-factory template inheritance — doc checklist + `tasks.md` 4.2),
> N2 (`work.gate.*` events not yet in `docs/observability.md`'s catalog),
> N3 (Russian trigger phrases in SKILL description), N4 (Linear runtime
> signalling vs. gate trigger wording).
>
> ---

**Branch:** `foundation/intent-alignment-gate` @ `02b0719` (base `origin/main` @ `a748498`)
**Scope:** +259/−0 in 3 files — `agents/scrum-master/skills/intent-alignment-gate/SKILL.md`,
`docs/intent-alignment-gate.md`, `crew/OFFICE-STANDARD.md` (+3)
**Reviewer:** Architect · 2026-08-27 18:20 UTC · read-only review (single pass)

---

## VERDICT: **needs-changes** (3 blocking)

The concept is sound and well-argued: intent drift is visible only end-to-end,
Scrum Master is the only agent at both ends, and a stop with named questions is
the right escalation shape. The split of artifacts is also correct: golden rule
11 = contract, `docs/intent-alignment-gate.md` = standard, `SKILL.md` =
procedure. The problems below are about *where the authority is recorded*,
*whether the shipped commands actually run*, and *whether the gate can lock
indefinitely*.

### Answers to the requested questions

**Does a stop-authority gate belong in a SKILL.md?**
The *procedure* does — and it is correctly placed there (the skill is mounted
into the SM at `/opt/data/skills/agent-office` via
`docker-compose.yml` SM volumes, and its trigger description fires on the right
phrases). The *authority* belongs in the standard, and it is there (rule 11).
What is **not** in the right place: the authority itself is a change to the
Scrum Master's defined role, and the role's capability spec
(`openspec/specs/agent-roles/spec.md`, "Scrum Master" section) was not updated —
see B2.

**Does it conflict with the existing OFFICE-STANDARD.md routing contract?**
Not with rule 5 (any-to-any) — the gate does not re-route anything; it adds a
pre-start checkpoint that any-to-any addressing still works around *after*
verdict. It also does not conflict with the standard's own escape hatch
(human/SM override, recorded) — the gate's escape hatch is consistent with it.
The real tensions are (a) the SM becomes a **mandatory serialization point**
for all In-Progress transitions (bottleneck + single point of policy failure),
and (b) the rule binds "any agent" in "every team", but **team agents cannot
see the rule**: instance containers mount only `instances/<team>/crew/` →
`/opt/crew` (which contains `FACTORY-STANDARD.md`, not `OFFICE-STANDARD.md`);
they *can* see `/opt/docs/intent-alignment-gate.md` (instances mount
`../../docs`), so the standard text is discoverable, but the authoritative
golden-rule file is not delivered to the agents it binds until the three
template repos ship it — which the doc's own unchecked checklist admits
(`docs/intent-alignment-gate.md:100–106`).

**Can it deadlock or be used to block legitimate work?**
As written, yes, in one concrete way: **there is no time bound on a blocked
series and no defined path when the customer is absent.** A stop moves tickets
to `Blocked` and waits for the customer to answer 1–3 questions
(`docs/intent-alignment-gate.md:51–58`, `SKILL.md` "Stopping and escalating").
The guardrails (bias to release, no double-gating, human override) prevent
*abuse by the SM*, but none of them prevents a *silent stalemate*: customer on
vacation → series parked in `Blocked` indefinitely, no event, no SLA, no
auto-escalation to the human operator. A gate that can lock forever without a
defined timeout is a deadlock by construction. Secondary gap: rule 11 says
"any agent" — undefined whether the SM gates its **own** Office tickets;
unaddressed, this is either a contradiction (SM must wait for itself) or an
implicit exemption that should be written down.

### BLOCKING

**B1 — The SKILL.md's own commands do not run in the SM container.**
`SKILL.md:47` tells the SM to reconstruct bus history with
`docker exec agent-office-shared-memory redis-cli XREVRANGE office:events + - COUNT 50`
— but the SM service has **no Docker socket**: on `origin/main` only
`factory-control` (compose line 39), `staff-engineer` (line 112) and
`super-devops` (line 173) mount `/var/run/docker.sock`; the SM volumes block
(lines 10–17) has no docker access, and the hermes image need not ship a
docker CLI at all.
`SKILL.md:90` uses `cd ~/agent-office` before `publish-event.py` — no such path
exists in the SM container; hermes home is `/opt/data`, the repo is mounted at
`/opt/repo` (ro), and `crew/` separately at `/opt/crew` (ro).
Both failure modes hit the skill's *core procedure* (step 1 "reconstruct the
intent chain" and step 3 "publish the stop"), so the gate as shipped will fail
at exactly the moments it must work. Concrete fix: replace the docker-exec
line with `python3 /opt/crew/office-log.py --count 50` (one-shot mode exists,
`crew/office-log.py:148–150`; talks TCP to `OFFICE_BUS_URL`, no docker needed —
SM has `OFFICE_BUS_URL=redis://shared-memory:6379`), and use
`python3 /opt/crew/publish-event.py …` (absolute path) instead of
`cd ~/agent-office && python3 crew/publish-event.py`. The
`docs/intent-alignment-gate.md:87–88` invocations only work from a host repo
root; state the container form there too.

**B2 — New stop authority for the Scrum Master with no capability-spec delta.**
`crew/OFFICE-STANDARD.md:37–38` (rule 11) grants the SM the power to stop work
and escalate — a change to the SM's defined role — but
`openspec/specs/agent-roles/spec.md` ("Scrum Master": entry point, status,
blockers) is untouched, and there is no `openspec/changes/` record for this
foundation change. Every comparable foundation change in this repo
(`add-factory-control-service`, `add-spec-team-type`, `add-team-agent-lifecycle`)
carried an OpenSpec change; `foundation-evolution` spec's Discipline section
requires foundation changes to be documented "so future teams inherit the
improvement" — the capability spec *is* the inheritance surface for role
authority. Fix is small: add a one-line delta to the agent-roles SM section
("SHALL be able to stop work and escalate when intent cannot be established —
see OFFICE-STANDARD rule 11 / docs/intent-alignment-gate.md") plus an
`openspec/changes/add-intent-alignment-gate/` record (proposal + delta).

**B3 — No unblock path when the customer is absent; self-gating undefined.**
Per the deadlock analysis above: add to `docs/intent-alignment-gate.md`
(Guardrails or a new "Timeouts" section):
(a) a blocked series is re-escalated to the human operator after a defined
window (e.g. 24 h) with a recommendation and an explicit "proceed or cancel"
question — a stop must never be a parking lot;
(b) state whether the SM's own Office tickets are exempt from the gate (or
self-gated with the verdict recorded) — rule 11's "any agent" currently leaves
this to each session's improvisation.
Neither weakens the gate's purpose (intent, not method); both remove the
indeterminate states.

### Non-blocking notes

**N1 — Delivery gap for team agents (until templates update).** Instances do
not mount the root `crew/`, so `OFFICE-STANDARD.md` (the file containing rule
11) is invisible to team containers; only `/opt/docs/intent-alignment-gate.md`
is visible (instances mount `../../docs`). The doc's unchecked template
checklist (`docs/intent-alignment-gate.md:102–106`) covers this, but it should
be a tracked ticket, not a checklist in a doc, and the interim enforcement
model ("Scrum Master enforces from the Office side") should say *how* the SM
catches un-gated starts (e.g. sweep for `task.started` without a preceding
`work.gate.passed` on the series — that pattern is already queryable on the
bus).

**N2 — New bus events `work.gate.passed` / `work.gate.blocked` are not in the
event catalog.** `message-bus` allows new categories, but the canonical lists
(docs/observability.md, bus event docs) should get these two names so
`office-log.py` consumers and Scrum Master reconstruction know them. Two-line
doc change.

**N3 — `SKILL.md` frontmatter description embeds Russian trigger phrases**
('сверка с целями', 'можно брать в работу', 'проверь соответствие'). If that is
intentional (operator speaks Russian, trigger recall), fine — but the repo's
OFFICE-STANDARD says "Work in English — code, commits, tickets, reports, bus
events, CLI output"; a skill *description* is not a report, so this is a
judgement call. Flagging only for consistency.

**N4 — Rule 11 vs. Linear runtime signalling.** `docs/linear-workflow.md:54`
says task start/finish is signalled by the runtime (completion watcher). If the
watcher moves a ticket to `In Progress` (or the runtime emits `task.started`)
*without* a gate verdict, teams can comply with the runtime and violate rule 11
simultaneously. The gate's trigger should be "before the team *pulls* work into
execution", not "before a status field changes" — one word, avoids a standing
contradiction between two standards.

**N5 — Strengths (so the fixes don't lose the good parts):** verdict taxonomy
with "well-formed ≠ aligned", the stop-requires-questions rule ("a stop with no
questions attached is obstruction"), bias-to-release, do-not-re-gate, goal-line
recorded on the ticket for later drift re-checking, and auditable events — this
is a well-shaped standard. The three blocking items are delivery/mechanics
fixes, not concept rework.

---

*Review committed on `review/architect-pr19-21` (this file). Companion reviews:
`architect-pr19.md`, `architect-pr21.md`. Note: this PR is the base of stacked
PR #21 — see `architect-pr21.md` B1 for merge-order impact.*
