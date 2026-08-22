# Status

**Date:** 2026-08-22

## Done

- Core architecture decisions locked
- Four Office roles + SOUL drafts (Architect, Staff Engineer, Scrum Master, Super DevOps)
- Architect owns foundation evolution; Staff Engineer implements it
- Handoff, observability, onboarding documented
- OpenSpec: agent-roles, team-onboarding, foundation-evolution, message-bus, environments, handoff, observability, **agent-lifecycle**
- **Agent lifecycle design**: idle stop (~40m) + wake-on-demand via lifecycle controller + wake-aware send
- Shared bus envelope: `bus/action-schema.json`
- Migration notes for lab/dev crews → Office bus + lifecycle

## Next recommended steps

1. Minimal runnable skeleton (Office agents + shared Redis + lifecycle controller pattern + CLI log + doors)
2. Prototype lifecycle controller + wake-aware crew-send (can start in dev-crew template)
3. Refine pre-prod locking protocol when multiple teams promote
4. First skills for Office agents after skeleton exists

## Open questions still pending

- Exact locking / ownership protocol for shared pre-prod when multiple teams promote
- Whether Lab teams ever need a private cluster of their own
- Whether Office agents themselves use the same idle/wake policy in v1 or stay always-on while few
