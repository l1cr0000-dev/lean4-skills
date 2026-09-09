---
name: paper-frontier
description: Compute contracted paper-formalization tickets that are actually ready for a fresh session
user_invocable: true
---

# Lean4 Paper Frontier

Read durable state; do not infer readiness from memory, issue ordering, or a
previous conversation.

## Usage

Run both validation layers:

```bash
lean4-skills-paper-workflow validate
lean4-skills-paper-workflow frontier
python3 <plugin-root>/lib/paper_architecture.py validate
python3 <plugin-root>/lib/paper_architecture.py status
```

For any proposed ticket, run the stronger architecture gate:

```bash
python3 <plugin-root>/lib/paper_architecture.py check-ticket T-042
```

## Actions

A ticket is actually runnable only when it passes **both** layers:

1. base Ticket DAG says it is `ready` or resumable `partial`;
2. every base `blocked_by` ticket is closed;
3. every base `requires_claims` claim is verified;
4. it has an approved architecture contract;
5. required statement locks are current;
6. dependency coverage is complete for the active Paper Claim closure;
7. every linked obligation belongs to the active verification stage;
8. every obligation dependency outside this ticket is satisfied;
9. no linked obligation is blocked or rejected;
10. mutating ownership and executable acceptance requirements are met.

Present each runnable ticket with objective, linked claims, linked obligations,
worker type, risk, owned files, GitHub mapping, and advisory size. Recommend one
full reference when exactly one ticket is ready.

For a large project, you may also inspect:

```bash
python3 <plugin-root>/lib/paper_architecture.py parallel-frontier
```

This returns conflict-free advisory batches using file ownership. It does not
start agents, create worktrees, or authorize concurrent writes.

## Safety

Do not start work automatically. A GitHub issue's state never overrides local
manifests. Do not make a ticket runnable by deleting a blocker, silently approving
a contract, changing a statement, or marking an obligation satisfied without
evidence.

Parallel execution is optional. The default remains one fresh context per ticket.
If parallelism is used, use separate worktrees/processes and preserve one-writer
ownership for each file.

## See Also

Use `/lean4:paper-status` for the combined project state. Once a user selects a
runnable ticket, continue with `/lean4:paper-implement`.

If the frontier is empty, report which dependency scans, base blockers, claims,
obligation edges, statement locks, stage boundaries, or contract requirements prevent progress. Planning defects go
back to `paper-to-tickets`; mathematical blockers remain explicit obligations.

Frontier computation is read-only and safe to rerun at every session boundary.
