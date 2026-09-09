---
name: paper-to-tickets
description: Derive formal obligations, then split them into fresh-context Lean ticket contracts
user_invocable: true
argument-hint: '[--publish-github]'
---

# Lean4 Paper To Tickets

Turn the settled spec into two separate planning artifacts: the **Formal
Obligation DAG** and the **Ticket DAG**. The Paper Claim DAG remains separate.

Read [paper-workflow.md](../skills/lean4/references/paper-workflow.md).

## Usage

```bash
lean4-skills-paper-workflow validate
lean4-skills-paper-workflow check-spec
python3 <plugin-root>/lib/paper_architecture.py init
python3 <plugin-root>/lib/paper_architecture.py status
```
Before implementation planning, the active claim closure must have completed
source dependency scans. For each claim, record the proof references found in the
paper and reconcile them with `depends_on` / `uses_assumptions`:
```bash
python3 <plugin-root>/lib/paper_architecture.py record-dependency-scan \
  --claim P-MAIN \
  --source-ref "paper §1, Theorem 1.1 proof" \
  --internal-claim P-PROP-3.1 \
  --assumption A-MATHLIB-X \
  --complete
```
If the scan finds a missing dependency, update the Claim DAG first. Do not mark a
mismatched scan complete.
## Actions

During `main-theorem`, create work only for the active main-theorem transitive
closure. `skip` is terminal after Stage 1; `ask` pauses for the user's choice;
`after-main` permits Stage-2 planning only after `promote-full-paper` succeeds.

### Stage A — Formal Obligation DAG

Prefer proof-responsibility boundaries over paper sections. Useful kinds include:

- `statement` / `definition_data`;
- `generic_lemma` / `arithmetic_ledger`;
- `analytic_estimate` / `regularity_support`;
- `coherence_invariant` / `actual_instance`;
- `assembly` / `comparator_bridge` / `audit`.

A preferred shape is:

```text
Spec -> Generic -> Actual -> Assembly -> Bridge -> Audit
```

Use conditional interfaces when useful: prove the consumer from obligations
`H1...Hn`, then discharge each `Hi` independently. Keep arithmetic ledgers
separate from hard analysis when this reduces coupling.

Persist obligations as drafts with `add-obligation`, present the DAG, then use
`approve-obligations`. More than two independent hard unknowns is normally a
split signal.

### Stage B — Ticket DAG and contracts

Create base tickets as drafts, then bind each implementation ticket to an explicit
contract:

```bash
python3 <plugin-root>/lib/paper_architecture.py bind-ticket T-042 \
  --obligation O-ANA-017 \
  --completes-obligation O-ANA-017 \
  --worker autoprove \
  --owned-file Paper/Estimates.lean \
  --read-file Paper/Definitions.lean \
  --accept "lake env lean Paper/Estimates.lean" \
  --risk high --hard-unknowns 1
```
Run this acceptance command from the Lean project root so its imports resolve against intended build artifacts.

After the Ticket DAG is readable and approved, export a Markdown view with one
file per ticket plus an index:

```bash
lean4-skills-paper-workflow render-tickets
```

This writes `.formalization/generated/tickets/README.md` and
`.formalization/generated/tickets/<ticket-id>.md`. The JSON files under
`.formalization/` remain authoritative; regenerate the Markdown view after
changing the ticket graph.

Mutating tickets require owned files. Non-research formal tickets require
executable acceptance commands. Research tickets may investigate but may not
complete formal proof obligations.

Do not force one claim = one ticket or one obligation = one ticket. Small coherent
obligations may share a contract; a difficult obligation may use prerequisite
research/proof tickets plus one final completion ticket.

## Approval

Before implementation:

1. approve the obligation plan;
2. approve base tickets;
3. approve architecture contracts;
4. run both validators;
5. run `check-ticket` on the intended frontier;
6. publish GitHub projection only after explicit approval.

The architecture gate refuses proof execution if dependency coverage is missing,
a ticket mixes inactive-stage obligations, statement locks are missing, external
obligation dependencies are unsatisfied, or acceptance/ownership is incomplete.

## Safety

Do not use issue order as dependency truth. Do not hide an uncertain estimate in
“formalize section N”. Do not let parallel tickets write the same owned file.

Acceptance commands are security/trust-critical: they must genuinely exercise the
Lean checks needed for the contract, not a dummy success command.

A required independent comparator remains separate from the proof root and blocks
final completion until machine verified.

## See Also

Use `/lean4:paper-frontier` for runnable contracted work and
`/lean4:paper-implement` to execute exactly one approved contract.
