---
name: paper-final-audit
description: "Audit paper completion, machine evidence, trust, and comparators."
---

# Paper Final Audit

Use this skill only for the selected paper closure's final gate. Follow
`plugins/lean4/commands/paper-final-audit.md` and distinguish kernel-closed,
formally imported, conditional trusted-external, and incomplete results.

From the repository root, run both canonical audits:

```bash
python3 plugins/lean4/lib/paper_workflow.py final-audit --format json
python3 plugins/lean4/lib/paper_architecture.py validate
python3 plugins/lean4/lib/paper_architecture.py verification-gate --format json
python3 plugins/lean4/lib/paper_architecture.py architecture-audit --format json
```

Do not mark completion from a manual PASS assertion, and do not copy or fork
the canonical runtime.
