---
name: paper-final-audit
description: Compute final trust status for target theorem closure, including trusted external premises and unfinished work
user_invocable: true
---

# Lean4 Paper Final Audit

This is the final paper-level gate after the target theorem appears complete.

## Usage

First run the normal Lean project/checkpoint verification appropriate to the repo.
Then run:

```bash
lean4-skills-paper-workflow validate
lean4-skills-paper-workflow final-audit
```

## Actions

The report distinguishes:

- fully kernel-checked target closure without `trusted_external` premises;
- kernel-checked target closure conditional on explicitly registered trusted external results;
- incomplete.

Do not describe a conditional result as an assumption-free complete formalization.
List every trusted external premise by stable ID and provenance. Also report any
unverified claim, unapproved premise, validation error, or related open ticket.

If clean, set project phase to `complete`:

```bash
lean4-skills-paper-workflow set-phase complete
```

## Safety

Only mark the project complete after the audit reports complete and the required
Lean build, sorry, and axiom checks have passed. A conditional result remains
conditional even when every Lean file compiles.

## See Also

Use `/lean4:paper-review` to inspect policy and graph integrity before this
gate, and `/lean4:paper-status` to report the durable final state.

The audit is intentionally a report, not a proof engine. It computes the
transitive closure from the selected targets, so a result is not complete while
any dependency remains unverified.

Keep the generated result with the project evidence. If the audit is
incomplete, return to the specific claim or ticket it identifies rather than
loosening the completion policy.

Archive no state solely because the audit is green. The durable manifests,
statement fingerprints, and proof evidence remain the reproducible audit trail.
They are the basis for any later independent review.
