# Handoff Protocol

How work moves between Agent Office, Lab teams and Dev teams.

## Principles

- Every handoff is an explicit, observable event on the shared Redis bus.
- The receiving side must acknowledge (or reject with reason).
- Context travels with the handoff; the receiver should not have to reverse-engineer intent.
- Scrum Master can always reconstruct the current ownership of a project.

## Main flows

### 1. Idea → Lab (research request)

**Trigger:** Human or Office decides an idea needs validation before building.

**Payload should contain:**
- Project / idea identifier
- Short description / BRIEF
- Why research is needed
- Desired outcome (Research Package, go/no-go, specific questions)
- Priority / constraints

**Lab team responsibilities after acceptance:**
- Run the hypothesis-driven cycle
- Produce a Research Package (or explicit “not worth building”)
- Publish `research.ready` (or equivalent) on the bus

### 2. Lab → Office (research complete)

**Payload:** Research Package (or negative recommendation) + link to artifacts.

Office (usually via Scrum Master + Architect) decides:
- Proceed to Dev
- More research needed
- Stop

### 3. Office → Dev (implementation assignment)

**Trigger:** Research is good enough (or the idea was already clear).

**Payload should contain:**
- Project identifier
- Link to Research Package / existing specs / OpenSpec
- Scope of what this particular Dev team is asked to do
- Known constraints and open questions
- Which private dev-cluster and later pre-prod path to use

**Dev team responsibilities after acceptance:**
- Follow its normal spec-first pipeline
- Keep status visible on the bus and in Linear
- Request promotion to shared pre-prod when ready

### 4. Dev → Office / Super DevOps (promotion request)

When a Dev team wants to put something into the shared pre-prod:

- Team DevOps (or developer) requests promotion
- Super DevOps reviews / coordinates
- Result (success / failure + notes) is published on the bus

### 5. Cross-team collaboration on the same project

Multiple teams may work on the same project over time or in parallel (different features).

Rules:
- Ownership of the *current active work* must be clear
- Shared pre-prod is the integration point
- Scrum Master is the source of truth for “who is currently responsible for what”

## Event naming (initial proposal)

These are high-level events; exact schema will live in `bus/` later.

| Event | Meaning |
|-------|--------|
| `project.created` | New project entered the portfolio |
| `project.assigned` | Project (or slice) given to a concrete team |
| `research.started` / `research.ready` | Lab lifecycle |
| `implementation.started` | Dev team began work |
| `promotion.requested` / `promotion.completed` | Movement into shared pre-prod |
| `project.blocked` | Explicit blocker raised |
| `handoff.rejected` | Receiving side cannot accept |

## Anti-patterns

- Silent reassignment of a project without an event
- Starting implementation without a clear assignment from Office
- Promoting to pre-prod without Super DevOps visibility
- Lab continuing to “improve” research after a formal handoff without a new cycle
