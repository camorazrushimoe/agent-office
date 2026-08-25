# Tasks — add-factory-control-service

## 1. Spec (this PR)
- [x] proposal.md
- [x] specs/agent-lifecycle/spec.md delta (MODIFIED requirements)

## 2. Implementation (follow-up PR after spec approval)
- [ ] `office/registry/factory-agents.json` — registry: agent id → container
      name + log path (exhaustive allowlist)
- [ ] `office/lifecycle/factory_control.py` — supervisor:
      - idle reaper (40m default, log-based signal, mtime fallback,
        busy-lock respect, fail-open)
      - wake listener on `office:inbox:*` (idempotent, health check after
        start, `agent.wake_failed` on timeout)
      - durable events via `publish_event`
- [ ] `Dockerfile.factory-control` — slim image: python3 + docker CLI
- [ ] `docker-compose.yml`: add always-on `factory-control` service
      (`restart: unless-stopped`, docker.sock mount, repo read-only mount,
      env knobs)
- [ ] `.env.example`: `IDLE_TIMEOUT=40m`, `CHECK_INTERVAL=120s`,
      `WAKE_TIMEOUT=90s`
- [ ] Decommission `office/lifecycle/docker_controller.py` (delete in the
      same PR that ships factory-control; tracked here per review #6)
- [ ] Update `docs/agent-lifecycle.md` runtime notes to match spec

## 3. Validation
- [ ] Dry-run: reaper lists would-stop agents, touches nothing
- [ ] Live: stops an idle agent >40m; leaves a busy agent alone
- [ ] Wake: `agent.wake` starts a stopped agent; door responds after start
- [ ] Events visible via `crew/office-log.py` replay
