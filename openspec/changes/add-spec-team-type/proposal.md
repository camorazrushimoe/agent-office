# Change: add spec team type (product-factory template)

## Why

The Office composition model (openspec/specs/composition) declares Lab and Dev
team types, but the pipeline has a third stage: **Product Factory** — a
portable agentic factory that turns business intake into high-quality product
specifications (https://github.com/camorazrushimoe/product-factory).

Its PR #1 (merged) added `docs/office-template.md` — the explicit Office
template contract: shared Office Redis bus, idle stop + wake-on-demand,
`type=spec` registration, `spec.ready` handoff events, human gates as bus
events. The Office side must recognize this template as a first-class team
type; today `docs/team-registry.md` documents only `lab | dev | other` and
the example composition has no spec entry.

## What Changes

- **Team registry schema** (`docs/team-registry.md`): document `type: spec`
  as a first-class value (`lab | spec | dev | other`), with the standard
  required fields (name, type, template.repo/ref, status, endpoints.doors)
  and the spec-specific notes:
  - Spec teams need **no private dev-cluster** (artifacts are documents).
  - Handoff event is `spec.ready` with an artifact pointer.
  - Human gates surface as first-class bus events for Office escalation.
- **Composition example** (`config/office-composition.example.yaml`): add a
  commented `spec-1` entry showing how to declare a Product Factory instance
  from the pinned template ref (kept commented so the default example stays
  1 lab + 2 dev per v1 reference shape).
- **Onboarding checklist** (`docs/onboarding-team.md`): add spec-team row to
  the types table (no private cluster; artifacts = specs/wiki/workspace).

## Impact

- Affected specs: `composition` (template inventory now includes
  product-factory as the spec-team template), `team-onboarding`
  (type enumeration), `handoff` (spec.ready joins the documented flow:
  Lab → Office → **Spec** → Dev)
- Affected code: none — this change is documentation/config-shape only.
  Spawning/attaching instances remains follow-up work (explicitly out of
  scope here per operator request).
