# Deploy guide — Agent Office MVP

Primary operator brief: **[HANDOFF-DEVOPS.md](../HANDOFF-DEVOPS.md)**.

Goal: bring up a **runnable Office shell** on a single host, then attach team instances later.

## Prerequisites

- Docker + Docker Compose v2
- Git
- LLM API key (`CUSTOM_API_KEY`) matching `agents/*/hermes-home/config.yaml`

## What “MVP up” means

1. Shared Redis bus reachable (host **6380**)
2. Four Office agents with doors (**8751–8754**)
3. `crew/office-log.py` can read `office:events`
4. Signed message to Scrum Master returns success (typically 202)

## Steps

```bash
git clone https://github.com/camorazrushimoe/agent-office.git
cd agent-office
cp .env.example .env
# edit CUSTOM_API_KEY=

cp crew/agents.example.json crew/agents.json
# secrets already match config.yaml in the example

docker compose build
docker compose up -d

redis-cli -p 6380 ping
python3 crew/publish-event.py agent.online system "office shell up"
python3 crew/office-log.py --count 5
python3 crew/crew-send.py scrum-master "ping: deploy smoke"
```

## Services

| Service | Role | Host port |
|---------|------|-----------|
| `shared-memory` | Redis bus | 6380 |
| `architect` | Office agent | 8751 |
| `staff-engineer` | Office agent (+ docker.sock) | 8752 |
| `scrum-master` | Office agent | 8753 |
| `super-devops` | Office agent (+ docker.sock) | 8754 |

Networks: `agent-office-crew`, `agent-office-preprod`.

## Phase B+ (teams)

After shell is healthy, spawn team instances from composition config (`config/office-composition.example.yaml`) using template contract in team repos. Requires Office-attach implementation in those templates.

## Related

- `docs/composition.md`, `docs/team-registry.md`, `docs/preprod.md`, `docs/agent-lifecycle.md`
