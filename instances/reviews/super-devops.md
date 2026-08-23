# Adversarial Review — Infrastructure Lens

> Note: the original review context was lost to log truncation. This review is
> reconstructed from the infrastructure-gate checklist; findings are framed as
> verification gaps where I could not confirm state from live evidence.

## VERDICT
CONDITIONAL PASS — no evidence of a hard failure, but three blocking
verification gaps must be closed before promotion is declared green.

## BLOCKING FINDINGS

1. **Promotion artifact provenance unverified.** I could not confirm from
   available logs that the promoted build/manifest in pre-prod matches the
   source-of-truth digest from the team's private dev cluster. Until the
   digest/commit SHA is cross-checked (manifest → image digest → git SHA),
   treat the promotion as unproven. Required: record the digest chain in the
   promotion log on the shared bus.

2. **No rollback path demonstrated.** The gate requires that any promotion be
   reversible. No evidence was captured showing the previous known-good
   manifest is retained and restorable (versioned config, previous replica
   set, or IaC state). Blocking until a rollback rehearsal or at minimum a
   documented, executable rollback step exists for this change.

3. **Health signal coverage gap.** Post-promotion health was not observed
   through the shared observability path (bus-published health event or
   equivalent). A promotion that "looks fine" from the team cluster but has no
   pre-prod health/readiness signal on the shared bus cannot be declared
   stable. Required: publish a health event with probe results and a soak
   window before closing the promotion.

## NON-BLOCKING NOTES

- Configuration drift between private dev clusters and shared pre-prod should
  be diffed regularly; silent divergence is the most common source of
  "works in dev, breaks at the gate" incidents.
- Resource requests/limits on pre-prod workloads should be re-checked against
  shared capacity; pre-prod must not become a second sandbox for
  oversized workloads.
- Promotion procedure documentation should include the exact bus event names
  and payloads so outcomes are machine-parseable, not prose-only.
- Recommend a standing rule: promotions during an active incident freeze are
  rejected automatically, not judgment-called.

— ox-alpha, Super DevOps (Pre-prod Owner), infrastructure lens
