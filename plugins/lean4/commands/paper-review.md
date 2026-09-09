---
name: paper-review
description: Read-only audit of paper-level scope, trust boundary, claim DAG, ticket DAG, statement locks, and handoffs
user_invocable: true
argument-hint: '[--scope=project|claim|ticket]'
---

# Lean4 Paper Review

This is read-only. It complements `/lean4:review`, which focuses on Lean proof
quality.

## Usage

Read [paper-workflow.md](../skills/lean4/references/paper-workflow.md), then run
`lean4-skills-paper-workflow validate`.

## Actions

Audit for:

1. target theorem and transitive Paper Claim closure match the stated scope;
2. no paper-original claim appears in `assumptions.json`;
3. every trusted external premise has provenance and explicit approval;
4. claim DAG has no missing or circular edges;
5. locked statements have Lean mapping + fingerprint;
6. no `verified` claim lacks build/sorry/axiom evidence;
7. ticket DAG is execution-oriented and not confused with the claim DAG;
8. tickets are fresh-context executable and not obviously oversized;
9. acceptance criteria can fail and are owned by that ticket;
10. blocked/partial tickets have useful handoffs;
11. GitHub issue mapping does not override contradictory local state.

When reviewing one claim or ticket, include its direct dependencies and direct
reverse dependents so an apparent local change is evaluated for downstream impact.

## Safety

Report defects without repairing planning state, statements, tickets, or GitHub
issues. Route concrete repairs to the responsible paper command after review.

## See Also

Use `/lean4:review` for Lean proof-quality review and `/lean4:paper-final-audit`
to compute the project-level closure and trust result.

Review findings should name the durable record, affected IDs, observed evidence,
and recommended next action. This gives a later planning session enough detail
to resolve the issue without relying on the reviewer conversation.

When the review finds a source ambiguity, distinguish it from a proof failure:
the former reopens a planning decision, while the latter belongs to a ticket.

For trust-boundary findings, identify the category (`foundation`, `mathlib`,
`formal_import`, or `trusted_external`) and whether the premise is approved.
Never label a paper-original theorem as external merely to make the audit pass.
Record the required correction in a follow-up planning or implementation ticket.

Keep the report scoped to observed repository state and cite its record paths.
This helps a later reviewer reproduce both the finding and its resolution.
