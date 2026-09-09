---
name: paper-to-tickets
description: "Derive formal obligations and contracted fresh-context Lean tickets."
---

# Paper to Tickets

Use this skill only after a durable paper specification exists. Follow the
canonical workflow at `plugins/lean4/commands/paper-to-tickets.md`; keep the
Claim, Obligation, and Ticket DAGs distinct and require dependency coverage.

From the repository root, reuse the canonical runtimes:

```bash
python3 plugins/lean4/lib/paper_workflow.py validate
python3 plugins/lean4/lib/paper_workflow.py check-spec
python3 plugins/lean4/lib/paper_architecture.py status
```

Create approved ticket contracts before implementation. Do not jump from a
paper section directly to proof work, and do not add adapter-local wrappers.

To make the split easy to read, export one Markdown file per ticket and an
index after the DAG is in shape:

```bash
python3 plugins/lean4/lib/paper_workflow.py render-tickets
```

The output is `.formalization/generated/tickets/README.md` plus one
`.md` file per ticket. The JSON state remains authoritative.
