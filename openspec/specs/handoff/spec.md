# Capability: handoff

## Requirements

### Explicit and observable

Every significant transfer of work between Office and teams (or between teams via Office) SHALL be an explicit handoff that:

- Is published as an event on the shared bus
- Carries enough context for the receiver to act without reverse-engineering intent
- Can be accepted or rejected with a reason

### Main flows

1. **Idea → Lab**  
   Office (or human via Office) assigns research. Lab runs the hypothesis cycle and returns a Research Package (or explicit stop).

2. **Lab → Office**  
   Research Package (or negative recommendation) is handed back. Office decides next step (Dev, more research, stop).

3. **Office → Dev**  
   Clear assignment with context, links to Research Package / specs, scope, and constraints.

4. **Dev → Office / Super DevOps**  
   Status, blockers, and promotion requests to shared pre-prod.

5. **Cross-team on same project**  
   Ownership of the currently active slice of work must remain clear. Scrum Master is the source of truth for “who is responsible for what right now”.

### Anti-patterns (SHALL NOT)

- Silent reassignment without a bus event
- Starting implementation without a clear Office assignment when routing through Office is required
- Promoting to pre-prod without Super DevOps visibility
- Continuing research after a formal handoff without opening a new cycle

### Traceability

Scrum Master SHALL be able to reconstruct the current ownership and recent handoffs of any known project from bus events and linked artifacts.
