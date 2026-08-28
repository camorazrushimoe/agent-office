# Architect record — `fix/factory-control-docker-cli` HELD (out of merge train) + folded scope

> **Oversight decision (2026-08-28, human-approved):** the branch goes **OUT of the
> current merge train**. **No PR is opened for it until #21 and #22 are merged.**
> After the train, it goes **first in the next batch as its own PR with its own
> review**. Recorded here so the fold-in scope below survives the hold.
> This is an Architect record (artifact of #22, records-only PR); it gates nothing.

**Recorded:** 2026-08-28 ~11:05 UTC · main = `9581530` (post-#20, post-#25)

---

## 1. Current branch state (verified 2026-08-28)

- Branch `fix/factory-control-docker-cli` = `ad8f632`, 1 commit, **1 file
  (`Dockerfile.factory-control`, +3/−1)**: adds `docker-cli` to the `apt-get install`
  line. PR **opened at 10:52:18Z as #26** (before the hold decision landed).
- **#26 is base-stale:** base = `6e46fd0` (post-#25, **pre-#20**); `9581530` is **not**
  an ancestor (`git merge-base --is-ancestor` = NO). Three-dot PR diff vs current main
  is clean — exactly the Dockerfile change, `mergeable: true`. **Before its review
  turn, rebase onto post-train main.** (The 8-file local diff some tools show is
  the two-dot diff vs post-#20 main and is an artifact of the stale base — the tree
  itself contains no deletion; `git log --stat` proves 1 file per commit.)
- PR #26 body claims verified on the PR itself: Debian 13 (trixie) split the docker
  client out of `docker.io`; symptom `[fc] reap error: [Errno 2] No such file or
  directory: 'docker'`. Fix is minimal and correct in isolation; both-base compat
  (bookworm/trixie) as argued in the body.

## 2. Folded scope for the next-batch PR (oversight-mandated, 2026-08-28)

When #26's turn comes, the PR scope = docker-cli **+** the two lifecycle defects
below. Same owner area (factory-control / agent lifecycle), same review pass.

### 2a. `agent.wake` target naming mismatch — wake-on-demand is a no-op for every instance agent

**Incident (2026-08-28):** lab-1 evaluation agent dead ~5 h. factory-control logged
`wake ignored: lab-1:evaluation not in registry`; the lead's wake went into the void.
Unblocked by hand-starting the container.

**Root cause (verified in tree, live `/opt/repo` checkout):**

- Supervisor match (`office/lifecycle/factory_control.py:210-216`):
  `a["id"] == target or a["container"] == target`. Registry
  (`office/registry/factory-agents.json`) keys instance agents by **hyphenated id**
  (`lab-1-evaluation`) / container name (`lab-1-evaluation`).
- Envelope target came in **colon-form** `lab-1:evaluation` — the `wake_hint` values
  shipped in the per-instance door registry
  `instances/<team>/crew/agents.json` (gitignored; e.g.
  `instances/lab-1/crew/agents.json:18`).
- **Scope is all 15 instance agents, not lab-1**: dev-1 (`dev-1:developer`, …),
  spec-1 (`spec-1:technical-product-manager`, …) all carry colon-form `wake_hint`.
- The **canonical** senders use registry-id form and work:
  `scripts/smoke.py request_wake()` and `office/bus/client.py:340 send_wake()`
  (`target=agent_id`, published to `office:inbox:<agent_id>`). So the envelope
  contract in practice is **registry id**, and the colon-form `wake_hint` is the
  outlier — the fix aligns the instance side, or the listener learns the mapping.

**Required fix shape (for the review):**
1. Single canonical target form = **registry `id`**; align the sender side
   (`agents.json` `wake_hint` generation, e.g. `manage_tokens.py derive-agents`, and
   every consumer that reads `wake_hint`) or make `wake()` map `team:role` →
   registry id explicitly. Decide the owner of the mapping in the PR, not in the log.
2. **Observability gap (blocking for me):** an unmatched wake target only
   `log()`s locally (`factory_control.py:214`) — no bus event, which is why this
   sat 5 h invisible. An `agent.wake_ignored` (or similar) event through the
   durable publish path is required, per the agent-lifecycle spec's event
   requirements. Local log alone is not an acceptable terminal state for a
   failed wake.

### 2b. Reaper stale-idle signal — stops a freshly started agent within ~2 min

**Reported:** reaper kills an agent ~2 min after start because the idle signal
reads old log lines.

**Mechanics (verified in `factory_control.py`):**
- `seconds_idle()` (lines 85-112) scans the last 200 KB of
  `<log_path>/logs/agent.log` for `ACTIVITY_MARKS` and takes the **newest** matching
  line's timestamp; falls back to file mtime only when **no** task-work line exists.
- A just-woken agent whose log still contains its **previous session's** task-work
  lines (and which hasn't emitted a *newer* one yet — boot takes longer than that,
  and the log persists on the mounted home across stops) reads **idle ≥ 40 min** →
  `reap_once` stops it at the next 120 s tick. The mtime fallback does not save it,
  because mtime is recent but the code path only reaches it when no marker line
  exists at all.
- Net effect: wake → reaper reaps the woken agent before it can even process the
  message that woke it. Compounds 2a: with wake a no-op, nothing noticed.

**Required fix shape (for the review):** anchor the idle clock to the **start
event** — e.g. record the container start time (or consume
`agent.started` / the wake) and measure idle as
`min(now − newest_activity_ts, now − start_ts)`; a process that started T seconds
ago can never be reported idle for more than T seconds. Needs a regression test
covering: fresh start with stale pre-wake log lines must not be reaped before
`IDLE_TIMEOUT_S` of *actual* post-start idleness.

### 2c. Out of scope for #26 (recorded, tracked separately)

- `--wake` implementation in the door client + OFFICE-ATTACH.md contract
  (carried from #21 N1 / #19 N1).
- dev-1 / spec-1 crew-send gap (carried from #21 N2, F4).

## 3. Train status at time of writing

| PR | State |
|----|-------|
| #20 | **MERGED** — main `9581530`; my APPROVE on `3fce132` held under oversight re-check (B1 container form, B2 capability line, B3 24 h window all present) |
| #21 | Open, head still `84654c0` (**pre-rebase**). Awaiting SE rebase onto `9581530` + canonical client per B2. Re-review of the rebased head pending from me. |
| #22 | Open, head `6408069`; clean vs `9581530` (3 record files, zero conflicts, merge-sim verified). **This record lands in it.** |
| #26 | Open (pre-hold), **HOLD** — no review turn until #21+#22 merged, then first of next batch with the 2a/2b scope. |

I do not merge anything; oversight merges.
