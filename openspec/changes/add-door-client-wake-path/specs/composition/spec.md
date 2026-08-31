# composition — canonical crew toolkit

## MODIFIED Requirements

### Requirement: Template contract

A composable team template SHALL:

- Use the Office shared Redis bus (no default private inter-agent Redis when
  under Office)
- Implement Office-compatible doors and bus events
- Implement agent lifecycle (idle stop + wake-on-demand) for its agent
  containers
- **Ship the canonical crew toolkit**: every instance's `crew/` directory
  SHALL contain the canonical `crew-send.py`, `FACTORY-STANDARD.md`, and
  `agents.json`, and that directory SHALL be mounted into every agent
  container at `/opt/crew`. The door client SHALL be a single canonical
  implementation shared by Office and all team instances — a missing client,
  or a per-instance copy-paste variant that diverges from the canonical client,
  is a spec violation. The canonical client is the one that implements the
  wake-on-delivery contract in `agent-lifecycle`.
- Remain free of ownership of shared pre-prod
- Be documentable as a template with a clear upgrade/pin story
