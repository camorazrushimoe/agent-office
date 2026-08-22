# Capability: environments

## Requirements

### Private dev-cluster (per Dev team)

Each Dev team SHALL own a private dev-cluster.

- The team (via its developer / DevOps agents) fully controls this environment.
- It is the sandbox for feature work, experimentation and breaking changes.
- Other teams and Office agents do not have default write access.

### Shared pre-prod (Office level)

Agent Office SHALL provide one shared pre-prod cluster.

- Owner: Super DevOps.
- Purpose: integration point and release-candidate gate for work coming from any Dev team.
- Promotion into pre-prod MUST follow rules defined by Super DevOps and be observable on the bus.

### Lab teams

Lab teams typically do not require a full private cluster. They work primarily with temporary workspace artifacts. If a Lab team later needs an environment, it is defined case by case and still must not bypass Office observability rules.

### Promotion path (Dev)

1. Work is developed and verified in the team's private dev-cluster.
2. When ready, the team requests promotion to shared pre-prod.
3. Super DevOps (or delegated process) coordinates / validates the promotion.
4. Result is published as a bus event.

### Isolation vs sharing

- Private clusters remain isolated by default.
- Shared pre-prod is the deliberate integration boundary.
- Multiple teams MAY work on the same product over time; pre-prod is where their outputs meet under controlled rules.
