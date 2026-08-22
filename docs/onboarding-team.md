# Onboarding a New Team into Agent Office

This document describes how to create or connect a new agent team (Lab or Dev style) so that it becomes a first-class citizen of the Agent Office.

## Goal

A new team must:

1. Be visible to Office agents (especially Scrum Master and Architect)
2. Connect to the **single shared Redis bus**
3. Follow the Office standards (handoff, observability, promotion rules)
4. Have a clear identity in the team registry
5. (For Dev teams) be able to promote work into the shared pre-prod under Super DevOps rules

## Types of teams

| Type | Typical source | Private environment |
|------|----------------|---------------------|
| Lab | `lab-crew` template | Usually lightweight workspace only |
| Dev | `dev-crew` template | Own private dev-cluster |
| Future specialized | New factory template | Defined case by case |

## High-level process

```text
1. Decide type + purpose of the new team
2. Create / clone the team foundation (from lab-crew or dev-crew)
3. Adapt the team to Office rules (drop local Redis, connect to shared bus)
4. Register the team in Agent Office
5. Smoke-test connectivity and handoff
6. Announce the team as available
```

### 1. Decide type and purpose

- What kind of work will this team do?
- Is it a permanent capacity or a temporary experiment?
- Who will be the primary Office contact for it? (usually Scrum Master)

### 2. Create the team foundation

- Prefer starting from the existing `lab-crew` or `dev-crew` repositories.
- Keep the separation of concerns: foundation vs instance config vs project work.
- Give the team a clear, unique name (e.g. `dev-crew-2`, `lab-crew-alpha`).

### 3. Adapt to Agent Office rules (critical)

The team **must**:

- **Stop running its own Redis.** All agents connect to the Office shared bus.
- Expose the same style of webhook doors (HMAC-signed).
- Publish the required high-level events (see `docs/handoff-protocol.md` and `docs/observability.md`).
- For Dev teams: implement the promotion path into shared pre-prod according to Super DevOps rules.
- Keep its private dev-cluster (if any) truly private and owned by the team.

Recommended checklist for the team maintainers (Architect / Staff Engineer can help):

- [ ] Local Redis removed or disabled
- [ ] Bus connection points to Office Redis
- [ ] Door registry and secrets follow Office conventions
- [ ] Required bus events are emitted
- [ ] Health endpoint works
- [ ] (Dev) Promotion procedure documented and tested against pre-prod

### 4. Register the team in Agent Office

Add an entry to the team registry (location TBD in implementation — config or dedicated registry service):

```yaml
# example shape
name: dev-crew-2
type: dev
foundation: https://github.com/camorazrushimoe/dev-crew
endpoints:
  doors: ...
  health: ...
capacity_notes: "..."
owner_contact: scrum-master  # or specific human
```

Office agents (especially Scrum Master) must be able to discover the new team without manual tribal knowledge.

### 5. Smoke-test

Minimum tests before declaring the team ready:

- Office can send a message to any agent of the new team and receive a reply
- The team can publish a test event on the shared bus and it appears in the Office CLI log
- (Dev) A dry-run promotion request reaches Super DevOps
- Scrum Master can answer “what is the status of this new team?”

### 6. Announce

- Publish a clear event / note that the team is online and available for assignment
- Update any portfolio or capacity view that Scrum Master uses

## Who does what during onboarding

| Step | Primary owner |
|------|----------------|
| Decide that a new team is needed | Human + Scrum Master / Architect |
| Create / adapt the foundation | Architect + Staff Engineer (with possible help from Super DevOps) |
| Wire to shared bus & doors | Staff Engineer + team agents |
| Register in Office | Scrum Master (or automated) |
| Validate promotion path | Super DevOps |
| Final “ready for work” | Scrum Master |

## Anti-patterns

- Spinning up a team that still has its own Redis “for now”
- Forgetting to register the team → invisible capacity
- Allowing a new Dev team to write directly into pre-prod without Super DevOps rules
- Treating onboarding as pure infrastructure work and skipping the observability contract

## Future evolution

Later the Architect and Staff Engineer may turn this process into a more automated “spawn team” capability of the Office itself. Until then this document is the source of truth.
