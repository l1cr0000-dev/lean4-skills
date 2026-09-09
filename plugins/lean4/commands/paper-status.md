---
name: paper-status
description: Show durable paper workflow phase, claim/ticket counts, frontier, and tracker mappings
user_invocable: true
---

# Lean4 Paper Status

## Usage

Run:

```bash
lean4-skills-paper-workflow validate
lean4-skills-paper-workflow status
```

## Actions

Report:

- planning phase and grill readiness;
- target paper claim IDs;
- claim status counts;
- ticket status counts;
- current frontier;
- spec fingerprint/GitHub mapping;
- tracker repository.

For a factual progress report, use these files as truth instead of conversational
memory. If validation fails, surface the exact invariant violation before
recommending more proof work.

## Safety

Treat status as read-only. Do not infer a completed claim from a closed GitHub
issue, a passing partial build, or an earlier conversation; only verified local
evidence can establish it.

## See Also

Use `/lean4:paper-frontier` to choose ready work, `/lean4:paper-review` for a
read-only audit, and `/lean4:paper-final-audit` for the completion gate.

Include whether the recorded specification fingerprint is current. A changed
spec is a planning signal, not a reason to continue implementation against a
stale ticket graph.

When a ticket is `in_progress`, report whether it has a durable handoff. An
orphaned ticket must be recovered deliberately before another session resumes
it, preserving a truthful history of the interrupted work.

Status is also the right place to surface an empty target set, an unrecorded
spec fingerprint, or unresolved grill categories. These are planning gaps, not
ordinary proof blockers, and should be resolved before large proof sessions.

This keeps the next session's scope grounded in repository state rather than a
possibly incomplete chat summary.

It can be rerun after any state transition without changing the project.
Use it to make handoff and resume decisions explicit.
