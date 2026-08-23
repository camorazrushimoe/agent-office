# Design: spec team type

## Context

Product Factory merged its Office template contract (its PR #1): the Spec
team sits between Lab (validated research in) and Dev (approved spec out).
Office-side recognition is a small, documentation-level change — the heavy
lifting (bus attach, lifecycle, wake-aware doors) lives in the template per
its own contract.

## Decisions

1. **`type: spec`** as the registry value. The registry schema already says
   "lab | dev (extensible)"; this change exercises the extension point with
   a concrete third value rather than the vague `other`.
2. **No private cluster for spec teams.** Their artifacts are documents.
   This matches `openspec/specs/environments` ("Lab teams typically do not
   require a full private cluster") and the template's own statement.
3. **Handoff naming: `spec.ready`.** Mirrors `research.ready`; the event
   carries an artifact pointer, not the spec body (bus = signal layer).
4. **Composition example keeps 1 lab + 2 dev uncommented** (the closed v1
   reference shape), with the spec-1 entry present but commented so
   operators opt in deliberately.

## Risks / Trade-offs

- [Type enumeration drift] → registry doc becomes the single list
  (lab | spec | dev | other); future templates extend it via the same
  change process.
- [Premature documentation] → the template itself is at design/Phase 0 for
  Docker runtime; documenting the type now is cheap and prevents ad-hoc
  `other` registrations later.

## Migration Plan

None required — additive documentation/config-shape change; no running
instances are affected.
