---
name: paper-sync
description: "Project approved local paper state to GitHub Issues safely."
---

# Paper Sync

Use this skill only after explicit approval to project local state. Follow
`plugins/lean4/commands/paper-sync.md`; keep `.formalization/`, evidence, Lean
files, and git history authoritative.

From the repository root, reuse the canonical workflow runtime:

```bash
python3 plugins/lean4/lib/paper_workflow.py github-sync \
  --repo owner/repo --approved --spec --tickets
```

Do not import tracker edits silently, publish without approval, or introduce a
second sync format in the adapter.
