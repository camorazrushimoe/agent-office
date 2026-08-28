# Foundation Sync Plan — Agent Office

**Date:** 2026-08-28
**Authors:** Staff Engineer (executed) + Architect (lead)
**Scope:** Office foundation only (no project work).
**Trigger:** the human suspected the local machine holds factory enhancements
that diverged from GitHub, on top of a stack of open PRs nobody has landed.
This audit verifies that, renders a verdict on every local-only artifact, and
sets the merge order for the open PRs.

## 0. Verified facts (re-checked on the host, not trusted blindly)

- Repo `camorazrushimoe/agent-office`. `main == origin/main == a748498`.
- **No unpushed commits on any local branch.** All local branches equal their
  remotes (`fix/lab-1-crew-send-missing` = PR #21,
  `foundation/intent-alignment-gate` = PR #20).
- The only local-only delta is **untracked** runtime artifacts under
  `agents/*/hermes-home/`. There is **no divergent, committed enhancement**
  hidden on a local branch — the "divergence" the human suspected lives in
  the *untracked runtime state*, not in git history.
- Sibling foundation repos (`lab-crew`, `dev-crew`, `product-factory`) are
  clean: no unpushed commits, zero open PRs.
- Open PRs (all base=main, `mergeable_state=clean`, 0 review comments before
  this audit): #19, #20, #21, #22.

## 1. Delta verdict — every untracked local artifact

| Artifact | Verdict | Rationale |
|---|---|---|
| `agents/*/hermes-home/memories/` (architect + scrum-master `MEMORY.md` + `.lock`) | **IGNORE** | Per-agent runtime memory (local state, like the already-ignored `sessions/`, `state.db`). Not foundation code. → added to `.gitignore`. |
| `agents/architect/hermes-home/verification_evidence.db` | **IGNORE** | Runtime SQLite state (verification events). Nothing in the repo references it. → added to `.gitignore`. |
| `agents/scrum-master/hermes-home/plans/fam-*.py` (11 files) + `fam-linear-ids.json` | **DISCARD** | Dead scaffolding. One-off Linear/bus/door scripts written at runtime for a single research commission (BON-35..39), already executed (the project + tickets exist). The bus + door-dispatch capabilities they exercise are already covered by committed tools (`crew/publish-event.py`, `crew/crew-send.py` — the latter is what PR #21 fixes). Not promoted. → `plans/` added to `.gitignore`. See F1 for the real gap it exposes. |
| `agents/scrum-master/hermes-home/sweep-report.md` | **IGNORE** | One-time output of the committed `scrum-sweep` skill (a runtime report). → added to `.gitignore`. Note: written in Russian (see F3). |
| `agents/architect/hermes-home/skills/` (6.6 MB bundle) | **IGNORE** | Upstream Hermes default skill library (apple, creative, devops, email, github, mlops, …), runtime-mounted into the agent's home. **Not Office-authored foundation** — it exists nowhere in the repo and is not a "divergence." The foundation skill set is the already-committed curated `agents/<role>/skills/` (code-review, tdd, git-branch-discipline, prototype, research, …). Already gitignored by design; no action needed. |

**Net:** nothing from the untracked delta deserves *code* promotion. The
local-only delta is runtime state + one-off scaffolding, not a hidden
enhancement. The durable output of this audit is (a) the `.gitignore` hygiene
that keeps the tree clean, and (b) this plan (merge order + follow-ups).

### The `fam-*.py` cluster — the interesting case

The cluster is **DISCARD (dead scaffolding)**, not a promotion, because:

1. It is already executed — the Linear project + tickets (BON-35..39) exist
   (confirmed by `fam-linear-ids.json` and the SM's runtime memory).
2. It duplicates committed tools: bus publish = `crew/publish-event.py`; door
   dispatch = `crew/crew-send.py` (the canonical client that PR #21 fixes for
   lab-1).
3. The one genuinely new capability — *generic* Linear project + ticket
   creation — is hardcoded to this one commission and is not a reusable
   Office tool.

It **dies** as written, but it exposes a real gap (F1) that should become a
proper foundation tool in a follow-up — not a one-off script.

### The local-only architect skills bundle — is any of it foundation?

No. The 6.6 MB bundle is the upstream Hermes default skill library,
runtime-mounted into `hermes-home/skills/`. It is not Office-authored, it
exists nowhere in the repo, and it is already gitignored by design. The
Office's foundation skill set is the small, curated
`agents/<role>/skills/` directory that is already committed. Nothing in the
bundle is promoted.

## 2. Merge order — #19, #20, #21, #22 + this PR

**Recommended sequence:**

1. **#19 `spec/office-mcp`** — **GO**
2. **this PR `foundation/foundation-sync-audit`** — **GO**
3. **#22 `review/architect-pr19-21`** — **GO**
4. **#20 `foundation/intent-alignment-gate`** — **NEEDS-CHANGE → GO after fixes**
5. **#21 `fix/lab-1-crew-send-missing`** — **NEEDS-CHANGE → GO after #20**

**Rationale + conflict risk (per PR):**

- **#19 (spec: Office MCP facade)** — **GO.** Architect-approved (0 blocking).
  Spec only (no code): `openspec/`, `docs/office-mcp.md`, `README.md`.
  **No file overlap** with #20/#21/#22 or this PR → **zero conflict risk.**
  Merge first: it is the lead, independent, and its follow-up implementation
  PR will build on it. Carry the Architect's notes N1–N6 into the
  *implementation* PR, not this spec PR.

- **this PR (`foundation/foundation-sync-audit`)** — **GO.** `.gitignore`
  hygiene + this plan doc. **No file overlap** with any open PR → **zero
  conflict risk.** Land early so the merge-order plan is on `main` as the
  durable reference for the rest of the sequence.

- **#22 (review: architect's adversarial review of #19-21)** — **GO.**
  Additive review documentation (3 new files under `instances/reviews/`).
  **No file overlap** → **zero conflict risk.** It is the durable record of
  the Architect's verdicts; land it so the fixers of #20/#21 have the review
  reference on `main`.

- **#20 (foundation: intent alignment gate)** — **NEEDS-CHANGE.** Three
  blocking findings (Architect's `instances/reviews/architect-pr20.md`):
  - **B1** — the skill's own commands do not run in the SM container.
    **Independently verified:** the `scrum-master` compose service mounts no
    `docker.sock` (only `factory-control`, `staff-engineer`, `super-devops`
    do), so `docker exec … redis-cli XREVRANGE` cannot run there. Fix:
    `python3 /opt/crew/office-log.py --count 50` (TCP, no docker) and
    `python3 /opt/crew/publish-event.py` (absolute path).
  - **B2** — the new SM stop-authority has no capability-spec delta
    (`openspec/specs/agent-roles/spec.md` untouched; no `openspec/changes/`
    record).
  - **B3** — no unblock path when the customer is absent (a stop can park
    indefinitely) + self-gating undefined.
  **Conflict risk:** none with #19/#22/this PR. **But it is the base of #21
  (stacked)** → it **must merge before #21** (see #21).

- **#21 (fix: lab-1 crew-send never mounted)** — **NEEDS-CHANGE**, and it is
  **stacked on #20.** Verified: `#20 is an ancestor of #21`;
  `git diff --stat pr20..pr21` = `instances/lab-1/crew/crew-send.py` (+79)
  only; the other 3 files are **byte-identical** in both branches. Two
  blocking findings (Architect's `instances/reviews/architect-pr21.md`):
  - **B1** — merge-order coupling: #21 **must not** merge before #20 (it
    would silently land the intent-alignment gate). **Order #20 → #21 is
    mandatory.**
  - **B2** — the committed file is a **divergent, weaker copy** of the door
    client (the lab-crew variant), not the canonical `crew/crew-send.py`. It
    lacks the missing-registry guard (unhandled `FileNotFoundError`) and
    already differs (docstring, no `from __future__ import annotations`,
    unsorted agent listing, 15 s vs 30 s timeout). The durable fix is a
    **shared read-only mount** of the canonical client (or, at minimum before
    merge, adopt the guard + a header pinning the file to
    `crew/crew-send.py`).
  **Conflict risk:** byte-identical overlap with #20's 3 files. If #20 merges
  first, #21's diff collapses to the single `crew-send.py` (no conflict); if
  #21 merges first, it silently lands the gate (process violation). Hence
  **#20 → #21**.

**Conflict matrix (file overlap):**

| PR | files | overlaps with |
|---|---|---|
| #19 | `README.md`, `openspec/`, `docs/office-mcp.md` | none |
| this PR | `.gitignore`, `docs/foundation-sync-plan.md` | none |
| #22 | `instances/reviews/architect-pr{19,20,21}.md` (3 new) | none |
| #20 | `crew/OFFICE-STANDARD.md`, `docs/intent-alignment-gate.md`, SM `skills/intent-alignment-gate/SKILL.md` | #21 (same 3 files) |
| #21 | #20's 3 files + `instances/lab-1/crew/crew-send.py` | #20 (same 3 files, byte-identical) |

Only #20 ↔ #21 overlap (by stacking). Everything else is independent.

## 3. Follow-up findings (tracked, not fixed in this PR)

- **F1 — Linear tool gap.** No committed, generic Office tool for Linear
  project + ticket creation; `fam-linear-create.py` is a one-off prototype.
  Recommend a foundation ticket: promote to a real tool (e.g.
  `crew/linear-create.py` / `office/linear.py`) **and** document the Linear
  API quirks the SM recorded at runtime: `projectCreate` description
  ≤ 255 chars; `Project` has no `identifier` field; `IssueUpdateInput` has no
  `blockedByIssueIds` (blocking edges go in the ticket body).
- **F2 — factory-dashboard skill is unreliable.** The SM already recorded an
  `audit.finding` on the bus: the skill's container-name list is stale
  (reported 0 running / 16 sleeping while 9 containers were up). Suggested
  owner: Architect + Staff Engineer. Verify container state via bus events or
  a door TCP probe until fixed. Not yet ticketed.
- **F3 — Russian-language sweep report.** `sweep-report.md` (and the
  `scrum-sweep` output) is in Russian, against the Office standard "Work in
  English." Minor; fix in the `scrum-sweep` skill.
- **F4 — door-client unification (#21 B2 follow-up).** After #21, reconcile
  the three divergent `crew-send.py` copies (office, lab-crew, dev-crew) to
  one canonical client + shared read-only mount, and apply to dev-1/spec-1
  (same latent gap). Track one ticket.

## 4. Cross-review record

- Architect's adversarial review of #19/#20/#21: PR #22
  (`instances/reviews/architect-pr{19,20,21}.md`).
- Staff Engineer ↔ Architect cross-review of this PR and the merge order: see
  the PR review comments on this PR and #22 (posted as `COMMENT` events, since
  the shared GitHub token is the PR author).
- **Nothing is merged by this plan.** The human approves the sequence.
