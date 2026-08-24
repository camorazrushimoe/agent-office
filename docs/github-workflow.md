# Agent Office — GitHub Workflow Standard (foundation)

Shared GitHub discipline for **every agent in every team** (Lab / Spec / Dev /
Office). This is the foundation layer — it applies to any repository the teams
touch: product repos, the factory template repos, and `agent-office` itself.

## Golden rules

1. **Never push directly to `main`/`master`.**
2. **Always work on a feature branch**, named after the work (`feature/<ticket>-slug`, `fix/...`, `chore/...`, `docs/...`).
3. **Every change lands via a Pull Request.**
4. **Never self-merge** — a reviewer (not the author) approves before merge.
5. **Conventional commits** — `feat:`, `fix:`, `chore:`, `docs:`, `refactor:`, `test:`.
6. **CI green before merge** (where CI exists); never merge a red branch.

## The flow

1. **Branch** off the latest `main`.
2. **Commit** incrementally with conventional-commit messages.
3. **Open a PR** with context: what changed, why, and a link to the ticket/spec
   (Linear ticket `BON-<n>` or the OpenSpec change).
4. **Request review** — assign a concrete reviewer (qa / manager / architect /
   staff-engineer depending on the repo). Do not leave it unassigned.
5. **Address review** — respond to comments; push follow-up commits to the same
   branch.
6. **Merge only after approval** — squash or rebase-merge; do not self-approve.

## Review etiquette

- Review against the **spec / requirements**, not just style.
- Verdict is explicit: `approve` or `needs-changes`, with **at most 3 blocking
  findings** (evaluation, not redesign).
- Non-blocking nitpicks are labelled as such; do not block a PR on nits.
- Reviews are factual and reference the spec or a concrete defect.

## What "done" means for a PR

- Branch is up to date with `main` (rebase if needed).
- CI / checks pass.
- Scratch/temp files are cleaned (no debug dumps committed).
- The ticket/issue references the PR, and the PR references the ticket.
- Merged by a reviewer; the branch is deleted after merge.

## Anti-patterns (forbidden)

- `git push origin main` with work on it.
- Self-merging without review ("I'll just merge it").
- `git add -A` blindly — stage explicit paths.
- Committing secrets or local runtime files (respect `.gitignore`).
- Merging with a failing CI to "fix later".

## Why this matters

GitHub is where review and auditability happen. A PR is the durable record of
*what* changed and *why*, and review is the only gate that keeps the factory's
output coherent across teams. Linear tracks the *work*; GitHub tracks the *code*;
the two are linked by referencing `BON-<n>` in PR bodies and comments.
