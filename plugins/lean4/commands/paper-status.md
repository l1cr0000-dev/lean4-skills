---
name: paper-status
description: Show combined claim, dependency-coverage, obligation, contract, evidence, comparator, and scope state
user_invocable: true
---

# Lean4 Paper Status

## Usage

```bash
lean4-skills-paper-workflow validate
lean4-skills-paper-workflow status
python3 <plugin-root>/lib/paper_architecture.py validate
python3 <plugin-root>/lib/paper_architecture.py status
```

Optionally inspect advisory parallel work with:

```bash
python3 <plugin-root>/lib/paper_architecture.py parallel-frontier
```

## Actions

Report:

- planning phase and active verification stage;
- `full_paper_policy` (`skip`, `ask`, or `after-main`);
- selected target IDs and Paper Claim status;
- dependency coverage completeness, including missing/stale scans;
- Formal Obligation counts and frontier;
- base Ticket and architecture-contract state;
- invalid/stale machine evidence and the affected ticket/obligation;
- required/optional comparator state;
- current verification result/trust label;
- spec/source fingerprint status and last handoff.

The runnable frontier is the intersection of base Ticket readiness and hardened
`check-ticket` readiness. A base-ready ticket is still blocked if dependency
coverage is incomplete, its contract is unapproved, it mixes active and inactive
obligations, a required statement is unlocked, or an external obligation
dependency is unsatisfied.

`parallel-frontier` is advisory only. It derives conflict-free batches from
explicit file ownership; it does not prove that concurrent mathematical work is
independent.

Treat local manifests and machine evidence as progress truth. A closed GitHub
issue, chat summary, or agent assertion does not imply proof completion.

## Safety

Status is read-only. Never mark claims verified, obligations satisfied, scans
complete, contracts approved, or comparators verified while reporting state.

Surface source/spec drift, evidence fingerprint mismatch, contract/source drift,
uncovered target claims, and orphaned tickets before recommending more proof work.

If the result is `PASS_CONDITIONAL_TRUSTED_EXTERNAL`, name that condition instead
of shortening it to `PASS`.

## See Also

Use `/lean4:paper-frontier` to choose work, `/lean4:paper-review` for read-only
scrutiny, and `/lean4:paper-final-audit` for the completion gate.
