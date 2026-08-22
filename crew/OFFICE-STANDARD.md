# Agent Office — Standard

This is the meta-factory. It does not build products itself. It decides *where* work should happen, keeps the portfolio coherent, and makes the whole system observable.

## Golden rules

1. **No silent work**  
   Every significant action (new project, handoff, promotion to pre-prod, architectural decision, override) must leave a trace that Scrum Master can surface.

2. **Teams stay specialized**  
   Lab Crew does research. Dev Crew builds software. Office does not turn into a third implementation team.

3. **One bus to rule them all**  
   There is a single Redis bus at Office level. Teams do not run their own message bus.

4. **Private sandbox, shared gate**  
   Each Dev team owns its private dev-cluster. The shared pre-prod is the only integration / release-candidate environment and is owned by Super DevOps.

5. **Any-to-any is allowed, primary path is clear**  
   Any agent may address any other agent. The recommended human entry point is Scrum Master.

6. **External agent is first-class**  
   The human works through an external Hermes agent that has the same rights to address internal agents as any Office agent.

## What Office is responsible for

- Portfolio of projects and their current stage
- Routing: idea → Lab or Dev (and which instance)
- Observability of the whole system via the shared bus + CLI event log
- Stability of the shared pre-prod
- Architectural coherence across projects and across the factory itself
- Process hygiene (helping teams keep work understandable)

## What Office is *not* responsible for

- Writing product code
- Running the private dev-clusters of the teams
- Owning the product OpenSpec or Linear projects of individual products
- Replacing the specialized skills of Lab or Dev agents

## Handoff discipline

- Lab → Office: Research Package (or explicit “not worth building”)
- Office → Dev: clear assignment + context + link to Research Package / specs
- Dev → Office: status, blockers, promotion requests to pre-prod
- All handoffs are visible on the bus and queryable by Scrum Master

## Escape hatch

In a critical situation the human (via external agent) or Scrum Master MAY override normal routing or process.  
Every override SHALL be recorded as an explicit event and, if it creates technical debt, as a tracked item (GitHub issue or Linear ticket labelled accordingly).

## Language

Work in English — code, commits, tickets, reports, bus events, CLI output.
