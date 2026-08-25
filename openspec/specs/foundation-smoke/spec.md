# Capability: foundation-smoke

## Purpose

Provide a **fast, hierarchical smoke test** of the Agent Office shell foundation.
After local foundation changes (agents, bus, compose, factory-control, skills
mounts, config render), operators and agents SHALL be able to confirm that the
shared infrastructure and Office agents are still coherent enough to operate.

The smoke test is a gate, not a full system test. It does **not** exercise
LLM behaviour, Linear/GitHub live APIs, team-instance pipelines, or product
work.

## Requirements

### Hierarchical levels

The system SHALL expose levels that can be run independently. Higher levels
include the checks of lower levels.

| Level | Name | Checks |
|-------|------|--------|
| 0 | Static | Required repository paths exist; `bus/action-schema.json` is valid JSON; Office agents registry (`crew/agents.json`) is present or the operator is told to copy the example |
| 1 | Infra | Shared Redis is reachable (default host `127.0.0.1:6380`); `factory-control` and `shared-memory` containers exist; Office agent containers are known to Docker |
| 2 | Bus | A smoke event can be published to the durable `office:events` stream and read back |
| 3 | Doors + lifecycle | For each selected Office agent: if the container is not running, a wake is requested (unless disabled); after the container is Running, a signed door POST returns HTTP 2xx. The test MUST NOT wait for an LLM reply |

Default run SHALL execute through level 3.

### Speed and cost

- A full successful run SHOULD complete in under 90 seconds on a normal host
  when agents are already warm; cold wake of several agents may take longer
  but MUST respect the same wake timeout used by factory-control (default 90s
  per agent).
- The smoke test MUST NOT call external LLM providers as part of the assertion
  path. Door acceptance (2xx) is sufficient.

### Observability

- The smoke run SHOULD publish start and completion events on the Office bus
  (`actor=smoke` or similar) so the run is visible via `crew/office-log.py`.
- Failures MUST print a clear human-readable reason and exit non-zero.

### CLI contract

- Entry point: `scripts/smoke.py` (wrapper `scripts/smoke.sh` optional).
- Flags that SHOULD be supported:
  - `--level N` — run up to level N (0–3)
  - `--agents a,b,...` — restrict door checks to named Office agents
  - `--no-wake` — do not request wake; fail if a required agent container is stopped
  - `--url` — override `OFFICE_BUS_URL` (default `redis://127.0.0.1:6380`)
  - `--json` — machine-readable summary on stdout

### What is out of scope (v1)

- Smoke tests for team instances (`lab-1`, `spec-1`, `dev-1`)
- Live Linear or GitHub API calls
- Waiting for agent LLM responses or tool execution
- Full Idea → Lab → Spec → Dev pipeline
- Production / pre-prod promotion checks beyond container presence

### Relation to other capabilities

- Uses the single shared bus (`message-bus`)
- Respects agent idle/wake behaviour (`agent-lifecycle` / factory-control)
- Does not modify agent roles or composition rules
