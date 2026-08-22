# Status

**Date:** 2026-08-22

## Done

- Core architecture decisions locked
- Four Office roles described (Architect, Staff Engineer, Scrum Master, Super DevOps)
- Architect explicitly owns continuous improvement of the factory foundation
- Staff Engineer added as hands-on technical partner of the Architect
- Handoff protocol sketched
- Observability contract for CLI event log defined
- Team onboarding process documented
- Repository created and populated with foundation docs

## Next recommended steps

1. Flesh out OpenSpec capability specs (`agent-roles`, `message-bus`, `environments`, `handoff`, `observability`, `team-onboarding`, `foundation-evolution`)
2. Draft SOUL.md for all four Office agents
3. Define the concrete message schema under `bus/`
4. Decide how existing lab-crew / dev-crew instances will connect to the shared bus (migration notes)
5. Minimal runnable skeleton (Office agents + shared Redis + CLI log)

## Open questions still pending

- Exact locking / ownership protocol for shared pre-prod when multiple teams promote
- How much change is required in lab-crew and dev-crew to drop their local Redis
- Whether Lab teams ever need a private cluster of their own
