---
name: paper-implement
description: Execute exactly one contracted paper-formalization ticket in a fresh context
user_invocable: true
argument-hint: '<ticket-id-or-owner/repo#issue>'
---

# Lean4 Paper Implement

One invocation owns **one approved ticket contract**. It does not reopen upstream
planning during ordinary implementation.

Read [paper-workflow.md](../skills/lean4/references/paper-workflow.md) and
[cycle-engine.md](../skills/lean4/references/cycle-engine.md).

## Usage

Resolve the supplied reference to a stable local ticket ID, then run:

```bash
lean4-skills-paper-workflow validate
python3 <plugin-root>/lib/paper_architecture.py validate
python3 <plugin-root>/lib/paper_architecture.py check-ticket T-042
python3 <plugin-root>/lib/paper_architecture.py render-dispatch T-042
lean4-skills-paper-workflow start-ticket T-042
```

`check-ticket` is a hard gate. It also requires completed dependency coverage for
the active Paper Claim closure and rejects any ticket containing even one
obligation outside the active verification stage.

## Actions

### Reconstruct the session

Use the generated dispatch JSON as the primary zero-context packet. It contains
spec fingerprint, claims, obligations, statement locks, ownership, acceptance
commands, risk, and last handoff. Read only the source/Lean context needed by the
contract.

### Work the contract

Use the contract-selected worker (`formalize`, `prove`, `autoprove`, `disprove`,
`integrate`, `review`, or bounded `research`). Research may not discharge a formal
obligation.

For proof work:

```text
inspect goal -> search -> edit -> compile/check -> diagnose -> repair -> repeat
```

Modify only `owned_files`. Treat `read_files` as read-only. Never alter a locked
paper statement inside an implementation session.

## Completion

When the mathematical work appears finished, run the contract's Lean checks and
close the base ticket according to the existing workflow. Then let the architecture
helper independently execute the frozen acceptance commands:

```bash
python3 <plugin-root>/lib/paper_architecture.py verify-ticket T-042
```

The helper records command exit codes, stdout/stderr hashes, environment metadata,
contract fingerprint, and relevant current source hashes. A failed command does
not produce PASS evidence.

Then satisfy only obligations named by `completes_obligations`:

```bash
python3 <plugin-root>/lib/paper_architecture.py satisfy-obligation O-ANA-017 \
  --ticket T-042 \
  --evidence "contracted estimate completed"
```

If no valid ticket verification exists, `satisfy-obligation` runs machine
verification automatically. Free-form `--evidence` is only a note; it cannot
replace executable evidence. Manual `--command` values may not differ from the
approved contract commands.

If the relevant source file, evidence file, or contract changes later, validation
marks the machine evidence stale/invalid until re-verification.

If this closes a Paper Claim, use the existing statement fingerprint, build,
zero-sorry, axiom, and dependency gate before marking the claim verified.

### Incomplete

Persist a paper handoff and leave the base ticket `partial`. A fresh session can
render a new dispatch and resume the same contract.

### Too large

Return to planning, create child obligations/tickets, and revise dependencies.
Do not silently expand ownership or scope.

## Safety

- Never turn a paper-original claim into an assumption.
- Never accept prose or agent confidence as proof evidence.
- Never broaden to unrelated obligations.
- Never use a dummy acceptance command merely to obtain exit code 0.
- If the target is false/malformed, block and route to planning or disproof.
- More than two independent hard unknowns is a split signal.

After completion, show the new frontier. Do not automatically start another ticket
inside the same context.

## See Also

Use `/lean4:paper-handoff` before context loss, `/lean4:paper-review` for
architecture scrutiny, and theorem-level workflows for Lean proof mechanics.
