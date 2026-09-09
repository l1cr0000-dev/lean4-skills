---
name: paper-implement
description: "Execute one approved paper ticket contract in a fresh context."
---

# Paper Implement

Use this skill for exactly one approved ticket. Follow
`plugins/lean4/commands/paper-implement.md`; validate the contract and active
stage before delegating theorem work to the existing `$lean4` workflows.

From the repository root, reuse the canonical runtime and the architecture
companion in this exact form:

```bash
python3 plugins/lean4/lib/paper_workflow.py validate
python3 plugins/lean4/lib/paper_architecture.py check-ticket T-042
python3 plugins/lean4/lib/paper_architecture.py render-dispatch T-042
```

Finish only when the ticket evidence is verified. If work is incomplete, use
`$paper-handoff` or split the ticket; never broaden a locked statement.
