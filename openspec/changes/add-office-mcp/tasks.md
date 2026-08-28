# Tasks — add-office-mcp

## This PR (specification only)

- [x] GitHub issue describing the facade (#18)
- [x] OpenSpec change proposal + design + capability spec
- [x] `docs/office-mcp.md`
- [x] README pointer, reserved port, key decision

## Follow-up implementation PR (not this change)

- [ ] `office/mcp` server implementing resources + tools in the spec
- [ ] Compose service `office-mcp` (`restart: unless-stopped`, host 8760)
- [ ] Wire send through existing wake-aware door path
- [ ] Readiness via `manage_tokens.py` without accepting raw secrets
- [ ] `plan_onboard` / `apply_onboard` against registry + instance layout
- [ ] Smoke hook that lists tools and reads `office://manifest`
- [ ] Client snippet for Hermes/Grok MCP config
