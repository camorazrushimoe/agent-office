# Deploy guide — Agent Office MVP

Goal: bring up a **runnable Office shell** on a single host, then attach team instances.

This is the operator path from zero to “Office is up; teams can be registered”.

## Prerequisites

- Docker + Docker Compose v2
- Git
- Host with enough RAM for Office agents + Redis (team instances add more later)
- Tokens for LLM providers used by Hermes agents (same pattern as dev-crew)

## What “MVP up” means

Minimum healthy Office:

1. Shared Redis bus is reachable
2. Four Office agents have doors (even if some stay always-on in v1)
3. Team registry file exists and can list zero or more teams
4. `office log` (or equivalent) can read bus events
5. An external client can send a signed message to Scrum Master’s door

Team templates (`dev-crew` / `lab-crew`) can be attached **after** this.

## Layout on disk (recommended)

```text
~/factories/
  agent-office/          # this repo (shell)
  instances/
    dev-1/               # checkout of dev-crew @ pin
    lab-1/               # checkout of lab-crew @ pin
  config/
    office-composition.yaml
    team-registry.yaml
```

Secrets stay out of git (`.env`, `crew/agents.json`, tokens).

## Step 1 — Clone and configure Office

```bash
git clone https://github.com/camorazrushimoe/agent-office.git
cd agent-office
cp .env.example .env          # when present
cp crew/agents.example.json crew/agents.json   # door URLs + HMAC secrets
```

Fill:

- LLM / Hermes credentials (per agent or shared, as you use in dev-crew)
- Door secrets for architect, staff-engineer, scrum-master, super-devops
- `OFFICE_BUS_URL` (default `redis://shared-memory:6379` inside compose network)

## Step 2 — Start Office shell

```bash
docker compose up -d
```

Expected services (MVP):

| Service | Role |
|---------|------|
| `shared-memory` | Redis bus |
| `architect` | Office agent |
| `staff-engineer` | Office agent |
| `scrum-master` | Office agent |
| `super-devops` | Office agent |
| `event-log` (optional process) | CLI-friendly tail of bus events |

Health checks: Redis PING; each agent door accepts signed POST (202).

## Step 3 — Smoke Office alone

```bash
python3 crew/crew-send.py scrum-master "ping: Office up?"
# expect 202

python3 crew/office-log.py --follow   # or: office log --follow
```

Publish a test event on the bus and confirm it appears in the log.

## Step 4 — Composition file

Create `config/office-composition.yaml` (see `docs/composition.md`):

```yaml
office:
  bus_url: redis://shared-memory:6379
  preprod_network: agent-office-preprod

teams:
  - name: lab-1
    type: lab
    template:
      repo: https://github.com/camorazrushimoe/lab-crew.git
      ref: main
    instance_dir: ../instances/lab-1
  - name: dev-1
    type: dev
    template:
      repo: https://github.com/camorazrushimoe/dev-crew.git
      ref: main
    instance_dir: ../instances/dev-1
  - name: dev-2
    type: dev
    template:
      repo: https://github.com/camorazrushimoe/dev-crew.git
      ref: main
    instance_dir: ../instances/dev-2
```

Reference v1 shape: **1 Lab + 2 Dev**. Fewer teams is fine for first bring-up.

## Step 5 — Spawn a team instance (manual until CLI exists)

```bash
mkdir -p ../instances
git clone --branch main https://github.com/camorazrushimoe/dev-crew.git ../instances/dev-1
cd ../instances/dev-1
# configure Office-attach: BUS URL, TEAM_NAME=dev-1, door secrets, networks
docker compose up -d
```

Team must implement Office template contract (`docs/office-template.md` in team repo). Until that code lands, instance may run in standalone mode for template development only — **not** full Office integration.

## Step 6 — Register the team

Add entry to `config/team-registry.yaml` (schema in `docs/team-registry.md`).

Smoke:

- Wake path (when lifecycle exists): send to a stopped agent → starts → 202
- Event from team appears on Office bus / CLI log
- Scrum Master can name the team in status answers

## Step 7 — Pre-prod (Dev only)

- Create Docker network `agent-office-preprod` (or name from composition)
- Super DevOps owns promotion rules (`docs/preprod.md`)
- Dev instance private cluster stays separate; promote only via documented path

## Order of implementation vs deploy

| Phase | You can deploy | Blocked on |
|-------|----------------|------------|
| A | Office Redis + 4 agents + doors + CLI log | Compose + agent images + secrets |
| B | Register teams (even if manual) | Registry file + endpoints |
| C | Full Office-attach team instances | Team template code (bus + lifecycle) |
| D | Pre-prod promotions | Pre-prod network + Super DevOps procedures |

**Start with phase A.** Phases C–D need team-repo implementation PRs after template-contract merge.

## Networks (naming)

| Network | Purpose |
|---------|--------|
| `agent-office-crew` | Office agents + Redis |
| `agent-office-preprod` | Shared pre-prod (external for team composes) |
| per Dev instance `*-dev-env` | Private sandbox (team-owned) |

Team composes attach to Office Redis network (or reach Redis via published port / external network).

## Failure checklist

- Door 401/403 → HMAC secret mismatch
- Cannot reach Redis from team → network / URL wrong
- Agent never wakes → lifecycle controller not running or docker.sock missing
- Events missing in CLI log → not publishing to Office bus or wrong stream key

## Related docs

- `docs/composition.md` — multi-repo shape
- `docs/team-registry.md` — registry schema
- `docs/preprod.md` — promotion lock rules
- `docs/agent-lifecycle.md` — idle/wake
- `docs/onboarding-team.md` — admitting a new team
