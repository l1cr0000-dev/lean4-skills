# Paper Workflow Reference

This add-on wraps the existing lean4-skills theorem-level workflows with durable,
multi-session orchestration for formalizing a whole paper.

## Non-negotiable design rule

> Conversation context is disposable. `.formalization/`, Lean source files, and git must be sufficient for a fresh agent to resume.

The add-on intentionally does **not** replace `/lean4:prove`, `/lean4:autoprove`,
`/lean4:formalize`, `/lean4:disprove`, `/lean4:review`, or `/lean4:checkpoint`.
Those remain the proof engines. Paper workflow decides *what* one fresh session
should work on and persists what happened.

## Main chain

```text
paper-grill
  ↓
paper-to-spec
  ↓
paper-to-tickets
  ↓
paper-frontier
  ↓
paper-implement <one ticket>
  ↓
  ├─ finish → close ticket → next frontier item
  ├─ partial → paper-handoff → fresh session resumes same ticket
  └─ too large / new independent unknowns → split child tickets → parent blocks on children
  ↓
paper-final-audit
```

This follows the same high-level separation used by Matt Pocock's engineering
skills: interview/decision making, spec synthesis, ticket slicing, then one
fresh context per ticket. The Lean version adds stronger durable state and two
separate dependency graphs.

## Durable files

```text
paper-repo/
├── FORMALIZATION_SPEC.md
├── .formalization/
│   ├── project.json
│   ├── CONTEXT.md
│   ├── decisions.json
│   ├── terms.json
│   ├── assumptions.json
│   ├── claims.json
│   ├── tickets.json
│   ├── generated/
│   └── handoffs/
└── Paper/
    └── *.lean
```

Machine truth lives in the JSON files. GitHub Issues are a projection for
collaboration, visibility, and native blocking edges. If GitHub is unavailable,
local state remains sufficient to continue.

## Grill discipline

`paper-grill` asks one decision question at a time and records every resolved
answer immediately. Unlike a glossary-only workflow, ordinary decisions do not
remain solely in chat history.

At minimum the grill must settle these categories:

- `scope`: which theorem(s) and what dependency closure are in scope;
- `trust_boundary`: what external mathematics may be imported or trusted;
- `statement_policy`: what happens when formalization reveals a missing or wrong hypothesis;
- `completion_policy`: what evidence counts as finished.

Use:

```bash
lean4-skills-paper-workflow grill-check
```

before moving to `paper-to-spec`.

## Trust boundary

External inputs are registered separately from paper claims:

- `foundation`: accepted foundational Lean assumptions/policy;
- `mathlib`: a theorem already available in mathlib;
- `formal_import`: a theorem imported from another checked Lean development;
- `trusted_external`: an informal external result accepted as a project premise.

A paper-original claim must never be registered as an assumption. It belongs in
`claims.json` and must be proved if it lies in the target dependency closure.

Final audit distinguishes:

- `kernel-checked-without-trusted-external-results`;
- `kernel-checked-conditional-on-trusted-external-results`;
- `incomplete`.

## Two DAGs

### Paper Claim DAG

`claims.json` records mathematical dependency:

```text
P-LEM-021 → P-PROP-044 → P-THM-001
```

Paper IDs are stable and never recycled. This graph changes only when source
analysis or an explicit planning revision changes the understood mathematical
dependency.

### Ticket DAG

`tickets.json` records execution dependency:

```text
T-031 formalize statement
  ↓
T-032 prove coercivity helper
  ↓
T-033 prove boundary estimate
  ↓
T-034 assemble paper proposition
```

One paper claim can require many tickets, and one small ticket may cover several
claims. Ticket DAG may evolve freely as Lean exposes new proof obligations.

Do not collapse these two graphs into one.

## Ticket sizing

A ticket is sized for one *fresh* context, not for an exact token count. The
default project metadata assumes a 220k nominal context and stores advisory
planning numbers:

- target around 140k tokens;
- soft handoff around 175k tokens.

These are planning estimates only. Runtime token accounting is host-dependent.
Use mathematical uncertainty as the stronger signal: if a ticket contains more
than one or two independent hard unknowns, or repeatedly needs another full
session, split it rather than stretching the budget.

A good ticket is zero-context executable. It states:

- objective;
- paper claim IDs and source references;
- blockers and required verified claims;
- constraints, especially locked statements;
- acceptance criteria that can actually fail;
- handoff/split rule.

## Statement locks

A paper statement is first translated and reviewed, then fingerprint-locked:

```bash
lean4-skills-paper-workflow set-statement P-LEM-034 \
  --file Paper/Section4.lean \
  --declaration lemma_4_2 \
  --statement-text /tmp/P-LEM-034.statement \
  --lock
```

Proof sessions may change proof bodies and add helper lemmas, but may not alter
the locked paper statement. If a change is mathematically necessary:

```bash
lean4-skills-paper-workflow unlock-statement P-LEM-034 \
  --reason "source statement appears to miss hypothesis ..."
```

This invalidates prior proof trust and routes the claim back to planning as
`needs_revision`.

## Frontier

A ticket is on the frontier iff:

1. status is `ready` or resumable `partial`;
2. every ticket in `blocked_by` is `closed`;
3. every claim in `requires_claims` is `verified`.

Compute rather than guess:

```bash
lean4-skills-paper-workflow frontier
```

## One-ticket implementation contract

A `paper-implement` session:

1. resolves one full ticket reference and confirms its title;
2. validates local state and confirms the ticket is on the frontier;
3. reconstructs context from the ticket, spec, mapped claims, direct dependencies, and last handoff;
4. calls the existing lean4-skills proof/formalization workflows as appropriate;
5. does not reopen the upstream plan;
6. either closes the ticket with evidence, persists a handoff, or splits it.

If the session discovers the paper claim is false or malformed, do not edit the
statement to make the ticket pass. Block it and use `/lean4:disprove` or create a
mathematical-blocker ticket.

## Handoff

Persist before context loss, stop budget, or manual interruption:

```bash
lean4-skills-paper-workflow handoff T-042 \
  --reason context-boundary \
  --completed "proved H-042-01" \
  --current-goal "⊢ ..." \
  --failed-approach "linarith: nonlinear term remains" \
  --new-knowledge "equation (4.17) uses μ < 1, already in main assumptions" \
  --remaining "prove H-042-02" \
  --next-action "search weighted L2 coercivity lemmas" \
  --file Paper/Section4.lean
```

A handoff is both embedded in the ticket record and written append-only under
`.formalization/handoffs/`. When the ticket is mapped to GitHub, it can also be
posted as an issue comment.

## GitHub projection

Publishing is explicit and requires approval:

```bash
lean4-skills-paper-workflow github-sync \
  --repo owner/repo --spec --tickets --approved
```

The helper publishes blockers-first. When the installed `gh` supports native
`--parent` and `--blocked-by`, it uses those relationships. Otherwise the issue
body still carries IDs and local `tickets.json` remains authoritative.

Never let a tracker edit silently rewrite local mathematical truth. Reconcile
tracker changes into the local manifest deliberately.

## Verification and final audit

A paper claim reaches `verified` only through an evidence gate:

```bash
lean4-skills-paper-workflow verify-claim P-LEM-034 \
  --build passed --sorries 0 --axioms passed \
  --statement-text /tmp/P-LEM-034.statement
```

Here `axioms=passed` means the project's axiom audit found no *unauthorized*
trust-basis change. Standard Lean foundations and explicitly approved external
premises are governed by project policy.

Final audit computes the target transitive closure and reports unresolved claims,
trusted external premises, unapproved premises, and related open tickets:

```bash
lean4-skills-paper-workflow final-audit
```

## Invariants

1. No remaining-task list exists only in chat.
2. Every settled grill answer is persisted before the next decision question.
3. Paper claim IDs are stable.
4. Paper Claim DAG and Ticket DAG remain distinct.
5. Proof sessions cannot silently change locked paper statements.
6. Paper-original claims cannot be smuggled into the trust boundary as assumptions.
7. `verified` requires build pass, zero sorry, axiom audit pass, and verified claim dependencies.
8. One fresh session owns one ticket.
9. A repeatedly oversized ticket is split rather than endlessly resumed.
10. Every unfinished session writes a durable handoff.
11. GitHub is a projection; local manifests and Lean files remain sufficient for recovery.
