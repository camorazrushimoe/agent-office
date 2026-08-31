# Product Factory — Factory Standard

This factory turns ideas into **specifications**: intake → understand-system →
research → shape → spec → review (human gate) → finalize. Its artifacts are
**documents** — an OpenSpec-style spec plus a per-project LLM Wiki — published
through the shared Office Redis bus with explicit event provenance at every
stage. If there is no spec, there is no work.

## The golden rule

**No spec → no work.** Every task is backed by a spec with a clear owner. When
a task arrives without a reference to a spec or a pipeline stage, do NOT start
shaping or drafting. Ask: **"Where is the spec? Who owns this stage?"** The
technical-product-manager decides before you begin.

## The pipeline (end to end)

1. **Intake** — TPM receives the business request, classifies it, publishes
   `intake.received` / `intake.classified`.
2. **Understand system** — system-domain-analyst maps the AS-IS: code,
   architecture, constraints (`architecture.mapped`, `domain.mapped`).
3. **Research** — product-researcher owns problems, opportunities, human
   insights (`human.insights.ready`, `opportunities.ready`).
4. **Shape** — TPM frames the problem and shapes candidate solutions
   (`problem.framed`, `solutions.shaped`, `constraints.collected`).
5. **Spec** — TPM drafts the product spec (`spec.drafted`) and the per-project
   LLM Wiki (`wiki.updated`).
6. **Review (human gate)** — adversarial-reviewer owns the quality gate
   (`spec.reviewed`, `human.gate.required`); the human decides.
7. **Finalize** — TPM publishes the final spec (`spec.final`,
   `pipeline.finished`).

## Roles

| Agent | Door | Owns |
|---|---|---|
| technical-product-manager | 8681 | intake, constraints, solution shaping, the Spec, the Wiki |
| product-researcher | 8682 | problems, opportunities, human insights |
| system-domain-analyst | 8683 | factual AS-IS (code, architecture) |
| adversarial-reviewer | 8684 | the quality gate (human-gated stage) |

Do not overstep: each stage has one owner; hand work to a sibling over its
webhook door (`/opt/crew/agents.json`, `container_url` + HMAC secret) and
always use the wake-on-failure door client.

## Bus discipline

- Use the shared Office bus (`$OFFICE_BUS_URL`); always publish via the
  durable path (`publish_event` → `office:events` stream + live topic) — never
  raw PUBLISH, or followers and Scrum Master lose the durable log.
- Publish at every stage boundary and verify after publishing (read back with
  `XREVRANGE office:events + - COUNT n`).
- Actor id = `$TEAM_NAME/<role>` (e.g. `spec-1/technical-product-manager`).

## Workspace hygiene

- **Scratch** = non-deliverable files (review drafts, temp notes, dumps).
- Write scratch only under `$HERMES_HOME` or `/tmp`.
- Never leave scratch under `workspace/<project>/`.
- Before opening a PR, clean untracked scratch from the project tree.
- Never `git add -A` blindly — stage explicit paths.

## Skill guardrails

Factory skills are read-only mounts; do not silently create or patch them.
Runtime/personal notes may live under hermes-home (gitignored) and are not
factory contract until promoted via a normal reviewed PR. Skill-like writes
under hermes-home should be visible on the bus when feasible
(`skill.created` / `skill.patched`).

## Escape hatch (critical override)

In a critical situation the TPM MAY override the workflow by explicitly
approving the override. Every override SHALL be recorded immediately as
**tech debt** — a GitHub issue labelled `tech-debt` (or a Linear ticket) — so
the shortcut is never silent.

## Language

Work in English — code, commits, PRs, tickets, specs and reports.
