# Delta: handoff — spec stage

## MODIFIED Requirements

### Requirement: Main flows

The main flows SHALL include the specification stage between validated
research (or raw intake) and implementation:

1. Idea → Lab (research)
2. Lab → Office (research complete)
3. Office → **Spec** (specification assignment; product-factory instance
   turns intake/research into a Product Spec)
4. **Spec → Office** (`spec.ready` with artifact pointer) → Office routes to Dev
5. Office → Dev (implementation assignment)
6. Dev → Office / Super DevOps (status, blockers, promotion requests)

#### Scenario: spec completed

- **WHEN** a Spec team publishes `spec.ready` with an artifact pointer
- **THEN** Office SHALL treat the spec as the entry artifact for the
  implementation assignment flow and record ownership via Scrum Master

### Requirement: Anti-patterns (SHALL NOT)

Existing anti-patterns apply. Additionally:

- Starting Dev implementation on a project whose Product Spec was never
  delivered (`spec.ready`) when the pipeline includes a Spec stage SHALL be
  treated as silent reassignment — a bus event is required.
