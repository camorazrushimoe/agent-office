# Agent Office — Standard

This is the meta-factory. It does not build products itself. It decides *where* work should happen, keeps the portfolio coherent, makes the whole system observable, and continuously improves the factories.

## Golden rules

1. **No silent work**  
   Every significant action (new project, handoff, promotion to pre-prod, architectural decision, foundation change, override) must leave a trace that Scrum Master can surface.

2. **Teams stay specialized**  
   Lab Crew does research. Dev Crew builds software. Office does not turn into a third product-implementation team.

3. **One bus to rule them all**  
   There is a single Redis bus at Office level. Teams do not run their own message bus.

4. **Private sandbox, shared gate**  
   Each Dev team owns its private dev-cluster. The shared pre-prod is the only integration / release-candidate environment and is owned by Super DevOps.

5. **Any-to-any is allowed, primary path is clear**  
   Any agent may address any other agent. The recommended human entry point is Scrum Master.

6. **External agent is first-class**  
   The human works through an external Hermes agent that has the same rights to address internal agents as any Office agent.

7. **Foundation is also a product**  
   Improving Agent Office and the crew factories themselves is first-class work, led by Architect + Staff Engineer.

8. **Agents sleep when idle; wake is part of send**  
   Agent containers that have no work for the configured idle period are stopped. Delivering a message to an agent MUST wake it if needed, wait until healthy, then deliver. Work must not be silently lost because the target was stopped. See `docs/agent-lifecycle.md`.

9. **Linear is the source of truth for work**  
   Every team tracks its work in Linear (Projects + tickets). The human and Scrum Master read live status from there. See `docs/linear-workflow.md`.

10. **GitHub discipline is universal**  
    Every agent, in every team, follows the same GitHub foundation rules: feature branch → PR → review → merge, never push to `main`, never self-merge. See `docs/github-workflow.md`.

11. **Credential discovery** — when an agent needs `GITHUB_TOKEN`, `LINEAR_API_KEY`, etc., it checks the **process environment first** (`printenv`), not dotfiles; commented-out lines mean "absent". See `docs/credential-discovery.md`.

## What Office is responsible for

- Portfolio of projects and their current stage
- Routing: idea → Lab or Dev (and which instance)
- Observability of the whole system via the shared bus + CLI event log
- Stability of the shared pre-prod
- Architectural coherence across projects and across the factory itself
- Process hygiene (helping teams keep work understandable)
- Continuous evolution of the factory foundation (new capabilities, better protocols, structural improvements)
- Onboarding of new teams according to the documented process
- Lifecycle policy for agent containers across team factories

## What Office is *not* responsible for

- Writing product (customer) code as its main job
- Running the private dev-clusters of the teams
- Owning the product OpenSpec or Linear projects of individual products
- Replacing the specialized skills of Lab or Dev agents for normal project work

## Handoff discipline

- Lab → Office: Research Package (or explicit “not worth building”)
- Office → Dev: clear assignment + context + link to Research Package / specs
- Dev → Office: status, blockers, promotion requests to pre-prod
- All handoffs are visible on the bus and queryable by Scrum Master

## Foundation changes

Changes to Agent Office or to the Lab/Dev crew templates follow the same discipline as any important work:

- Clear intent and (when non-trivial) a short design
- Visible on the bus / event log
- Reviewed with appropriate depth (Architect + Staff Engineer)
- Documented so future teams inherit the improvement

## Escape hatch

In a critical situation the human (via external agent) or Scrum Master MAY override normal routing or process.  
Every override SHALL be recorded as an explicit event and, if it creates technical debt, as a tracked item (GitHub issue or Linear ticket labelled accordingly).

## Language

Work in English — code, commits, tickets, reports, bus events, CLI output.
