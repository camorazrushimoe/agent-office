# Status

**Date:** 2026-08-22

## Done

### Specification
Architecture, roles, SOULs, composition, lifecycle, handoff, registry, pre-prod lock, deploy guide, MVP scope.

### Runnable Office shell (phase A)
- `docker-compose.yml` — Redis + 4 Office agents + crew/preprod networks
- `Dockerfile.agent` — Compose CLI for staff-engineer / super-devops
- Hermes `config.yaml` + SOUL per agent
- `crew/crew-send.py` — door client
- `crew/office-log.py` — CLI event log
- `crew/publish-event.py` — publish to `office:events` stream
- `crew/agents.example.json`, `.env.example`
- **`HANDOFF-DEVOPS.md`** — instructions for the DevOps agent on hardware

## For DevOps now

Follow **HANDOFF-DEVOPS.md**: clone → `.env` + `agents.json` → `compose build && up` → smoke ping/log/send.

## Still later (not blocking shell deploy)

- Office-attach code in `dev-crew` / `lab-crew` (template contract PRs)
- Lifecycle controller for **team** agents
- Real pre-prod workloads + promotion automation
- Rich role skills beyond SOUL
