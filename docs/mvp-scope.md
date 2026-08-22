# MVP scope — when can we start deploying?

## Spec is “done enough” when

An implementer can build phase A without inventing architecture:

| Area | Status |
|------|--------|
| Roles + SOULs | Done |
| Architecture / composition / multi-repo | Done |
| Bus envelope | Done (`bus/action-schema.json`) |
| Handoff + onboarding | Done |
| Agent lifecycle (idle/wake) | Done (design) |
| Team registry schema | Done (`docs/team-registry.md`) |
| Pre-prod lock protocol | Done (`docs/preprod.md`) |
| Deploy path | Done (`docs/deploy.md`) |
| Observability CLI contract | Done (`docs/observability.md`) |

## Still implementation (not missing product decisions)

These are **code/compose**, not open design questions:

1. `docker-compose.yml` for Office (Redis + 4 agents + ports)
2. `crew/crew-send.py` + `crew/agents.example.json` for Office doors
3. Minimal `office-log` reader on Redis
4. Agent `config.yaml` / Hermes wiring per Office role
5. `.env.example` for secrets
6. Team-side Office-attach (in `dev-crew` / `lab-crew` after template PRs merge)

## Explicit v1 decisions (closed)

| Question | Decision |
|----------|----------|
| Office agents idle/wake? | **Always-on in v1** (only 4 agents). Lifecycle required for **team** agents. |
| Lab private cluster? | **No** by default |
| Pre-prod multi-team writes? | **Global lock** (see `docs/preprod.md`) |
| First deploy shape | Office alone (phase A), then 1 team instance |

## Definition of “can start deploying”

You can start deploying when phase A artifacts exist in the repo (compose + doors + Redis + send + log).  
You can start **using** the multi-team system when at least one team template implements Office-attach and is registered.

Spec for phase A is complete; remaining work is skeleton implementation.
