---
name: paper-status
description: "Show durable paper claims, tickets, evidence, and scope state."
---

# Paper Status

Use this skill for an evidence-backed progress report. Follow
`plugins/lean4/commands/paper-status.md` and read local durable state rather
than conversation history or GitHub issue state.

From the repository root, invoke the canonical runtimes:

```bash
python3 plugins/lean4/lib/paper_workflow.py validate
python3 plugins/lean4/lib/paper_workflow.py status
python3 plugins/lean4/lib/paper_architecture.py status
```

Surface invalid evidence, missing dependency coverage, and orphaned tickets.
This adapter only provides the skill surface; it owns no paper state.
