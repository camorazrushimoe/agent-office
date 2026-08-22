# Status

**Date:** 2026-08-22

## Done

- Core architecture decisions locked
- Four Office roles described (Architect, Staff Engineer, Scrum Master, Super DevOps)
- Architect owns continuous improvement of the factory foundation
- Staff Engineer is the hands-on technical partner of the Architect
- Handoff protocol, observability contract, team onboarding documented
- OpenSpec capability specs for: agent-roles, team-onboarding, foundation-evolution, message-bus, environments, handoff, observability
- Draft SOUL.md for all four Office agents
- Repository foundation docs in place

## Next recommended steps

1. Define concrete message schema under `bus/` (action-schema style)
2. Migration notes: how lab-crew / dev-crew drop local Redis and connect to Office bus
3. Minimal runnable skeleton (Office agents + shared Redis + CLI log + doors)
4. Refine SOULs and add first skills after skeleton exists
5. Resolve open questions on pre-prod locking and Lab environments

## Open questions still pending

- Exact locking / ownership protocol for shared pre-prod when multiple teams promote
- How much change is required in lab-crew and dev-crew to drop their local Redis
- Whether Lab teams ever need a private cluster of their own
