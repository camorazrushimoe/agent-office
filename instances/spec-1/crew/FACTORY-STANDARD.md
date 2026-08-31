# Product Factory — Factory Standard

This factory produces **product specs, not code**. Its pipeline takes a business
request and drives it through research, system analysis, adversarial review, and
spec finalization — publishing a reviewed Product Spec plus a per-project LLM
Wiki as the handoff artifact.

## The golden rule

**No spec → no handoff.** Every pipeline run must end in a reviewed spec
artifact. If a task has no path to a spec, clarify scope with the requester
before doing deep work.

## What a run looks like

A run follows the spec pipeline: **intake → understand-system → research →
shape → spec → review (human gate) → finalize**. Each stage publishes its
outcome on the Office bus (`office:events`) with explicit event provenance, and
intermediate artifacts live in the shared `/workspace` / `/knowledge` volumes.

## Roles

| Agent | Owns |
|---|---|
| technical-product-manager | drives the pipeline, shapes the spec, owns the human review gate |
| product-researcher | gathers evidence, market/context research feeding the spec |
| system-domain-analyst | maps the system being changed and constraints |
| adversarial-reviewer | reviews the spec from an adversarial lens before the human gate |

## Working with sibling agents

- Siblings are reached through their webhook doors in `crew/agents.json`
  (HMAC-signed, container URLs on the shared docker network).
- Delivering a message to a stopped sibling **wakes it automatically**: the
  canonical door client (`crew/crew-send.py`) publishes `agent.wake`, waits for
  health, then re-delivers. Never manually manage containers.
- Handoffs must be visible on the bus (`handoff.requested` /
  `handoff.accepted`) per `docs/handoff-protocol.md`.

## Skill guardrails

Factory skills and standards are read-only mounts; do not silently create or
patch them. Runtime notes may live under hermes-home (gitignored) and are not
factory contract until promoted via a reviewed PR.

## Language

Work in English — specs, reviews, bus events and reports.
