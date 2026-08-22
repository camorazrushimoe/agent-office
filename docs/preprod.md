# Shared pre-prod — ownership and promotion protocol

## Owner

**Super DevOps** owns the shared pre-prod cluster at Office level.

- Stability, access, network, baseline services
- Promotion rules and visibility on the bus
- Coordination when multiple Dev instances promote

Team-level DevOps agents own **private dev-clusters** only. They do not unilaterally own shared pre-prod.

## Purpose

Shared pre-prod is the **integration and release-candidate gate**:

- Work verified in a team’s private dev-cluster can be promoted here
- QA and release decisions happen against pre-prod
- Not a second wild-west sandbox

## Promotion flow (happy path)

1. Dev team finishes work in private dev-cluster and is ready to promote.
2. Team publishes `promotion.requested` on the Office bus (actor = team-qualified devops or developer).
3. Payload includes at least: `team`, `project`, `artifact` (image tag / compose ref / commit), `summary`, optional `rollback` hint.
4. Super DevOps (or automated policy they define) accepts or rejects.
5. On accept: apply change to pre-prod; publish `promotion.completed` (success) or failure with reason.
6. On reject: publish `handoff.rejected` or `promotion.completed` with `success: false` and reason.

All steps must be visible in the Office event log.

## Locking when multiple teams promote (v1 decision)

**v1 rule: single-writer lock per pre-prod “slot” (default: one global lock).**

| Rule | Detail |
|------|--------|
| Lock scope | Entire shared pre-prod (v1). Later may split by project namespace. |
| Lock holder | Team name + promotion id |
| Acquire | Before applying changes; recorded on bus / Redis key `preprod:lock` |
| TTL | Configurable (default 30 minutes); renewable while promotion is in progress |
| Conflict | Second `promotion.requested` while lock held → reject or queue; do not interleave silent writes |
| Release | On `promotion.completed` (success or fail) or TTL expiry (then Super DevOps investigates) |

### Redis key sketch

```text
preprod:lock → { "team": "dev-1", "promotion_id": "…", "expires_at": "…" }
```

Only Super DevOps (or the lifecycle/promotion helper they run) should set/clear the lock in v1. Team agents request; they do not force-unlock without Office visibility.

## What teams must not do

- Write to pre-prod without `promotion.requested` / acceptance
- Hold the lock across unrelated workstreams without renewing intent
- Point production traffic at pre-prod without a separate decision (out of scope for factory v1)

## QA and Super DevOps

- Team QA may test **after** successful promotion to pre-prod
- Super DevOps remains responsible if pre-prod is broken by a promotion — they can roll back and mark the promotion failed

## Lab teams

Lab instances normally **do not** promote to pre-prod. Research artifacts live in workspace / handoff packages. If a Lab ever needs a shared env, it is an explicit exception under Super DevOps.

## Open extensions (post-v1)

- Per-project namespaces on the same cluster
- Queue of promotions with fairness
- Automated canary checks before `promotion.completed` success
