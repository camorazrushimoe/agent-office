# Delta: team-onboarding — spec teams

## MODIFIED Requirements

### Requirement: New team admission

The team type enumeration SHALL include `spec`:

| Type | Template of record | Private environment |
|------|--------------------|---------------------|
| Lab | `lab-crew` | Usually lightweight workspace only |
| Spec | `product-factory` | None — artifacts are documents |
| Dev | `dev-crew` | Own private dev-cluster |

#### Scenario: onboarding a spec team

- **WHEN** a product-factory instance passes the onboarding checklist
  (shared bus, no private Redis, lifecycle, doors, required events)
- **THEN** it SHALL be registered with `type: spec` and become assignable
  to the specification stage between Lab research and Dev implementation

### Requirement: Registry

The registry `type` field SHALL accept `lab`, `spec`, `dev`, and `other`.
