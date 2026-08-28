# Adversarial Architecture Review — PR #19 (spec: Office MCP facade)

> ## STATUS STAMP (Architect, 2026-08-28)
>
> Merged to main as `5586974` (base of PR #20's rebase). The approval verdict
> and its verified facts stand; nothing in the #20 fix pass (B1–B3) touches or
> contradicts the office-mcp spec. Non-blocking notes N1–N3 remain carried
> into the implementation PR as recorded below.

**Branch:** `spec/office-mcp` @ `e1b5ac6` (base `origin/main` @ `a748498`)
**Scope:** +454/−8 in 7 files — `openspec/changes/add-office-mcp/` (proposal, design, tasks, delta), `openspec/specs/office-mcp/spec.md`, `docs/office-mcp.md`, `README.md`
**Reviewer:** Architect · 2026-08-27 18:20 UTC · read-only review (single pass)
**Tracks:** issue #18

---

## VERDICT: **approve** (0 blocking)

The spec is internally coherent, implementable as written, contradicts no existing
capability, and its always-on / reserved-port decisions are consistent with
`docker-compose.yml` and the `agent-lifecycle` spec. The notes below are
implementation-PR concerns the spec should carry into the follow-up.

### Verified facts (checked against `origin/main`)

- **All wrapped sources of truth exist:** `config/team-registry.yaml`,
  `office/registry/factory-agents.json`, `registry/doors.json`,
  `office/manage_tokens.py`, `scripts/smoke.py`, `crew/crew-send.py`.
  (`tokens/tokens.yaml` / `crew/agents.json` are intentionally gitignored — the
  spec's "operators write tokens/tokens.yaml" is consistent with `.gitignore`.)
- **Lead-role map is correct against the live registry:** dev→`tech-pm`
  (dev-1), lab→`research-lead` (lab-1), spec→`technical-product-manager`
  (spec-1) — all three leads exist in `config/team-registry.yaml`.
- **Port 8760 is free.** Used host ports on main: 6380 (Redis), 8751–8754
  (Office agents), 8661–8664 (dev-1), 8671–8673 (lab-1), 8681–8684 (spec-1).
  No compose file, spec, or doc claims 8760 today; the README marks it
  "(spec, not running yet)" — honest reservation, no service added.
- **Always-on class is consistent.** `agent-lifecycle` spec ("Always-on vs
  ephemeral") requires shared infra + lifecycle controllers to stay always-on;
  the spec puts MCP in the same class as `factory-control` and defers the
  compose service to the implementation PR, exactly as `tasks.md` splits it.
  No compose/lifecycle change is required for *this* PR, so there is nothing
  to contradict today.
- **No capability conflicts:** "facade, not a second bus" + "MUST NOT expose raw
  Redis publish / door HMAC secrets / Docker API" satisfies `message-bus`
  (single bus) and `composition` (separation of evolution); two-phase
  `plan_onboard`/`apply_onboard` matches `team-onboarding` (registry + smoke
  before admission) and is the natural implementation of `composition`'s
  "declare a composition … spawn instances from pinned template refs".
  `addressing`/`send`/`wake` semantics match `agent-lifecycle` "Wake on demand"
  (wake → wait healthy → deliver; wake failure is a send failure, not a drop).

### Non-blocking notes

**N1 — "wake-aware send" is claimed as an existing source of truth but half of
it does not exist in code.** `spec.md:28` lists "wake-aware send (`crew-send` +
factory-control)" among the sources MCP wraps, and `design.md` says "wake-aware
send (crew-send + factory-control)". Reality on main: `factory-control`
subscribes `agent.wake` envelopes and wakes (correct), but `crew/crew-send.py`
contains **no** wake code — no `--wake` flag, no `send_wake` call. `send_wake()`
exists only as a library function in `office/bus/client.py:340`.
`docs/office-mcp.md`'s step list is fine, but the spec should say the
implementation PR must *add* the wake-publish step to the send path (which
`tasks.md` in fact says: "Wire send through existing wake-aware door path" —
that path does not exist yet; the wording should be "through the wake-aware
path **built per `agent-lifecycle`**"). As written, the implementer may assume
something exists that doesn't.

**N2 — `wait_for` "first matching event" is underspecified.** `spec.md:111`
allows MCP to "attach the first matching bus event" with examples
(`agent.started`, inbound ack, `task.started`, …). No door currently publishes a
receipt event carrying the envelope's `message_id` (Hermes webhook door returns
202 in-band; `make_envelope` ids are uuid4 and never echoed back on the bus).
So "matching" can only mean "first event from the target actor in a
client-chosen category after send" — which will happily match an *unrelated*
`agent.started`. Implementable, but the implementation PR must define the
matching rule (or add a door receipt event `message.received` with
`message_id`). Flagging so the contract isn't loosened by ambiguity.

**N3 — `apply_onboard` vs. a one-shot registry in `factory-control`.**
`office/lifecycle/factory_control.py:247` loads
`office/registry/factory-agents.json` **once at startup** and never reloads it.
`apply_onboard` creates new instances/agents (spec.md:130–137) — those agents
would be invisible to the idle reaper and the wake listener until
`factory-control` restarts. The spec's "wake-aware send" promise (spec.md:115)
and "foundation smoke for the new teams" (spec.md:137) are only true for
onboarded teams if the implementation adds registry hot-reload (or an explicit
restart) to `apply_onboard`. Add a line to the spec's Onboarding section:
"apply_onboard SHALL make new agents visible to the lifecycle controller
(reload or restart) as part of success."

**N4 — `apply_onboard` is the riskiest tool in v1; consider a confirm step.**
It makes the factory self-replicate from an external MCP client call: clone
pinned template refs, allocate names/ports, write compose, derive tokens,
register, start containers. The guardrails present (readiness must be green,
`plan_expired` on registry/port drift, `secret_refused`, `conflict`, two-phase)
are good. Suggestion for the implementation spec: `apply_onboard` takes an
explicit `confirm` token returned by `plan_onboard` (binds the mutation to a
fresh plan) — cheap insurance against a stale-plan race.

**N5 — OpenSpec delta file deviates from house convention (cosmetic).**
`openspec/changes/add-office-mcp/specs/office-mcp/spec.md` is a 3-line pointer
("See `openspec/specs/office-mcp/spec.md` (same text)"). Existing changes
(`add-factory-control-service`, `add-spec-team-type`) carry real
`## ADDED/MODIFIED Requirements` deltas. Either way is locally defensible (no
`openspec/changes/archive/` exists; all completed changes stay in place), but
make the delta say `## ADDED Requirements: new capability, full text at
openspec/specs/office-mcp/spec.md` so the change record is self-describing.

**N6 — README flow diagram: PR #19 breaks the box drawing.** The PR re-drew the
pipeline diagram's top and bottom borders shorter but left the middle rows
unchanged (README.md:26–29):

```
main :  top  ┌…┐ @ col 38–57 / 78–92   side walls @ 38,58 / 79,93   bottom └┬┘ @ 38–57 / 78–92  (consistent)
pr-19:  top  ┌…┐ @ col 38–56 / 77–90   side walls @ 38,58 / 79,93 (unchanged)  bottom └…┘ @ 38–56 / 77–84
```

In pr-19 the Spec box top border ends 2 cols short of its right wall (56 vs 58)
and the Dev box bottom border ends at col 84 while the box still spans to 90 —
the "Dev team" box is no longer a box, and the `│ PR → review → merge → deploy`
drop line now hangs under a floating border. The diagram did not need touching
for this PR at all; restore the original border rows (keep only the text edits
in "Core idea", which are fine).

### Answers to the requested questions

1. **Internally coherent and implementable as written?** Yes, with the three
   implementation-prerequisites above (N1 wake path, N2 wait matching, N3
   registry reload) that the follow-up PR must own. The spec's own scope split
   (spec now, service later) is clean and matches `tasks.md`.
2. **Contradicts any existing capability in `openspec/specs/`?** No. Checked
   against `agent-lifecycle`, `message-bus`, `team-onboarding`, `composition`,
   `agent-roles`, `observability`. It *extends* (facade over) rather than
   redefines; the "SHALL NOT" list correctly keeps bus/Linear/GitHub ownership
   where the existing specs put it.
3. **Reserved port / always-on consistent with `docker-compose.yml` and
   `office/lifecycle`?** Yes. 8760 is free and reserved-in-README-only (no
   compose service in this PR, as the PR states). Always-on +
   `restart: unless-stopped` + depends-on-healthy-bus is the same lifecycle
   class as `factory-control` and is exactly what `agent-lifecycle` mandates
   for shared infrastructure. `office/lifecycle/` code is untouched, so nothing
   to reconcile today.

---

*Review committed on `review/architect-pr19-21` (this file). Companion reviews:
`architect-pr20.md`, `architect-pr21.md`.*
