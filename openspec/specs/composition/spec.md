# Capability: composition

## Requirements

### Multi-repository system

Agent Office SHALL be composed of:

- The `agent-office` repository (shell, Office agents, shared bus, shared pre-prod, registry)
- One or more **team template** repositories (at minimum `dev-crew` and `lab-crew`)

Team templates SHALL remain separately versioned. Office SHALL NOT require a monorepo of all team code.

### Instantiation

An operator SHALL be able to declare a composition of team instances (count and type of Lab/Dev teams) and spawn instances from pinned template refs without forking Office for each shape.

Each instance SHALL have a unique name and SHALL register with the Office team registry.

### Template contract

A composable team template SHALL:

- Use the Office shared Redis bus (no default private inter-agent Redis when under Office)
- Implement Office-compatible doors and bus events
- Implement agent lifecycle (idle stop + wake-on-demand) for its agent containers
- Remain free of ownership of shared pre-prod
- Be documentable as a template with a clear upgrade/pin story

### Separation of evolution

- Changes to team craft (roles, skills, team workflows) SHOULD land in the team template repository.
- Changes to shell, registry, shared bus protocol, pre-prod ownership, and composition rules SHOULD land in `agent-office`.
- Breaking protocol changes SHALL be coordinated (Office spec + template updates).

### Default v1 shape

The reference composition for v1 is 1 Lab instance + 2 Dev instances. Other shapes MUST remain valid under the same contract.
