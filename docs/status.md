# Status

**Date:** 2026-08-22

## Done

- Core architecture decisions locked
- Four Office roles + SOUL drafts
- Handoff, observability, onboarding, agent lifecycle documented
- OpenSpec core capabilities including **composition** and **agent-lifecycle**
- Shared bus envelope `bus/action-schema.json`
- Migration notes for lab/dev → Office bus + lifecycle
- **Multi-repo composition model** (`docs/composition.md`): Office shell + instantiable team templates
- Template-contract PRs opened against `dev-crew` and `lab-crew`

## Next recommended steps

1. Merge template-contract docs in team repos; implement Office-attach code incrementally
2. Minimal runnable skeleton (Office agents + shared Redis + lifecycle pattern + CLI log)
3. Composition CLI / spawn script (optional after skeleton)
4. Pre-prod locking protocol when multiple Dev instances promote

## Open questions still pending

- Exact locking / ownership protocol for shared pre-prod when multiple teams promote
- Whether Lab teams ever need a private cluster of their own
- Whether Office agents themselves use idle/wake in v1 or stay always-on while few
