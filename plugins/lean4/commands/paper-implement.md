---
name: paper-implement
description: Execute exactly one paper-formalization ticket in a fresh context using existing lean4-skills proof engines
user_invocable: true
argument-hint: '<ticket-id-or-owner/repo#issue>'
---

# Lean4 Paper Implement

One invocation owns **one ticket**. This workflow trusts the upstream spec/ticket
plan and does not reopen it during ordinary implementation.

Read [paper-workflow.md](../skills/lean4/references/paper-workflow.md) and the
existing [cycle-engine.md](../skills/lean4/references/cycle-engine.md).

## Usage

Resolve the supplied ticket to a stable local ticket ID. For a GitHub reference,
confirm the issue title and its embedded local ticket ID before editing Lean.
If the reference is ambiguous, stop rather than guessing from a numbered list.

Then:

```bash
lean4-skills-paper-workflow validate
lean4-skills-paper-workflow frontier
lean4-skills-paper-workflow start-ticket T-...
```

Do not start if it is not on the frontier. If durable state says `in_progress` but
the prior session is gone and no handoff was written, inspect the worktree first
and explicitly recover the orphaned session:

```bash
lean4-skills-paper-workflow recover-ticket T-... \
  --reason "previous session terminated before handoff"
```

Then recompute the frontier; never silently reset an in-progress ticket.

## Reconstruct only relevant context

Read:

- the ticket body/local ticket record;
- `FORMALIZATION_SPEC.md` sections relevant to the ticket;
- `.formalization/CONTEXT.md`;
- mapped paper claim(s), direct mathematical dependencies, registered assumptions;
- the last handoff if status was `partial`;
- relevant Lean files/imports.

Do not reread the whole paper unless the ticket explicitly requires broader source
analysis.

## Actions

Use the existing workflow that matches the ticket:

- statement/formalization work → `/lean4:formalize` or drafting tools;
- proof filling → `/lean4:prove` or `/lean4:autoprove`;
- suspected false statement → `/lean4:disprove`;
- integration check → `/lean4:checkpoint`/build ladder;
- review → `/lean4:review` when appropriate.

Paper workflow does not replace their LSP/search/build/header-fence mechanics.

## Safety

- Do not change a locked paper statement in a proof session.
- Do not turn a paper-original claim into an axiom/assumption.
- Do not silently broaden the ticket to unrelated claims.
- If a locked statement appears wrong, block the ticket and route the claim to planning or disprove.

## Completion paths

### Finished

Run the ticket's actual acceptance checks. If this ticket closes a paper claim,
verify that claim through the evidence gate only after its statement is locked,
its paper dependencies are verified, build passes, sorry count is zero, and the
axiom audit passes:

```bash
lean4-skills-paper-workflow verify-claim P-... \
  --build passed --sorries 0 --axioms passed \
  --statement-text /tmp/P-....statement
lean4-skills-paper-workflow finish-ticket T-... --verification passed
```

If mapped to GitHub, close it explicitly:

```bash
lean4-skills-paper-workflow github-close-ticket T-...
```

### Incomplete but still one coherent task

Persist `/lean4:paper-handoff` before the context boundary and leave the ticket
`partial`. A fresh session may resume the same ticket.

### Too large / newly discovered independent unknowns

Create child tickets first, then make the parent depend on them with
`split-ticket`. Do not burn repeated full contexts against an oversized parent.

At the end, show the new frontier; do not automatically start the next ticket in
the same context.

## See Also

Use `/lean4:paper-handoff` before a context boundary, `/lean4:paper-review` for
paper-level read-only scrutiny, and the existing theorem workflows for Lean work.
