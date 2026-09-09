---
name: paper-frontier
description: "Find paper tickets that pass architecture and dependency gates."
---

# Paper Frontier

Use this skill to identify tickets safe for a fresh implementation context.
Follow `plugins/lean4/commands/paper-frontier.md` and recompute durable state;
never infer readiness from issue order or chat memory.

From the repository root, run the canonical workflow and architecture checks:

```bash
python3 plugins/lean4/lib/paper_workflow.py validate
python3 plugins/lean4/lib/paper_workflow.py frontier
python3 plugins/lean4/lib/paper_architecture.py validate
python3 plugins/lean4/lib/paper_architecture.py parallel-frontier
```

Present only tickets that pass both gates. The adapter contains no copy of the
runtime or a new architecture wrapper.
