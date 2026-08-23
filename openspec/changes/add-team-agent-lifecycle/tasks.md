# Tasks: add-team-agent-lifecycle

## 1. Controller
- [ ] 1.1 Docker-API client over unix socket (inspect/start/stop)
- [ ] 1.2 Project-label scoping (COMPOSE_PROJECT filter)
- [ ] 1.3 Wake path: inbox subscribe → idempotent start → health wait → events
- [ ] 1.4 Idle reaper: last_active + busy-lock checks → stop → agent.stopped
- [ ] 1.5 Events via publish_event() (durable stream + live topic)

## 2. Bus client alignment with upstream contract
- [ ] 2.1 publish_event() XADDs to office:events stream (upstream log format)
- [ ] 2.2 PING watchdog on subscriber connections (idle timeout hardening)

## 3. Verification
- [ ] 3.1 Unit: envelope validation, duration parsing, RESP round-trip
- [ ] 3.2 Integration vs local Redis: wake → started event visible in crew/office-log.py
- [ ] 3.3 Idle stop fires after shortened IDLE_TIMEOUT in a scratch compose project

## 4. Review gate (SDD process)
- [ ] 4.1 PR opened; adversarial review per involved agents' lenses
- [ ] 4.2 Spec deltas merged only after approvals
