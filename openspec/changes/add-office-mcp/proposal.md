# Change: add Office MCP facade

## Why

An external agent that clones Agent Office today has to learn Redis ports,
door URLs, registry YAML, wake rules, and the token file layout before it
can say hello to Scrum Master. That knowledge is tribal and does not survive
"clone the shell and attach Hermes/Grok".

The internal machinery already exists (shared bus, doors, factory-control,
team registry, `crew-send.py`, `manage_tokens.py`, `scripts/smoke.py`).
What is missing is a **small, always-on MCP server** that comes up with the
factory and exposes a stable facade: orient, talk, onboard.

MCP MUST NOT become a second bus. It wraps current sources of truth.

Tracked by GitHub issue #18.

## What Changes

- New capability `office-mcp`.
- Operator-facing document `docs/office-mcp.md`.
- README pointer + reserved host port for the future compose service.
- OpenSpec change record (this folder) so implementation has a contract.

Out of scope for this change (follow-up implementation PR):

- `office/mcp` Python package
- `docker-compose.yml` service `office-mcp`
- smoke level that probes MCP tools

## Decisions locked in this spec

| Topic | Choice |
|-------|--------|
| Lifecycle | Always-on compose service, starts with `docker compose up -d` |
| Send | Wake-aware ack + optional short wait for first bus event |
| Onboard | `plan_onboard` / `apply_onboard`; one plan may create N instances |
| Secrets | Presence/scope only; no raw tokens in tool arguments |
| Default entry | Scrum Master |

## Impact

- New spec: `openspec/specs/office-mcp/spec.md`
- New doc: `docs/office-mcp.md`
- README documentation map + key decisions + reserved port **8760**
- Related existing specs (no text change required yet): `team-onboarding`,
  `message-bus`, `agent-lifecycle`, `composition`
