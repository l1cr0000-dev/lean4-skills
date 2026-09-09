---
name: paper-final-audit
description: Compute final machine-evidence, trust, and architecture status for the selected target closure
user_invocable: true
---

# Lean4 Paper Final Audit

This is the final paper-level completion gate. It combines the existing base trust
audit with the hardened architecture audit.

## Usage

Run the normal project-wide Lean checks appropriate to the repository, then:

```bash
lean4-skills-paper-workflow validate
lean4-skills-paper-workflow final-audit --format json
python3 <plugin-root>/lib/paper_architecture.py validate
python3 <plugin-root>/lib/paper_architecture.py verification-gate --format json
python3 <plugin-root>/lib/paper_architecture.py architecture-audit --format json
```

Do not mark the project complete unless both audit layers are complete and
`verification-gate` reports `terminal_for_selected_scope=true`.

For `full_paper_policy=skip`, a clean main-theorem closure is a valid terminal
result. `ask` requires the user's explicit stop/continue choice. `after-main` is
terminal only after the promoted full-paper scope is complete.

## Actions

Require all of the following for the active target closure:

- current spec/source fingerprints and locked target statements;
- every Paper Claim source dependency scan is complete and consistent with the
  Claim DAG / registered assumptions;
- every target-closure claim has Formal Obligation coverage;
- all transitive obligations are satisfied;
- each satisfied obligation points to untampered machine evidence from an approved
  contract;
- relevant machine evidence is current for its contract/source hashes;
- no related implementation ticket remains open;
- required independent comparators have machine-executed passing evidence;
- base build, zero-sorry, axiom, and verified-claim requirements pass.

Report the exact verification result label:

```text
PASS_KERNEL_CLOSED
PASS_FORMALLY_IMPORTED
PASS_CONDITIONAL_TRUSTED_EXTERNAL
INCOMPLETE
```

List every trusted external premise by stable ID and provenance. A conditional
result means Lean verified the selected paper proof relative to those approved
external premises; never describe it as assumption-free.

Also list every unverified claim, missing/stale dependency scan, uncovered claim,
incomplete obligation, invalid/tampered evidence item, open related contract, and
required unverified comparator.

If both audit layers are clean and the selected scope is terminal:

```bash
lean4-skills-paper-workflow set-phase complete
```

Preserve generated audit output with project evidence.

## Safety

Do not repair state during final audit. Do not downgrade trust requirements,
reclassify paper-original claims as external, or replace a failed machine command
with a manual PASS flag.

A compiled final theorem alone is insufficient if the source dependency map is
incomplete, the formal target drifted, machine evidence is stale, or a required
comparator has not passed.

Direct `--strategy full-paper` may have
`main_theorem_gate=explicit-full-paper-bypass`; do not report that as a passed
Stage-1 main-theorem gate. The full selected scope must still pass its final audit.

## See Also

Use `/lean4:paper-review` before this gate and `/lean4:paper-status` for a durable
progress report.
