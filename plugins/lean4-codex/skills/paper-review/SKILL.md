---
name: paper-review
description: "Audit paper scope, DAGs, evidence, trust, and comparators read-only."
---

# Paper Review

Use this skill for a read-only paper-scale audit. Follow
`plugins/lean4/commands/paper-review.md` and inspect scope, source coverage,
the three DAGs, evidence integrity, trust boundary, and comparator status.

From the repository root, reuse the canonical audit commands:

```bash
python3 plugins/lean4/lib/paper_workflow.py validate
python3 plugins/lean4/lib/paper_architecture.py validate
python3 plugins/lean4/lib/paper_architecture.py verification-gate --format json
```

Report findings without mutating planning or proof state. Do not duplicate the
architecture implementation in this adapter.
