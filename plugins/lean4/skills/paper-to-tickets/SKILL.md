---
name: paper-to-tickets
description: "Derive formal obligations and split them into fresh-context Lean ticket contracts."
---

# Paper To Tickets

Use this visible Codex skill after a durable paper specification exists. Follow
the canonical [paper-to-tickets command](../../commands/paper-to-tickets.md) to
keep the Paper Claim DAG, Formal Obligation DAG, and Ticket DAG distinct. Require
dependency coverage and approved contracts before implementation.

After the Ticket DAG or its contracts change, always run
`lean4-skills-paper-workflow render-tickets` so the Markdown projection stays
current. If the user explicitly requests `--publish-github`, ask for
confirmation, then use the `paper-sync` workflow with `--approved`; never
publish draft tickets silently.
