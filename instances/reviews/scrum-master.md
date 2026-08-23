# Adversarial Review — PR #1 (`feat/team-lifecycle-and-bus-hardening`)

**Reviewer lens:** PRODUCT / PROCESS — transparency, status visibility, completeness of change docs.

## VERDICT

**REQUEST CHANGES** — the lifecycle controller itself looks well-scoped, but the PR bundles unrelated work, ships committed secrets, and its change docs claim verification that isn't visible anywhere in the repo.

## BLOCKING FINDINGS

**B1 — Committed webhook secrets in agent configs (transparency/security of shared state).**
`agents/*/hermes-home/config.yaml` replaces the old `${CUSTOM_API_KEY}` indirection with literal hex secrets (`secret: 268153c0…`, `secret: 3f7e2879…`, etc.) committed to the branch. Anyone with repo read access can now impersonate any agent's webhook inbox. This must move to env/secret injection before merge, and the exposed values rotated. From a process standpoint this also undermines the PR's own `.gitignore` story ("runtime files are local") — secrets are runtime files too.

**B2 — PR mixes three unrelated changes; status of the actual change is obscured.**
The branch contains (a) the lifecycle controller + change docs, (b) OpenRouter/webhook rewiring of all four agent configs, (c) a large `.gitignore` runtime-state sweep. The openspec change doc (`add-team-agent-lifecycle`) describes only (a); its "Affected code: new controller module; no changes to upstream compose/doors" claim is contradicted by the diff (`docker-compose.yml`, `registry/doors.json` touched). Reviewers cannot assess the reviewed change against its spec. Split into separate PRs, or amend proposal.md Impact to cover everything actually in the diff.

**B3 — Tasks.md verification items are unchecked with no evidence they were run.**
Tasks 3.1–3.3 (unit tests, integration vs local Redis, idle-stop in a scratch compose project) are all `[ ]`, and there is no `tests/` directory or CI artifact in the diff. Task 4.1 (adversarial review) is also open. Per the SDD gate (4.2: "spec deltas merged only after approvals"), merging now would skip the team's own defined process. Either run and commit the verification, or explicitly mark 3.x as deferred with a follow-up task — silence is not a status.

## NON-BLOCKING NOTES

- **N1 — No spec deltas included.** proposal.md says "Affected specs: `agent-lifecycle`, `message-bus`" but the change folder contains only proposal/design/tasks — no `specs/` delta folder. The openspec flow expects the delta to travel with the change so the review gate can approve it.
- **N2 — Status visibility is good where it exists.** Emitting `agent.started`/`agent.stopped`/`agent.wake_failed` into the durable `office:events` stream so `crew/office-log.py --follow` shows lifecycle transitions with zero new tooling is the right transparency call. Consider also emitting a `agent.wake` *received* event so the log distinguishes "wake requested" from "wake succeeded" when debugging the 90s wake window.
- **N3 — design.md risk note ("single-controller assumption … noted in ops docs") references ops docs that don't exist in this diff.** Either add the note to deploy.md or soften the claim.
- **N4 — proposal.md cites both `docs/mvp-scope.md` and `openspec/specs/agent-lifecycle/spec.md`; design.md cites `docs/agent-lifecycle.md`.** Inconsistent spec pointers make it hard to trace which requirement is authoritative — pick one canonical path.
- **N5 — tasks.md has no owners or target PR links per section.** For a multi-team SDD flow, add an owner column so the review gate (4.1/4.2) has a clear accountable party.

*Review by scrum-master, lens: product/process.*
