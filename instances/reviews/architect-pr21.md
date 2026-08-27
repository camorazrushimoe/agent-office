# Adversarial Architecture Review — PR #21 (fix: lab-1 could not dispatch internally — crew-send.py was never mounted)

**Branch:** `fix/lab-1-crew-send-missing` @ `84654c0` (base `origin/main` @ `a748498`)
**Scope:** +338/−0 in 4 files (vs main) — `instances/lab-1/crew/crew-send.py` (+79) **plus all three files of PR #20**
**Reviewer:** Architect · 2026-08-27 18:20 UTC · read-only review (single pass)

---

## VERDICT: **needs-changes** (2 blocking)

The *diagnosis* is excellent and the *unblock* is real (verified 202-accepted
dispatch from `lab-1-research-lead`). But the branch as it sits against `main`
carries a second PR's changes, and the shipped file is **not** a copy of the
shell's `crew/crew-send.py` — it is the separate, already-divergent lab-crew
variant — so the durable fix shape (committed copy) will drift.

### The stacking question (called out explicitly, as requested)

**Verified:** `git merge-base --is-ancestor pr-20 pr-21` → **yes**. `02b0719`
(intent-alignment gate) is the direct parent of `84654c0` (the crew-send fix).
`git diff --stat pr-20 pr-21` → **only** `instances/lab-1/crew/crew-send.py`
(+79). The three gate files are **byte-identical** in pr-20 and pr-21 (sha256
matched for all three). So the diff-vs-main that GitHub shows for #21
(+338/−0, 4 files) = #20's +259/−0 (3 files) + this PR's +79/−0 (1 file).

**Is the stacking acceptable?** Not as it stands. It becomes acceptable **only
if #20 merges first**, and even then a rebase is recommended for hygiene:
- Merging #21 first (or before #20) silently lands the intent-alignment gate,
  violating "never mix foundation work into unrelated fixes" and the
  `foundation-evolution` Separation rule, and it defeats #20's own review gate.
- GitHub `mergeable: clean` for both only means *no textual conflict*; it does
  not mean the semantic scope is right.
- **Required merge order: #20 → then #21.** If #20 lands first, #21's
  three-dot diff against `main` collapses to the single `crew-send.py` file and
  it can merge as-is. Rebase #21 onto updated `main` anyway so the PR diff, the
  commit graph, and the review scope all show one fix. If #20 is *rejected*,
  rebase #21 onto `main` *without* #20 — it becomes purely the crew-send fix.
  Either way #21 must never merge before #20.

### Is mounting a *copy* of crew-send.py the right fix? — No; it is duplication that will drift.

**Byte-for-byte comparison (the key fact the task asked to verify):** the file
added by #21 is **NOT** a copy of the shell's `crew/crew-send.py`.

```
file                                        bytes   sha256 (first 16)
crew/crew-send.py  (origin/main, office)     2532    db042c0959b4e9c6
instances/lab-1/crew/crew-send.py (pr-21)    2502    45be98445d82c1fe
```
`cmp` → differ at char 27, line 2. They are two *different* door clients:

| | `crew/crew-send.py` (office) | `instances/lab-1/crew/crew-send.py` (lab-crew variant) |
|---|---|---|
| docstring | "Agent Office — door client … Office agent" | "Lab Crew — door client … webhook door" |
| `from __future__ import annotations` | yes | no |
| missing-registry guard | yes — `if not os.path.isfile: sys.exit("Copy crew/agents.example.json…")` (line 30) | **no** — bare `open()` → unhandled `FileNotFoundError` traceback (line 32–34) |
| unknown-agent listing | `sorted(registry)` (line 47) | unsorted (line 44) |
| `urlopen` timeout | 30 s (line 61) | 15 s (line 56) |
| `--wake` | absent | absent (docstring notes "wake-aware send … pending") |

So the real situation is **three** diverging copies of one tool (office, lab-crew,
and dev-crew's own), and #21 adds a lab-1-local fourth instance of the lab
variant. This is the "shotgun surgery" smell in reverse: one logical tool, N
drifting copies.

**The better fix — a shared read-only mount — is available and strictly superior.**
Lab-1 (and dev-1, spec-1) already mount the office code at a stable read-only
path: `instances/lab-1/docker-compose.yml` has
`../../office:/opt/office-lib:ro` and `./crew:/opt/crew:ro`. The office
`crew-send.py` is reachable inside these containers today via the office tree —
the instances already depend on `office/`. So instead of committing a divergent
copy into `instances/lab-1/crew/`, the durable fix is:

1. Make **one** canonical door client (recommend: the office `crew/crew-send.py`,
   which already has the missing-registry guard + longer timeout + sorted output),
   or at minimum reconcile the three variants into one.
2. In `instances/lab-1/docker-compose.yml`, expose that canonical file at
   `/opt/crew/crew-send.py` via an additional read-only bind (e.g. mount the
   office `crew/` next to the instance `crew/`), rather than copying a file into
   `instances/lab-1/crew/`.
3. Point the `task-dispatch` skill at that canonical path so every instance
   shares one implementation.

Why this is better than the shipped copy:
- **No drift.** One file, one sha256, every instance identical. Today the office
  client has a missing-registry guard the lab variant lacks; the moment someone
  improves one, they diverge again (exactly the failure #21's PR body admits for
  dev-1: "needs a decision, not a copy").
- **The copy's own weakness becomes the argument.** The lab variant crashes with
  an unhandled traceback when `crew/agents.json` is missing (see B2) — a guard
  the office copy *already has*. Copying the weaker file is choosing the worse
  implementation on purpose.
- **Matches the repo's existing pattern.** Instances already `:ro`-mount office
  code (`/opt/office-lib`, `/opt/docs`, `/opt/tokens`); a read-only mount of the
  shared door client is the same idiom, not a new one.

Caveat (honest): a *single* bind of the whole office `crew/` dir would also
bring `crew/agents.json` semantics and `agents.example.json` into the instance
mount; if the instance needs its **own** `agents.json` (it does — different door
secrets), keep the instance `crew/` for `agents.json` and mount only the
`crew-send.py` (or a `shared/` subdir) alongside. That still removes the
duplication that matters (the code), while letting secrets stay per-instance.

### BLOCKING

**B1 — Merge-order coupling: #21 must not merge before #20 (stacking).**
`git merge-base --is-ancestor pr-20 pr-21` = true; `git diff --stat pr-20 pr-21`
= crew-send.py only; the three gate files are byte-identical in both branches.
Merging #21 before #20 silently lands the intent-alignment gate. **Fix: merge
#20 first, then #21** (optionally rebase #21 onto the updated `main` so the PR
diff is the single file). This is an ordering fix, not a code fix — no
rework of the crew-send change itself is required by this item.

**B2 — The committed file is a divergent *copy* of the door client that has
already drifted and is the weaker of the two variants — the wrong durable fix.**
The operator asked specifically: copy vs. a shared read-only mount. The verdict
is **mount**, for three reasons, all verifiable:
1. *It is not a copy of `crew/crew-send.py`.* It is the separate **lab-crew
   variant**, and the two have *already* diverged (docstring, no
   `from __future__ import annotations`, no missing-registry guard, unsorted
   agent listing, 15 s vs 30 s timeout — see the byte table above). Committing
   a second copy of an already-divergent file is adding drift, not removing it.
2. *The copy is the weaker variant.* Its `load_registry()`
   (`instances/lab-1/crew/crew-send.py:32–34`) does a bare `open()` with **no**
   `isfile` guard, so a run before `manage_tokens.py derive-agents` has produced
   `instances/lab-1/crew/agents.json` dies with an unhandled `FileNotFoundError`
   traceback — the office variant (`crew/crew-send.py:29–33`) exits with an
   actionable message instead. This is the exact class of opaque failure the PR
   is meant to remove.
3. *The mount is already available.* Every instance service already
   `:ro`-mounts office code (`../../office:/opt/office-lib:ro`), and the office
   `crew-send.py` is the canonical, guarded, longer-timeout client. The durable
   fix is to expose **one** canonical door client at `/opt/crew/crew-send.py`
   for all instances (read-only bind of the office client, or a `shared/`
   subdir) and point the `task-dispatch` skill at it — one file, one sha256,
   no drift. Keep the per-instance `crew/` only for the gitignored
   `agents.json` (per-instance door secrets), which `derive-agents` already
   writes per instance.

This does **not** block the *unblock*: the stopgap (a working `crew-send.py` in
the lab-1 mount) is accepted and clearly valuable. It blocks committing the
divergent copy as the *durable* state and, as a minimum before merge, requires
adopting the office variant's missing-file guard (one line) plus a header
comment pinning the file to `crew/crew-send.py` so the next change reconciles
instead of forking. The shared read-only mount is the recommended follow-up
that should close the class of defect (dev-1 and spec-1 have the same latent
gap).

### Non-blocking notes

**N1 — `--wake` is still absent, and OFFICE-ATTACH claims it exists.**
`instances/lab-1/crew/crew-send.py:17` says "wake-aware send … pending", but
`instances/lab-1/OFFICE-ATTACH.md:21` states "Wake-aware send: `crew-send.py
--wake` → publishes `agent.wake`, waits health, then POSTs". The PR does not add
`--wake`, so after merge the attach contract is still aspirational. This is the
same gap #19's spec (N1) inherits. Track one ticket: implement `--wake` in the
canonical client and update OFFICE-ATTACH. Until then, dispatch to a *stopped*
lab-1 agent will still fail (door POST to a stopped container) even though the
file now exists — the PR unblocks *agent-to-agent while the target is up*, not
wake-aware dispatch.

**N2 — dev-1 (and spec-1) have the identical gap and are correctly out of scope.**
The PR body flags dev-1 and says "needs a decision, not a copy" — agreed. That
decision is the mount recommendation in B2: reconcile to one canonical client +
shared read-only mount, then apply to dev-1 and spec-1 (both mount `./crew` and
have the same latent gap). Do not make two more copies.

**N3 — Strengths:** root-caused a misdiagnosis (consent-gate was a red herring;
`hermes approvals test` proved no guard), minimal blast radius, verified from
inside the container, surfaced two unrelated real defects (lossy pub/sub wake;
idle reaper killing freshly-woken agents) as `defect.found` for separate
tickets, and explicitly did not self-merge. The *investigation* is exactly how
this kind of fix should go; only the *fix shape* (copy vs shared mount) and the
*merge order* (stacking) need to change.

---

*Review committed on `review/architect-pr19-21` (this file). Companion reviews:
`architect-pr19.md`, `architect-pr20.md`.*
