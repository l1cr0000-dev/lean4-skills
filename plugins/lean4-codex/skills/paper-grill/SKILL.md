---
name: paper-grill
description: "Freeze paper scope, trust, statement, and completion policy durably."
---

# Paper Grill

Use this skill before a multi-session paper formalization. Ask one substantive
question at a time, persist each decision, and stop when `grill-check` is ready.

Follow the canonical workflow at `plugins/lean4/commands/paper-grill.md`.
Run from the repository root and reuse the existing runtime:

```bash
python3 plugins/lean4/lib/paper_workflow.py init --source <PATH> --title <TITLE>
python3 plugins/lean4/lib/paper_workflow.py grill-check
```

Do not start proof work, publish issues, or replace durable state with chat
memory. If `plugins/lean4/lib/paper_workflow.py` is unavailable, stop and
report the missing canonical runtime.
