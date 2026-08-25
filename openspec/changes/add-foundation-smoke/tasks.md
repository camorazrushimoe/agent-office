# Tasks — add-foundation-smoke

## 1. Spec (this PR)
- [x] proposal.md
- [x] openspec/specs/foundation-smoke/spec.md (new capability)
- [x] change delta under openspec/changes/add-foundation-smoke/specs/

## 2. Implementation (this PR)
- [x] `scripts/smoke.py` — hierarchical CLI (levels 0–3)
      - static: paths, schema JSON, agents.json presence
      - infra: Redis PING, docker containers for shared-memory +
        factory-control + office agents
      - bus: XADD smoke event + XREVRANGE / office-log style readback
      - doors: optional wake via inbox + door POST (crew-send path),
        assert 2xx, no LLM wait
      - flags: `--level`, `--agents`, `--no-wake`, `--json`, `--url`
      - clear non-zero exit + human-readable failure reason
- [x] `scripts/smoke.sh` — thin executable wrapper
- [x] README: one-line pointer under Quick start

## 3. Validation (manual / review)
- [ ] Level 0 alone succeeds on a clean checkout (agents.json may be missing
      → clear message)
- [ ] With `docker compose up -d`: full smoke (level 3) exits 0
- [ ] With an agent stopped: smoke wakes it and door returns 2xx
- [ ] `--no-wake` fails clearly if the target container is stopped
- [ ] Events from the smoke run appear in `python3 crew/office-log.py`
