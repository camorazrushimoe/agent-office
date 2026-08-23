# Team registry

The Office team registry is the source of truth for **which team instances exist** and how to reach them.

Scrum Master and other Office agents use it for routing, status, and onboarding.

## Storage (v1)

- File-based YAML (or JSON) in instance config, e.g. `config/team-registry.yaml`
- Gitignored if it contains secrets; a committed `team-registry.example.yaml` is allowed
- Later may move to Redis keys or a small service; **schema stays the same**

## Schema

```yaml
version: 1
teams:
  - name: dev-1                    # unique instance id
    type: dev                      # lab | spec | dev | other
    template:
      repo: https://github.com/camorazrushimoe/dev-crew.git
      ref: v0.1.0                  # tag preferred in production
    status: online                 # online | offline | provisioning | drained
    endpoints:
      doors:
        developer: https://host:8651/webhooks/inbox
        qa: https://host:8652/webhooks/inbox
        tech-pm: https://host:8653/webhooks/inbox
        devops: https://host:8654/webhooks/inbox
      health:
        developer: https://host:8651/health
      lifecycle: http://dev-1-lifecycle:8700   # optional URL for wake API
    bus:
      actor_prefix: dev-1          # actors published as dev-1/developer
    capacity_notes: ""
    owner_contact: scrum-master
    registered_at: "2026-08-22T12:00:00Z"
```

### Required fields

| Field | Meaning |
|-------|--------|
| `name` | Unique instance id across the Office |
| `type` | `lab`, `spec`, or `dev` (extensible) |
| `template.repo` + `template.ref` | Where this instance came from |
| `status` | Operational state |
| `endpoints.doors` | At least one door per active agent role |

### Optional but recommended

- `endpoints.lifecycle` — wake API for the instance controller
- `bus.actor_prefix` — avoids collisions on the shared bus
- `capacity_notes` — free text for Scrum Master

### Type notes: spec teams (product-factory template)

Spec team instances (`type: spec`, template
[product-factory](https://github.com/camorazrushimoe/product-factory))
turn business intake / validated research into **Product Specs ready for
engineering**:

- **No private dev-cluster** — artifacts are documents (specs, LLM Wiki,
  workspace drafts), not running systems.
- Handoff event: `spec.ready` with an artifact pointer (not the full text).
- Human gates inside the pipeline surface as first-class bus events so
  Office can escalate to human operators.
- Template contract: `docs/office-template.md` in the product-factory repo.

## Operations

| Action | Effect |
|--------|--------|
| Register | Add entry after smoke tests (`docs/onboarding-team.md`) |
| Drain | `status: drained` — no new assignments |
| Offline | Instance down or unreachable |
| Deregister | Remove entry only when instance is intentionally retired |

## Invariants

- No two teams share the same `name`
- Door URLs in the registry MUST match the running instance
- Changing `ref` without redeploying the instance is a documentation lie — update registry only after upgrade

## Example minimal registry (empty Office)

```yaml
version: 1
teams: []
```
