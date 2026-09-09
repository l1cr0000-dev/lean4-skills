---
name: paper-review
description: Read-only audit of scope, dependency coverage, three DAGs, machine evidence, trust, and comparators
user_invocable: true
argument-hint: '[--scope=project|claim|ticket]'
---

# Lean4 Paper Review

This is read-only. It complements `/lean4:review`, which focuses on Lean proof
quality rather than paper-scale orchestration.

## Usage

Read [paper-workflow.md](../skills/lean4/references/paper-workflow.md), then run:

```bash
lean4-skills-paper-workflow validate
python3 <plugin-root>/lib/paper_architecture.py validate
python3 <plugin-root>/lib/paper_architecture.py verification-gate --format json
```

## Actions

Audit for:

1. active scope matches `project.targets`, and Stage 1 has no mixed Stage-2 ticket;
2. `full_paper_policy` is explicit and promotion history is coherent;
3. target theorem and transitive Paper Claim closure match the selected scope;
4. every active claim has a completed, source-fingerprint-bound dependency scan;
5. each scan exactly matches Claim DAG edges and registered assumptions;
6. no paper-original claim appears in `assumptions.json`;
7. trusted external premises have provenance and approval;
8. every target-closure claim has Formal Obligation coverage;
9. obligation dependencies are acyclic and satisfied nodes have satisfied deps;
10. each implementation ticket has one approved contract and clear ownership;
11. research contracts do not complete formal obligations;
12. acceptance commands genuinely exercise the intended Lean verification;
13. satisfied obligations have untampered machine evidence tied to closed tickets;
14. evidence contract/source hashes are still current;
15. locked statements have Lean mappings/fingerprints;
16. required independent comparators are independent and machine verified;
17. GitHub state does not contradict authoritative local state.

When reviewing one claim, include source dependency coverage, direct claim deps,
obligation coverage, and downstream assembly/bridge obligations. For one ticket,
include stage membership, contract, ownership, external obligation deps, acceptance
commands, and evidence freshness.

## Safety

Report defects without mutating claims, scans, obligations, tickets, contracts,
comparators, or GitHub issues. Route repairs to the responsible workflow.

Do not demand a comparator when the spec marks it optional. Do not reclassify a
paper theorem as external to make an audit green. Do not accept a manually written
`passed` value in place of machine command evidence.

For trust findings, name the exact result class and external premise IDs.

## See Also

Use `/lean4:review` for Lean proof-quality review and `/lean4:paper-final-audit`
for the completion gate.
