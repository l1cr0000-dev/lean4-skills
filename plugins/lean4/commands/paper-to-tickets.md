---
name: paper-to-tickets
description: Split a formalization spec into one-fresh-context Lean tickets with explicit blocking edges
user_invocable: true
argument-hint: '[--publish-github]'
---

# Lean4 Paper To Tickets

Turn the settled spec into the **Ticket DAG**. The Paper Claim DAG remains a
separate mathematical artifact.

Read [paper-workflow.md](../skills/lean4/references/paper-workflow.md).

## Usage

```bash
lean4-skills-paper-workflow validate
lean4-skills-paper-workflow check-spec
```

## Actions

A ticket must be executable by a fresh session that has never seen the earlier
conversation. Prefer one narrow, verifiable mathematical/proof path over a
horizontal phase such as "formalize all definitions" or "prove all estimates".

Lean-specific useful ticket shapes include:

- formalize and lock one substantial paper statement plus its local definitions;
- prove one hard helper needed by a paper claim;
- close one estimate cluster whose dependencies are already verified;
- assemble already-proved helpers into a paper claim;
- perform a dedicated axiom/sorry/integration audit.

Do not force `one paper claim = one ticket`. One claim may need many tickets.

## Sizing

Default advisory budget is ~140k tokens for a 220k nominal window, with a soft
handoff around ~175k. Do not treat these as exact counters. Split earlier when a
ticket contains multiple independent hard unknowns.

## Approval gate

Before publishing anything:

1. persist the proposed breakdown locally as `--draft` tickets so it survives a context boundary;
2. present the numbered ticket plan to the user;
3. for every ticket show title, objective, claim IDs, blockers, and rough size;
4. explicitly ask whether to merge/split/reorder or change blockers;
5. after approval, promote the accepted drafts with `approve-tickets`;
6. publish only after approval.

Create blockers-first. Acceptance criteria must be observations that can fail at the starting state.

Example:

```bash
lean4-skills-paper-workflow add-ticket \
  --id T-042 \
  --title "Prove coercivity helper for P-PROP-014" \
  --kind prove \
  --objective "Prove the weighted coercivity estimate used in Proposition 4.2" \
  --claim P-PROP-014 \
  --requires-claim P-LEM-009 \
  --blocked-by T-039 \
  --constraint "Do not modify the locked statement of P-PROP-014" \
  --accept "helper theorem elaborates with zero sorry" \
  --accept "affected dependency build passes" \
  --estimate-tokens 130000 \
  --draft
```

After the user approves the breakdown:

```bash
lean4-skills-paper-workflow approve-tickets --all
```

Validate and inspect frontier:

```bash
lean4-skills-paper-workflow validate
lean4-skills-paper-workflow frontier
```

After user approval, publish GitHub tickets:

```bash
lean4-skills-paper-workflow github-sync --repo owner/repo --tickets --approved
```

Native `blocked-by`/parent relationships are used when supported by the installed
GitHub CLI; local `tickets.json` remains authoritative.

## Safety

Do not use issue ordering as the dependency graph or collapse a claim into one
ticket merely for tracker convenience. The context budget is advisory: split
when the work has multiple independent unknowns.

## See Also

Use `/lean4:paper-frontier` to select a ready ticket and
`/lean4:paper-implement` to execute exactly one of them.
