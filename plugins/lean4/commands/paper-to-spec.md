---
name: paper-to-spec
description: Freeze the paper source/target/trust boundary and synthesize the macro Paper Claim DAG
user_invocable: true
argument-hint: '[--publish-github]'
---

# Lean4 Paper To Spec

This is a synthesis workflow. It records settled mathematical intent; it does not
start proving or assign implementation work.

Read [paper-workflow.md](../skills/lean4/references/paper-workflow.md).

## Usage

```bash
lean4-skills-paper-workflow validate
lean4-skills-paper-workflow grill-check
```

If grill readiness is false, return to `/lean4:paper-grill`. Never invent missing
scope/trust policy just to complete the spec.

## Actions

1. Read durable decisions, `.formalization/CONTEXT.md`, the paper source, and
   relevant Lean repository context.
2. Freeze the paper source fingerprint and the exact external target: quantifiers,
   hypotheses, conclusion, domain, and selected main theorem(s). Architecture `init`
   safely fills a missing base-v2 source SHA; it never replaces a mismatch silently.
3. Extract the macro **Paper Claim DAG** with stable IDs for paper definitions,
   lemmas, propositions, theorems, and corollaries in the selected boundary.
4. Register approved external premises separately with `add-assumption`; never
   encode a paper-original result as an assumption.
5. Add source locators, `depends_on`, `uses_assumptions`, Lean statement mappings,
   and selected target IDs.
6. Write `FORMALIZATION_SPEC.md` containing scope, out-of-scope material, trust
   boundary, source/provenance rules, Claim DAG summary, statement-lock policy,
   architecture policy, comparator policy, ticket/ownership/handoff rules, and
   final completion criteria.
7. Record the spec fingerprint:

```bash
lean4-skills-paper-workflow record-spec --path FORMALIZATION_SPEC.md
```

Initialize and configure the architecture companion:

```bash
python3 <plugin-root>/lib/paper_architecture.py init
# init freezes a missing base-v2 project.source.sha256 from the current paper bytes
python3 <plugin-root>/lib/paper_architecture.py configure-verification \
  --primary-target P-MAIN \
  --full-paper-policy skip
```

Set `full_paper_policy` from the durable grill decision:

- `skip` — main-theorem closure is the final scope;
- `after-main` — continue to full-paper verification only after Stage 1 passes;
- `ask` — pause after Stage 1 and ask the user.

Before any proof ticket becomes executable, perform a second-pass **Dependency
Coverage Audit** over every claim in the active closure. For each claim, scan its
actual proof text/references and record the reconciled result:

```bash
python3 <plugin-root>/lib/paper_architecture.py record-dependency-scan \
  --claim P-MAIN \
  --source-ref "paper §1, proof of Theorem 1.1" \
  --internal-claim P-PROP-3.1 \
  --assumption A-EXT-01 \
  --complete
```

The recorded internal claims and assumptions must exactly match the Claim DAG. If
the scan discovers an omitted dependency, revise the DAG first and repeat the
scan. This prevents a formally clean but source-incomplete main-theorem closure.

The next workflow is `/lean4:paper-to-tickets`, which derives Formal Obligations
before creating execution tickets. Do not jump from paper sections directly to
implementation tickets.

If source interpretation exposes a real unresolved decision, persist it and route
back to `paper-grill`. If planning crosses a context boundary, write a durable
planning handoff rather than relying on chat memory.

## GitHub

Local spec/state is authoritative. Publish only after explicit approval:

```bash
lean4-skills-paper-workflow github-sync --repo owner/repo --spec --approved
```

## Safety

Do not weaken the target, change the trust boundary, or hide a paper-original
claim as an external premise. Do not mark dependency coverage complete from a
summary alone; inspect the source proof and reconcile every discovered reference.

The Claim DAG records mathematical dependency; Formal Obligations record Lean
proof responsibility; Tickets record execution dependency.

## See Also

Use `/lean4:paper-grill` for unresolved decisions and
`/lean4:paper-to-tickets` after source/target/claim planning is frozen.
