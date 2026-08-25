# Handoff for DevOps — deploy Agent Office shell

You are deploying the **Agent Office shell** (not full multi-team product yet).

Repo: https://github.com/camorazrushimoe/agent-office

## Goal

On target hardware:

1. `docker compose up -d` succeeds
2. Redis answers on host port **6380**
3. Four agent doors accept signed POSTs on **8751–8754**
4. `crew/office-log.py` can read the bus
5. Optional: send a message to `scrum-master` and see the gateway accept it (202)

Team instances (`dev-crew` / `lab-crew`) are **out of scope** for this first deploy unless Office-attach code already exists in those templates.

## Prerequisites

- Docker Engine + Docker Compose v2
- Git
- Outbound network to pull `redis:7-alpine` and `nousresearch/hermes-agent:latest`
- LLM API key for Hermes (put it in `tokens/tokens.yaml` under `llm.factories.office`)

## Steps

```bash
git clone https://github.com/camorazrushimoe/agent-office.git
cd agent-office

cp tokens/tokens.example.yaml tokens/tokens.yaml
# Fill in llm.factories.office, github.token, linear.api_key.
# Or consolidate from an existing .env:
python3 office/manage_tokens.py migrate
python3 office/manage_tokens.py check
python3 office/manage_tokens.py derive-agents

# Build images that need Docker Compose CLI (staff-engineer, super-devops)
docker compose build

docker compose up -d

docker compose ps
redis-cli -p 6380 ping    # PONG

python3 crew/publish-event.py agent.online system "office shell up"
python3 crew/office-log.py --count 5

python3 crew/crew-send.py scrum-master "ping: Office deploy smoke test"
```

## Ports

| Service | Host port |
|---------|-----------|
| Redis | 6380 |
| architect | 8751 |
| staff-engineer | 8752 |
| scrum-master | 8753 |
| super-devops | 8754 |

Chosen to avoid clashing with a local **dev-crew** (6379 / 8651–8654).

## Networks created

- `agent-office-crew` — Office agents + Redis
- `agent-office-preprod` — empty shared pre-prod network for later team attach

## Expected containers

- `agent-office-shared-memory`
- `agent-office-architect`
- `agent-office-staff-engineer`
- `agent-office-scrum-master`
- `agent-office-super-devops`

## Common failures

| Symptom | Check |
|---------|--------|
| Image pull fail | Registry access / mirror for Docker Hub |
| Door 401 | `crew/agents.json` secret ≠ `tokens.yaml` door (re-run `office/manage_tokens.py derive-agents`) |
| Door connection refused | `docker compose ps`, port bind, firewall |
| Agent crash loop | Logs: `docker logs agent-office-scrum-master` — often missing API key |
| office-log empty | Normal until events published; try `publish-event.py` |
| UID issues | Set `HERMES_UID` / `HERMES_GID` in `.env` to match host user if volume perms fail |

## What success looks like

- All five containers healthy / running
- `redis-cli -p 6380 ping` → PONG
- `publish-event` + `office-log` show the event
- `crew-send.py scrum-master "..."` returns HTTP 202 (or documented Hermes success)

## Spec references (read if stuck)

- `docs/deploy.md` — full deploy path
- `docs/secrets.md` — secrets single-source + rotation runbook
- `docs/mvp-scope.md` — what is in / out of MVP
- `docs/composition.md` — multi-repo later
- `docs/preprod.md` — pre-prod rules (not required for shell-only smoke)

## Report back

Please report: host OS, `docker compose ps`, result of ping/send/log, and any log errors from agents.
