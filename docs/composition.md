# Composition model — Agent Office + team templates

Agent Office is not a single repository. It is a **multi-repo system**:

| Repository | Role |
|------------|------|
| [agent-office](https://github.com/camorazrushimoe/agent-office) | Shell: Office agents, shared Redis bus, shared pre-prod, registry, composition rules |
| [dev-crew](https://github.com/camorazrushimoe/dev-crew) | **Template** for a Dev team instance |
| [lab-crew](https://github.com/camorazrushimoe/lab-crew) | **Template** for a Lab team instance |

Teams are developed and versioned independently. Office is assembled by instantiating as many team templates as needed.

## Operator mental model

```text
1. Clone agent-office
2. Bring up Office layer (Office agents + shared Redis + pre-prod + policies)
3. Declare desired shape, e.g.:
     teams:
       - name: dev-1
         template: dev-crew
         ref: v0.x
       - name: dev-2
         template: dev-crew
         ref: v0.x
       - name: lab-1
         template: lab-crew
         ref: v0.y
4. Spawn instances from templates (clone/checkout ref → instance dir → compose up)
5. Register instances in Office team registry
```

Examples of valid configurations:

- 1 Lab + 2 Dev (default v1 intent)
- 4 Dev only
- 2 Lab + 1 Dev
- any mix that the operator can resource

## Template vs instance

| Concept | Meaning |
|---------|--------|
| **Template** | Git repository (`dev-crew` / `lab-crew`) at a pinned tag or commit |
| **Instance** | A running copy: unique name, own private env (for Dev), own agent containers, connected to **this** Office’s bus and pre-prod |

Many instances may share the same template version. Improving the template (PR in `dev-crew` or `lab-crew`) does not automatically change running instances until they are upgraded.

## What lives where

### agent-office (shell)

- Architect, Staff Engineer, Scrum Master, Super DevOps
- Single shared Redis bus
- Shared pre-prod
- Team registry + portfolio routing
- Composition config and deploy conventions
- Office-level observability (CLI event log)
- Foundation evolution of the **system** (how modules plug in)

### dev-crew / lab-crew (templates)

- Agent roles, SOULs, skills for that team type
- Private dev-cluster definition (Dev only)
- Webhook doors + wake-aware send client
- Lifecycle controller for **this instance’s** agent containers
- Team-local docs and OpenSpec for the team’s craft

Templates **do not** own:

- A private Redis for inter-agent traffic (use Office bus)
- Shared pre-prod (Office / Super DevOps)
- Portfolio routing across teams (Office)

## Template contract (must implement)

Any crew template that can be composed under Office SHALL:

1. Connect agents to an **external** Redis URL (Office bus); no default local bus.
2. Expose HMAC webhook doors compatible with Office send conventions.
3. Emit Office-compatible bus events (see `bus/action-schema.json`), with team-qualified actors when needed.
4. Provide **lifecycle**: idle stop + wake-on-demand for agent containers (`docs/agent-lifecycle.md`).
5. Use `restart: "no"` (or equivalent) for agent services; always-on only for lifecycle + anything that must not sleep.
6. Register (or be registrable) with name, type, endpoints, template ref.
7. For Dev: keep private dev-cluster; promote to Office pre-prod only via Super DevOps rules.

Full migration notes: `docs/migration-teams-to-office-bus.md`.  
Onboarding checklist: `docs/onboarding-team.md`.

## Composition config (shape)

Canonical config lives in Office instance config (gitignored secrets elsewhere). Example shape:

```yaml
# office-composition.example.yaml
office:
  bus_url: redis://office-shared-memory:6379
  preprod_network: agent-office-preprod

teams:
  - name: dev-1
    type: dev
    template:
      repo: https://github.com/camorazrushimoe/dev-crew.git
      ref: main   # prefer tags in production
    instance_dir: instances/dev-1

  - name: dev-2
    type: dev
    template:
      repo: https://github.com/camorazrushimoe/dev-crew.git
      ref: main
    instance_dir: instances/dev-2

  - name: lab-1
    type: lab
    template:
      repo: https://github.com/camorazrushimoe/lab-crew.git
      ref: main
    instance_dir: instances/lab-1
```

Exact CLI (`office spawn`, make targets, etc.) is an implementation detail; this document is the contract.

## Deploy flow (canonical)

1. **Office up** — shared bus healthy, Office agents reachable (or at least registry + bus).
2. **For each team entry** — fetch template at `ref` into `instance_dir` (or reuse existing checkout).
3. **Configure instance** — point at Office bus, doors secrets, team name, networks for pre-prod if Dev.
4. **Start instance** — lifecycle controller + agents (agents may start stopped or on-demand per policy).
5. **Register** — write registry entry; smoke wake + message + bus event.
6. **Announce** — team available for assignment.

DevOps (human or Super DevOps agent) can be given only the Office repo URL and a composition file.

## Version compatibility

- Office and templates evolve on separate cadences.
- Pin `ref` (tag preferred) per instance in production.
- Breaking bus/door/lifecycle changes require a documented Office minor/major and matching template release.
- Changelog in each repo should note “Office compatibility: requires agent-office ≥ x.y”.

## Improving teams over time

- Day-to-day improvements to Dev or Lab craft → PRs in `dev-crew` / `lab-crew`.
- Improvements to how modules plug into the shell → PRs in `agent-office`.
- Cross-cutting protocol changes (bus schema, wake contract) → coordinated change: Office spec first, then template PRs.

This is intentional: **Agent Office grows as a small set of repositories**, not one monorepo.

## Standalone mode (optional)

Templates MAY still support a legacy standalone mode (local Redis, always-on agents) for development of the template itself.  
**Default when composed under Office is Office-attached mode.** Standalone must not be required for Office operators.

## Summary

- Pull **agent-office** → assemble **N× template instances**.
- Templates stay separate repos and stay thinner under Office.
- Composition config defines how many Lab/Dev teams you run.
- Spec and protocol live in Office; team craft lives in team repos.
