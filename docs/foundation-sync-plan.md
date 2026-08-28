# Foundation Sync Audit — Delta Verdict + Merge Order

> **Status:** Round 1 (staff-engineer execution). The DELTA VERDICT table starts
> from the Scrum Master's pre-verdict; the **Architect finalizes/overrides** it.
> Where a call changes from the pre-verdict, **both positions are kept visible**
> below — disagreements are never averaged.
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

Verdicts below start from the **Scrum Master pre-verdict**. Column "Changed?"
marks any deviation (none in R1; architect may change in R2/R3 — both
positions will then be kept).

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

**Cluster rationale (SM pre-verdict, unchanged in R1):** these are one-shot
intake scripts that already ran. The durable pattern is
`parse_tokens(TOKENS_FILE) -> stdlib urllib GraphQL`, which is documented in
Scrum Master memory; promoting the raw one-shots would **duplicate** that
pattern. **The one candidate for lasting value is `fam-linear-create.py`'s
reuse-or-create duplicate-guard** — and its home is a **note in the docs**, not
a committed script. The reusable facts (Linear API quirks) already live in
memory. **No fam file is promoted.**

### 1b. Other untracked artifacts

| Artifact | Verdict | One-line reason | Changed? |
|----------|---------|-----------------|----------|
| `agents/*/hermes-home/memories/` (SM + architect) | **IGNORE** (gitignore) | Per-agent live runtime memory; regrows every session. Repo convention commits SOUL/config.template/skills, not runtime state. | No |
| `agents/scrum-master/hermes-home/sweep-report.md` | **IGNORE** (gitignore) | Dated (25 Aug) output of the tracked `scrum-sweep` skill; regenerable. | No |
| `agents/architect/hermes-home/verification_evidence.db` | **IGNORE** (gitignore) | Runtime sqlite state; same class as already-ignored `response_store.db*`/`state.db*`. | No |
| `agents/*/hermes-home/plans/` (the dir) | **IGNORE-BY-VISIBILITY** (do **not** gitignore) | A recurring untracked `plans/` dir is a **signal** the next audit should see, not noise. **Open to challenge** — see §1c. | No (flagged open) |
| `agents/*/hermes-home/skills/` (architect **bundle**) | **IGNORE** (already gitignored, line `agents/*/hermes-home/skills/`) | Vendor-origin bundled skills (`airtable`, `apple-*`, `claude-code`, `codebase-inspection`, `github-*`, `hermes-agent`, `notion`, `obsidian`, … ~13 categories) with a `.bundled_manifest`. **Not** factory-authored foundation. **Do not promote anything from the bundle.** | No |

> **Do not confuse the two "skills" trees.** The **repo's curated foundation
> skills** are at `agents/<role>/skills/` (**tracked**, e.g.
> `agents/architect/skills/code-review`,
> `agents/scrum-master/skills/{scrum-sweep,intent-alignment-gate}`). The
> **bundle** is at `agents/<role>/hermes-home/skills/` (vendor-origin,
> **ignored by design**). The existing `.gitignore` line
> `agents/*/hermes-home/skills/` already covers the bundle — verified with
> `git check-ignore`.

### 1c. Open disagreement (kept visible, not averaged)

**`plans/` visibility — two positions:**

- **Position A (SM pre-verdict, R1 default):** do **not** gitignore
  `agents/*/hermes-home/plans/`. Keep it visible/untracked so the next sync
  audit *sees the recurrence*. A recurring untracked dir is a **signal**, not
  noise.
- **Position B (alternative):** gitignore `plans/` like `kanban*` — it is
  per-agent runtime working space, and leaving it untracked keeps polluting
  `git status`.

R1 ships **Position A** (visible) and flags it for the architect. If the
architect overturns it to B in R2/R3, this table is updated and **both
positions remain visible** here. The `.gitignore` change for that case is a
one-line addition.

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
- The `plans/` visibility call (§1c) stays **open** pending architect
  cross-review.

---

*Prepared by staff-engineer (R1) from the Scrum Master pre-verdict + verified
git/GitHub evidence. Architect finalizes/overrides the verdict table and merge
order in R2; cross-review is conducted as PR comments on #23 and #19/#20/#21/#22.*
