# Foundation Sync Audit — Delta Verdict + Merge Order

> **Status:** Round 1 **FINAL** — staff-engineer executed R1 (commit `30a675e`);
> **Architect has now finalized/overridden the verdict** (this commit). Where a
> call changed from the Scrum Master pre-verdict, **both positions are kept
> visible** below — disagreements are never averaged.
>
> **Scope (foundation only):** `.gitignore`, this `docs/` file, the sync-audit
> PR, and PR comments on #19/#20/#21/#22. **Nothing is merged here.** The human
> approves merges. No team/project work, no lab/spec/dev tickets, no Linear
> changes.

---

## 0. Verified baseline (git evidence, 2026-08-28)

Repo `camorazrushimoe/agent-office`. `origin/main == a748498` (no unpushed
commits). All four open PR branches are **direct children of `a748498`**
(`git merge-base origin/main <branch>` returns `a748498` for each):

| PR | Branch | Head SHA | Files vs main |
|----|--------|----------|---------------|
| #19 | `spec/office-mcp` | `e1b5ac6` | 7 (README, docs/office-mcp.md, openspec/*) |
| #20 | `foundation/intent-alignment-gate` | `02b0719` | 3 |
| #21 | `fix/lab-1-crew-send-missing` | `84654c0` | 4 (includes all of #20 — see below) |
| #22 | `review/architect-pr19-21` | `c225d70` | 3 (instances/reviews/*.md) |

**Stacking verified (not vibes):** `git merge-base --is-ancestor 02b0719
84654c0` → **YES**. `02b0719` (#20 head) is the **direct parent** of `84654c0`
(#21 head). So #21's diff vs `main` carries all of #20's 3 files; #21's own
payload is exactly **1 commit / 1 file** (`instances/lab-1/crew/crew-send.py`,
+79). Confirmed by `git log 02b0719..84654c0` (one commit) and
`git diff 02b0719..84654c0` (one file).

**Review state (GitHub API, 2026-08-28):** the brief's "ZERO review comments
so far" is **FALSE**. #19/#20/#21 each carry **3 comment-reviews** (architect
adversarial review + architect verdict + grok triage); #22 carries **1**
(grok triage re-check). Both positions are reported here; do not rely on the
"zero" claim for merge sequencing.

`mergeable_state` for all four: **clean** at snapshot time.

---

## 1. Delta verdict (local vs GitHub)

The human's suspicion: the local machine holds factory enhancements diverged
from GitHub. Inventory = 11 `fam-*.py` one-shot scripts (Scrum Master,
2026-08-27 15:19–15:22 UTC, during Federated Agent Memory intake; run from the
SM container where `/opt/repo` is ro-mounted; **nothing committed**), plus other
untracked runtime artifacts.

**Architect inventory correction (R1 final):** the plans dir also holds a
**12th file**, `audit-r1-dispatch.py` (SM, 2026-08-28 07:55 UTC) — this audit's
own Round-1 bus-event + HMAC dispatch one-shot, not part of the FAM intake.
Same class, same verdict (DISCARD). The cluster is therefore 12 executed
one-shots, all already run; the durable state they produced lives in Linear
(project `3bbdb9fe…`, BON-35..39) and on the bus, not in any file.

Verdicts below start from the **Scrum Master pre-verdict**. Column "Changed?"
marks any deviation (none — architect **confirms** all SM calls; see §4 for the
independent verification).

### 1a. The `fam-*` cluster (11 files, `agents/scrum-master/hermes-home/plans/`)

| # | File | Verdict | One-line reason |
|---|------|---------|-----------------|
| 1 | `fam-check.py` | **DISCARD** | One-shot Linear diagnostic (list projects/issues, dup guard) — already ran 2026-08-27. |
| 2 | `fam-introspect.py` | **DISCARD** | One-shot GraphQL introspection; the discovered quirk ("no `blockedByIssueIds` field") is already in `MEMORY.md`. |
| 3 | `fam-probe-projectcreate.py` | **DISCARD** | One-shot probe of `projectCreate` limits — already ran. |
| 4 | `fam-probe2.py` | **DISCARD** | One-shot description-length A/B/C probe; deleted its own probe projects. |
| 5 | `fam-probe3.py` | **DISCARD** | One-shot raw-error probe of `projectCreate`. |
| 6 | `fam-linear-create.py` | **DISCARD** | The one-shot payload that created project `3bbdb9fe` + BON-35..39 + blockedBy edges; already executed. |
| 7 | `fam-save-ids.py` | **DISCARD** | One-shot writer of the id map to `plans/fam-linear-ids.json`. |
| 8 | `fam-linear-ids.json` | **DISCARD** | Runtime state (project + 5 ticket ids/urls); durable record lives in Linear itself. |
| 9 | `fam-verify.py` | **DISCARD** | One-shot post-creation existence check. |
| 10 | `fam-bus-events.py` | **DISCARD** | One-shot publisher of the 4 intake bus envelopes via a hand-rolled RESP2 XADD client; the durable pattern is the committed office bus tooling, not this raw client. |
| 11 | `fam-dispatch.py` | **DISCARD** | One-shot HMAC dispatcher to lab-1 doors; the durable pattern is the committed `crew/crew-send.py` — a raw one-shot would duplicate it. |
| 12 | `audit-r1-dispatch.py` | **DISCARD** | *(architect addition, not in the SM inventory)* This audit's own R1 one-shot: bus event `audit.foundation_sync.started` + HMAC dispatch of the R1 brief to the architect/staff-engineer doors. Executed 2026-08-28; same class. |

**Cluster rationale (SM pre-verdict, **CONFIRMED by architect R1 final**):**
these are one-shot intake/audit scripts that already ran. The durable pattern is
`parse_tokens(TOKENS_FILE) -> stdlib urllib GraphQL`, which is documented in
Scrum Master memory; promoting the raw one-shots would **duplicate** that
pattern. The reusable facts (Linear API quirks) already live in memory.
**No fam file is promoted.**

**What survives from the cluster — as docs, not code** (architect R1 final):
the SM's pre-verdict correctly located the lasting value in *facts and pattern*,
not script. That value belongs in the repo (durable, agent-agnostic), not only
in one agent's memory (wipeable), so it is recorded here:

- **Linear intake pattern:** resolve the key via
  `parse_tokens(TOKENS_FILE)` (`/opt/repo/office/credentials.py`) → stdlib
  `urllib` GraphQL against `https://api.linear.app/graphql`. Pass all text as
  variables; filter client-side (the API is finicky with inlined text).
- **Linear API quirks (measured 2026-08-27):** `projectCreate` description is
  capped at 255 chars; `Project` has no identifier field (use `name`);
  `IssueUpdateInput` has **no `blockedByIssueIds`** field — dependency edges
  must go in ticket bodies / relations, not in the update mutation.
- **Idempotent-create pattern** (from `fam-linear-create.py`): list by exact
  name → reuse-or-create → delete accidental duplicates → verify before
  create → write id map → verify after. If a real Office Linear tool is ever
  commissioned, it starts from this note — it is not commissioned by this PR.

### 1b. Other untracked artifacts

| Artifact | Verdict | One-line reason | Changed? |
|----------|---------|-----------------|----------|
| `agents/*/hermes-home/memories/` (SM + architect) | **IGNORE** (gitignore) | Per-agent live runtime memory; regrows every session. Repo convention commits SOUL/config.template/skills, not runtime state. | No |
| `agents/scrum-master/hermes-home/sweep-report.md` | **IGNORE** (gitignore) | Dated (25 Aug) output of the tracked `scrum-sweep` skill; regenerable. | No |
| `agents/architect/hermes-home/verification_evidence.db` | **IGNORE** (gitignore) | Runtime sqlite state; same class as already-ignored `response_store.db*`/`state.db*`. | No |
| `agents/*/hermes-home/plans/` (the dir) | **IGNORE-BY-VISIBILITY** (do **not** gitignore) — **ruling: Position A confirmed (architect R1 final)** | A recurring untracked `plans/` dir is a **signal** the next audit should see, not noise. Residual cost: `git status` noise in the SM/architect home while one-shots accumulate. See §1c for the dissenter. | Confirmed A (was "open") |
| `agents/*/hermes-home/skills/` (architect **bundle**) | **IGNORE** (already gitignored, line `agents/*/hermes-home/skills/`) | Vendor-origin bundled skills (`airtable`, `apple-*`, `claude-code`, `codebase-inspection`, `github-*`, `hermes-agent`, `notion`, `obsidian`, … ~13 categories) with a `.bundled_manifest`. **Not** factory-authored foundation. **Do not promote anything from the bundle.** | No |

> **Do not confuse the two "skills" trees.** The **repo's curated foundation
> skills** are at `agents/<role>/skills/` (**tracked**, e.g.
> `agents/architect/skills/code-review`,
> `agents/scrum-master/skills/{scrum-sweep,intent-alignment-gate}`). The
> **bundle** is at `agents/<role>/hermes-home/skills/` (vendor-origin,
> **ignored by design**). The existing `.gitignore` line
> `agents/*/hermes-home/skills/` already covers the bundle — verified with
> `git check-ignore`.

### 1c. `plans/` visibility — ruling + dissenter (kept visible, not averaged)

**Two positions:**

- **Position A (SM pre-verdict):** do **not** gitignore
  `agents/*/hermes-home/plans/`. Keep it visible/untracked so the next sync
  audit *sees the recurrence*. A recurring untracked dir is a **signal**, not
  noise.
- **Position B (dissenter):** gitignore `plans/` like `kanban*` — it is
  per-agent runtime working space, and leaving it untracked keeps polluting
  `git status`. **Position B was the choice actually shipped in the SE's
  duplicate PR #24** (`foundation/foundation-sync-audit`, commit `77af6a2`),
  which gitignored `plans/`. #24 was closed by the architect as a duplicate —
  see §4b — so Position B is recorded here as the dissenter, not silently
  dropped.

**Architect ruling (R1 final): Position A — `plans/` stays visible.**
Reasoning:

1. **Signal value is real and just fired.** This very audit discovered its
   inventory was wrong *because* `plans/` was visible (the 12th file,
   `audit-r1-dispatch.py`, was missing from the SM's 11-file inventory). An
   ignored dir would have hidden that class of recurrence — exactly the
   "divergence nobody sees" the human suspected at the top level.
2. **The content policy is independent of the visibility policy.** DISCARD
   means "delete the executed one-shots at next housekeeping", not "hide them
   from git". Even if every one-shot dies, a *recurring* `plans/` appearing
   again is the audit's tripwire.
3. **Cost is bounded and cheap.** The noise is one untracked line per role
   home that has plans; `git status` already carries the rest of the
   hermes-home runtime state that *is* ignored (so the practical noise is
   minimal — only non-ignored items surface, i.e. `plans/` and a handful of
   files §1b covers).
4. **Escape hatch is one line.** If the recurrence proves noisier than
   useful (e.g. plans/ accumulates megabytes of scratch), the next audit
   flips to Position B with a one-line `.gitignore` addition — the flip is
   cheap in both directions, so the default should be the one that maximizes
   signal.

This is a **genuine, recorded disagreement**, not a rubber stamp: Position B
remains a defensible call, and it is preserved here with its provenance.

### 1d. Consequence

The sync-audit PR is **"docs + .gitignore only"**, with the honest line: **no
local artifact deserves promotion.** That is a valid result; padding is not.

---

## 2. Merge order

### 2a. Sequence (R1 seed)

```
#19  spec/office-mcp                       →  GO          (first)
#23  foundation/sync-audit-r1  (this PR)    →  GO          (second)
#20  foundation/intent-alignment-gate      →  NEEDS-CHANGES (after its 3 blocking fixes)
#21  fix/lab-1-crew-send-missing           →  NEEDS-CHANGES (after rebase onto fresh main + client fix)
#22  review/architect-pr19-21              →  GO (records) (last)
```

### 2b. Rationale

1. **#19 first.** Only open PR the architect has **APPROVE**d (0 blocking, 6
   non-blocking N1–N6; grok triage "merge"). Self-contained (README,
   docs/office-mcp.md, openspec/*). Merging it clears the cleanest win and
   moves `main` forward so the stacked work re-bases against less.
2. **#23 (this PR) second.** Docs + `.gitignore` only, **zero code**, no
   dependency on any other branch. Merging it early (a) lands the
   delta-verdict doc as the **shared reference** for the subsequent #20/#21
   reviews, and (b) stops runtime state from polluting `git status` while the
   remaining PRs are in flight. It touches only `.gitignore` +
   `docs/foundation-sync-plan.md` — no other open PR touches either file, so
   it cannot conflict.
3. **#20 third (after its 3 blocking fixes).** Architect **NEEDS-CHANGES**
   (B1 skill commands won't run in the SM container — no `docker.sock` / no
   `~/agent-office`, should use `/opt/crew/office-log.py` +
   `publish-event.py`; B2 `openspec/specs/agent-roles` not updated for the new
   SM authority; B3 no timeout/escalation path when the customer is absent,
   undefined whether SM gates its own tickets). It is the **base of the #21
   stack**, so it must land before #21.
4. **#21 fourth (after rebase onto fresh main + client fix).** #21 is
   **STACKED on #20** (verified §0). Its two blocking issues: (i) it is
   stacked — its diff vs `main` includes all of #20, so it must be **rebased
   onto the post-#20 `main`** so its true payload (1 file, +79) is what gets
   reviewed/merged; (ii) the shipped `instances/lab-1/crew/crew-send.py` is the
   **weaker lab-crew variant**, not the office one — no missing-registry guard,
   15 s vs 30 s timeout. **Durable fix = the canonical office client
   (`crew/crew-send.py`) + ro-mount**, not a second divergent client.
5. **#22 last.** Pure **review records** (`instances/reviews/architect-pr{19,20,21}.md`).
   It documents the reviews of #19/#20/#21, so it is natural to land it
   **after** those PRs resolve. Low risk (verbatim records of the architect's
   own reviews); its only review is a grok triage re-check. Merging it last is
   **organizational**, not a correctness blocker.

### 2c. Conflict risk (verified with git, not vibes)

File-set per PR (after #21 rebase), from `git diff --name-only main...branch`:

- #19: `README.md`, `docs/office-mcp.md`, `openspec/changes/add-office-mcp/*`, `openspec/specs/office-mcp/spec.md`
- #23: `.gitignore`, `docs/foundation-sync-plan.md`
- #20: `agents/scrum-master/skills/intent-alignment-gate/SKILL.md`, `crew/OFFICE-STANDARD.md`, `docs/intent-alignment-gate.md`
- #21 (rebased): `instances/lab-1/crew/crew-send.py`
- #22: `instances/reviews/architect-pr19.md`, `architect-pr20.md`, `architect-pr21.md`

**No file is touched by more than one PR** in the post-rebase file-sets.
`.gitignore` is touched **only by #23**. Therefore **static conflict risk is
zero** for any merge order; the only *ordering* constraints are the
**stacking dependency** (#21 ⇒ #20) and the **records semantics** (#22 last).

**Simulation (actual git, `git 2.47.3`):** in a throwaway worktree,
`git checkout -B sim/main origin/main` then, in order,
`git merge --no-ff --no-edit` of `#19`, `#23`, `#20` (its current branch as
proxy for the post-fix #20), then `git rebase sim/main` of `#21` (leaves
exactly **1 commit**, 1 file, no conflicts), then merge rebased `#21`, then
merge `#22`. **All six operations exited 0 with zero conflicts.** Final graph
is a clean linear-of-merges off `a748498`.

> **Caveat:** #20 and #21 were simulated with their **current** branches as
> proxies. The *fixed* #20/#21 (post blocking-fixes) may add/modify files, so
> re-run this simulation against the real fixed branches in R2 before merge.
> The structural conclusion (no overlapping file-sets, #21 rebases to 1
> commit) is expected to hold unless the fixes touch a file another PR owns.

### 2d. Per-PR go / no-go

| PR | Verdict | Gate to flip to GO |
|----|---------|--------------------|
| #19 | **GO** | — (architect APPROVE, 0 blocking). Optional: address non-blocking N1–N6. |
| #23 | **GO** | — (this PR; docs + .gitignore only). |
| #20 | **NEEDS-CHANGES** | Fix **B1** (SM-container-runnable commands via `/opt/crew/office-log.py` + `publish-event.py`), **B2** (update `openspec/specs/agent-roles`), **B3** (timeout/escalation when customer absent; define whether SM gates its own tickets). |
| #21 | **NEEDS-CHANGES** | **Rebase** onto post-#20 `main` (removes the #20 payload from the diff), and ship the **canonical office client + ro-mount** (not the weaker lab-crew variant). |
| #22 | **GO (records, merge last)** | None (records only). Note: sole review is a grok triage re-check; low risk. Merge after #19/#20/#21 resolve. |

---

## 3. Out of scope (explicit)

- **No merges.** The human approves merges. No self-merge.
- **No promotion** of any `fam-*` script or any bundled-skill content.
- **No team/project work**, no lab/spec/dev tickets, **no Linear changes**.
- The `plans/` visibility call (§1c) is **ruled** (Position A) in this
  finalization; the dissenting Position B is preserved in §1c.

---

## 4. Architect independent verification + PR #24 disposition (R1 final)

### 4a. Facts re-verified independently (not trusted from the brief)

Every "WHAT I ALREADY KNOW" fact in the SM brief was re-checked by the
architect on 2026-08-28 against `origin` and the GitHub API:

| Fact (brief) | Architect verification | Result |
|---|---|---|
| `main == origin/main == a748498`, no unpushed commits | `git rev-parse origin/main` + API `/commits/main` | **CONFIRMED** (`a748498d…`) |
| PR heads/sha's/base/mergeable_state | API `/pulls` for #19–#22 | **CONFIRMED** (e1b5ac6 / 02b0719 / 84654c0 / c225d70; all base `main`, `mergeable_state=clean` at snapshot) |
| `#21` stacked on `#20` | `git merge-base --is-ancestor 02b0719 84654c0` → **YES**; `git log 02b0719..84654c0` = 1 commit; `git diff 02b0719 84654c0 --name-only` = `instances/lab-1/crew/crew-send.py` only; the 3 shared files are **byte-identical** across the two branch tips | **CONFIRMED** (direct parent; #21 true payload = 1 file, +79) |
| Per-PR file sets / no overlap | `git diff --name-only origin/main...origin/<branch>` for each | **CONFIRMED** — only #20↔#21 overlap (via stacking); post-rebase, no file is touched by more than one PR |
| Reviews: "zero review comments" is FALSE | API `/pulls/N/reviews`: #19/#20/#21 = 3 comment-reviews each (architect adversarial + architect verdict + grok triage); #22 = 1 (grok triage) | **CONFIRMED** (all posted as `COMMENT` events — GitHub rejects APPROVE/REQUEST_CHANGES on a PR from its own author; both positions are reported per §0) |
| Office `crew/crew-send.py` has the registry guard + 30 s timeout | `grep` on `origin/main:crew/crew-send.py` (`sys.exit("Missing …")`; `timeout=30`) | **CONFIRMED** |
| #21's shipped `instances/lab-1/crew/crew-send.py` is the weaker variant | `origin/fix/lab-1-crew-send-missing` version: `timeout=15`, **no** missing-registry guard (`open()` unguarded → raw `FileNotFoundError`), no `from __future__ import annotations`, lab-crew docstring; 69-line diff vs the office client | **CONFIRMED** — #21's second blocking finding is real |
| `.gitignore` already covers `hermes-home/skills/` (the bundle) | `git check-ignore` on a fabricated `agents/architect/hermes-home/skills/github/skill.md` → ignored | **CONFIRMED** — the vendor bundle stays ignored by design; nothing from it promoted |
| New `.gitignore` patterns work (PR #23, R1 commit) | Worktree test on `30a675e`: fabricated `memories/MEMORY.md`, `sweep-report.md`, `verification_evidence.db` → all **IGNORED**; fabricated `plans/fam-check.py` + `plans/audit-r1-dispatch.py` → both **VISIBLE** (Position A behaving as intended) | **CONFIRMED** — exact paths on disk match the patterns |
| No `*sync*`/`*audit*` branch pre-existed; next PR number 23 | branch list at start of round: none matched; first free number was 23 | **CONFIRMED at R1 start** (see §4b for what followed) |

### 4b. The duplicate PR #24 (process note — recorded, not averaged)

**Two PRs were opened for this audit in the same round:**

- **PR #23** `foundation/sync-audit-r1` @ `30a675e` (opened 08:05 UTC) — the
  brief-mandated branch and number. Content: this doc (Position A for
  `plans/`) + `.gitignore` (memories/, sweep-report.md,
  verification_evidence.db).
- **PR #24** `foundation/foundation-sync-audit` @ `77af6a2` (opened 08:13 UTC)
  — a second, parallel branch by staff-engineer with a differently-worded
  version of this doc. It **gitignored `plans/`** (Position B), and its
  baseline text states "0 review comments before this audit" — which is
  **false per the API** (§4a: the reviews pre-existed the audit).

**Disposition (architect, as lead):** **PR #23 is the canonical sync-audit PR**
— it is the branch/number the brief specified, and its `.gitignore` implements
the §1c ruling (Position A). **PR #24 is closed as a duplicate**: it is
functionally a subset/superset-mix of #23 whose two deltas (gitignore `plans/`;
"0 review comments" baseline) are both contradicted by the verified state and
the ruling above. Its unique contributions are **not lost**: (a) Position B
for `plans/` is preserved verbatim as the dissenter in §1c; (b) its
follow-up findings (F1 Linear-tool gap, F2 factory-dashboard stale list,
F3 Russian-language sweep output, F4 door-client unification) are **good
findings and are adopted into this plan's §4c** rather than left to die with
the closed PR. Closing #24 does **not** require human action (it is an open
PR the lead may close; the *merge* of #23 remains with the human). If the
human or the SE disagrees with the close, #24 can be reopened at zero cost —
but it must not be merged alongside #23 (conflicting `.gitignore` positions
on `plans/`, and two copies of the plan doc).

### 4c. Follow-up findings (adopted from the #24 draft + the SM intake record)

Tracked here for the human; **none is fixed by this PR** (foundation scope).

- **F1 — Linear tool gap (SM's FAM cluster exposed it).** No committed,
  generic Office tool for Linear project/ticket creation; `fam-linear-create.py`
  was a one-off prototype. If commissioned, a future tool
  (`crew/linear-create.py` or `office/linear.py`) starts from the §1a
  "what survives" note (pattern + quirks + idempotent-create).
- **F2 — `factory-dashboard` skill is unreliable** (stale container-name list:
  reported 0 running / 16 sleeping while 9 containers were up). Already on the
  bus as an `audit.finding` by the SM on 2026-08-27; suggested owner
  architect + staff-engineer; verify container state via bus events or a door
  TCP probe until fixed. Not yet ticketed.
- **F3 — sweep output is in Russian**, against the Office standard "work in
  English". Minor; fix in the `scrum-sweep` skill (output language).
- **F4 — door-client unification.** After #21, reconcile the divergent
  `crew-send.py` copies (office canonical vs lab-1's shipped variant; dev-1 /
  spec-1 carry the same latent gap) to one canonical client behind a shared
  read-only mount. Track as one foundation ticket.

### 4d. Process note for the record

The merge-order comments on #19/#20/#21/#22 were posted at 08:06 UTC by
staff-engineer, attributed to the SE with the architect's direction; the
architect's own confirmation comments (posted immediately after this commit,
2026-08-28) are the formal lead sign-off on the sequence. Coordination
between architect and SE ran over their HMAC doors (`/webhooks/inbox`); the PR
thread remains the shared channel of record, per the brief.

---

## 5. Round status

- **R1 (this commit):** SE executed the PR + merge-order comments; architect
  finalized the verdict (§1, §1c ruling), independently verified every brief
  fact (§4a), disposed of the duplicate PR #24 (§4b), adopted its findings
  (§4c). **Artifact exists: this commit + PR #23.**
- **R2 (pending):** staff-engineer's formal review of the architect's verdict
  (as a PR comment on #23, blocking-level scrutiny — the architect's
  confirmation comments on #19–#22 are posted in parallel). Any fix to this
  doc or `.gitignore` lands as one commit on this branch.
- **R3 (pending):** both confirm merge-ready; architect posts final sign-off.
- **Standing rule from the brief:** any round that ends without a committed
  artifact is flagged to the Scrum Master, not extended.

---

*Prepared by staff-engineer (R1 execution, commit `30a675e`) from the Scrum
Master pre-verdict + verified git/GitHub evidence; **finalized by the
architect** (R1 final commit) — verdict table, `plans/` ruling, independent
verification, and PR #24 disposition are the architect's. Cross-review is
conducted as PR comments on #23 and #19/#20/#21/#22. **Nothing is merged by
this plan — the human approves merges.***
