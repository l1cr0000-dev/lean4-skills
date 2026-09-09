---
name: lean4
description: "Run validated Lean 4 and mathlib theorem workflows through the canonical runtime."
---

# Lean 4

Use this native Codex skill for theorem proving, formalization, review, and
diagnosis in Lean 4 projects.

This is an adapter surface, not a second Lean implementation. Read the
canonical workflow instructions in `plugins/lean4/skills/lean4/SKILL.md` and
keep all theorem-level behavior, proof runtime, wrappers, hooks, and schemas
owned by `plugins/lean4`.

When working from this repository, run commands from its root. If a workflow
needs paper state, reuse `plugins/lean4/lib/paper_workflow.py` and
`plugins/lean4/lib/paper_architecture.py`; do not create an adapter-local
runtime or wrapper. If `plugins/lean4` is absent, report that the canonical
runtime is unavailable instead of copying it.
