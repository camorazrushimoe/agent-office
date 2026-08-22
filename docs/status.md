# Status

**Date:** 2026-08-22

## Done (specification)

- Architecture, roles, SOULs, handoff, observability, lifecycle, composition
- Multi-repo model (Office shell + team templates)
- Bus envelope, migration notes, onboarding
- **Deploy guide** (`docs/deploy.md`)
- **Team registry schema** (`docs/team-registry.md`)
- **Pre-prod lock protocol** (`docs/preprod.md`) — global lock v1
- **MVP scope** (`docs/mvp-scope.md`) — closed open questions
- Example config: composition, registry, agents doors, `.env.example`

## Closed decisions

- Office agents: **always-on in v1**
- Lab: **no private cluster by default**
- Pre-prod: **single global promotion lock**
- First deploy: **Office phase A**, then attach teams

## Remaining to actually run (implementation)

1. `docker-compose.yml` + agent images for Office shell
2. `crew-send` + `office-log` scripts
3. Hermes `config.yaml` per Office agent
4. Merge template-contract PRs and implement Office-attach in `dev-crew` / `lab-crew`

Spec for starting implementation/deploy of the **shell** is complete.
