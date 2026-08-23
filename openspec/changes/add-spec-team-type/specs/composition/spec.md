# Delta: composition — spec team template

## ADDED Requirements

### Requirement: Spec team type

The Office SHALL recognize `spec` as a first-class team type alongside `lab`
and `dev`.

- Template of record: [product-factory](https://github.com/camorazrushimoe/product-factory)
  per its merged Office template contract (`docs/office-template.md`).
- Spec teams turn business intake / validated research into **Product Specs
  ready for engineering**.
- Spec teams require no private dev-cluster; their artifacts are documents.
- Pipeline position: Lab (research) → **Spec (product specification)** →
  Dev (implementation). Office owns routing between stages.

#### Scenario: declaring a spec instance in composition

- **WHEN** an operator declares a team entry with `type: spec` and the
  product-factory template repo/ref
- **THEN** the entry SHALL be valid under this contract without forking Office

### Requirement: spec handoff event

A completed Spec-team engagement SHALL be published as a `spec.ready` event
carrying an artifact pointer (not the full document body).

#### Scenario: spec finished

- **WHEN** a Spec team finishes a Product Spec
- **THEN** a `spec.ready` envelope SHALL appear on the shared bus with
  actor `<instance>/<role>`, project id, and payload artifact pointer
