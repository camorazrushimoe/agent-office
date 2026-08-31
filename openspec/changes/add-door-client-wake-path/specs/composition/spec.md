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
  SHALL contain `FACTORY-STANDARD.md` (instance-specific) and `agents.json`
  (per-instance secret config derived from `tokens.yaml`, gitignored), and
  that directory SHALL be mounted into every agent container at `/opt/crew`.
  The door client SHALL be a single canonical implementation —
  `crew/crew-send.py` at the Office repo root — delivered to every agent
  container as a read-only mount of that file at `/opt/crew/crew-send.py`
  (alongside the per-instance `crew/` mount). Instances SHALL NOT ship their
  own copy of the client; where a copy already exists it SHALL be
  byte-identical to the canonical file, verified by SHA-256 at
  instantiation/sync, and removed in favor of the mount. A missing client, or
  a per-instance copy that diverges from the canonical client, is a spec
  violation. The canonical client is the one that implements the
  wake-on-delivery contract in `agent-lifecycle`.
- Remain free of ownership of shared pre-prod
- Be documentable as a template with a clear upgrade/pin story
