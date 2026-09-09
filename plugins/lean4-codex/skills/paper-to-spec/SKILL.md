---
name: paper-to-spec
description: "Freeze paper targets and synthesize the durable Paper Claim DAG."
---

# Paper to Spec

Use this skill after `paper-grill` is ready. Read the canonical workflow at
`plugins/lean4/commands/paper-to-spec.md`, record the source fingerprint and
claims, and keep unresolved policy decisions out of the spec.

Reuse the canonical runtimes from the repository root:

```bash
python3 plugins/lean4/lib/paper_workflow.py validate
python3 plugins/lean4/lib/paper_workflow.py grill-check
python3 plugins/lean4/lib/paper_architecture.py init
python3 plugins/lean4/lib/paper_architecture.py configure-verification \
  --primary-target P-MAIN --full-paper-policy skip
```

Run the dependency-coverage audit before creating tickets. Do not copy either
runtime into this adapter or treat GitHub Issues as the source of truth.
