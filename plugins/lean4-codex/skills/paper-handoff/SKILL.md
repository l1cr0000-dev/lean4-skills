---
name: paper-handoff
description: "Persist unfinished paper work for safe fresh-session resumption."
---

# Paper Handoff

Use this skill at a context boundary or interruption. Follow
`plugins/lean4/commands/paper-handoff.md` and record completed work, the exact
goal, failed approaches, remaining work, blocker, and next action under
`.formalization/`.

From the repository root, reuse the canonical runtime:

```bash
python3 plugins/lean4/lib/paper_workflow.py handoff T-042 \
  --reason "context boundary" --current-goal "<goal>" \
  --next-action "<next action>"
```

GitHub comments are projections only. Do not create an adapter-local handoff
format or copy the workflow runtime.
