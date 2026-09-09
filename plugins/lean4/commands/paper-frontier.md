---
name: paper-frontier
description: Compute paper-formalization tickets that are actually ready for a fresh session
user_invocable: true
---

# Lean4 Paper Frontier

Read durable state; do not infer readiness from memory or from issue ordering.

## Usage

```bash
lean4-skills-paper-workflow validate
lean4-skills-paper-workflow frontier
```

## Actions

A ticket is ready only when all ticket blockers are closed and all
`requires_claims` are verified. Present each ready ticket's objective, linked
claims, GitHub mapping, and advisory estimate before selecting work.

Present the ready tickets with objective, linked paper claims, GitHub issue mapping,
and estimated size. If exactly one ticket is ready, recommend its full reference
(e.g. `owner/repo#123` or stable local ID `T-042`) for `/lean4:paper-implement`.

## Safety

Do not start work automatically. A GitHub issue's open or closed state does not
override `tickets.json`; reconcile contradictory tracker state through planning.

## See Also

Use `/lean4:paper-status` for the complete durable-state summary. Once a user
selects a frontier ticket, continue with `/lean4:paper-implement`.

The frontier is an execution query over the Ticket DAG, not a mathematical
topological sort. A ticket can mention several claims while waiting on only the
specific verified claims that it needs to begin.

If the result is empty, explain which ticket blockers or mathematical claim
requirements are preventing progress. Do not manufacture a ready ticket by
changing its status or deleting a dependency edge.

If several tickets are ready, present them as independent choices. Let the user
choose the next scope, then start a fresh context for its implementation.

Before proposing a ticket, confirm that its acceptance criteria are still
meaningful and that no changed statement fingerprint has invalidated its plan.
Use a planning review when the remaining work does not fit the existing ticket
edges.

Frontier output is safe to recompute at any time. It changes only when durable
claim or ticket state changes, never because the current conversation has more
or less context remaining.

The command never edits state. It only makes the existing execution constraints
visible for selection and handoff.

It is therefore safe to use at every planning boundary.
