---
name: paper-to-spec
description: Synthesize a durable formalization spec and macro paper-claim DAG from resolved grill decisions
user_invocable: true
argument-hint: '[--publish-github]'
---

# Lean4 Paper To Spec

This is a **synthesis** workflow. It records decisions already made; it does not
start a new interview.

Read [paper-workflow.md](../skills/lean4/references/paper-workflow.md).

## Usage

Run:

```bash
lean4-skills-paper-workflow validate
lean4-skills-paper-workflow grill-check
```

If grill readiness is false, route back to `/lean4:paper-grill`. Do not invent
missing policy just to fill the spec.

## Actions

1. Read the durable decisions, `.formalization/CONTEXT.md`, paper source, and relevant Lean repo context.
2. Extract the **macro Paper Claim DAG**: stable IDs for paper definitions/lemmas/propositions/theorems in the selected verification boundary. Do not explode every proof into Lean helper lemmas yet.
3. Register approved external premises separately with `add-assumption`; never encode a paper-original claim as an assumption.
4. Add claims with source locators and mathematical `depends_on` edges.
5. Set target claim IDs with `set-targets`.
6. Write `FORMALIZATION_SPEC.md` containing at least:
   - goal and target theorem(s),
   - verification boundary and out-of-scope,
   - trust boundary with every approved premise class,
   - source/provenance rules,
   - Paper Claim DAG summary,
   - statement-lock/revision policy,
   - ticket-sizing and handoff policy,
   - verification/final-audit criteria,
   - unresolved source ambiguities, if any.
7. Record the spec fingerprint:

```bash
lean4-skills-paper-workflow record-spec --path FORMALIZATION_SPEC.md
```

If source interpretation exposes a real decision not covered by grill, do not
silently choose. Record the ambiguity and return to `paper-grill` for that one
decision, then resume spec synthesis.

If macro claim extraction itself reaches a context boundary, persist a planning
handoff before stopping:

```bash
lean4-skills-paper-workflow planning-handoff \
  --reason context-boundary \
  --completed "mapped sections 1-3" \
  --remaining "map section 4 and main theorem closure" \
  --next-action "resume claim extraction from section 4"
```

## GitHub

Local spec is authoritative. Publish only after explicit user approval:

```bash
lean4-skills-paper-workflow github-sync --repo owner/repo --spec --approved
```

Do not start implementation from the parent spec. Next step for multi-session
work is `/lean4:paper-to-tickets`.

## Safety

The spec records planning decisions; it does not authorize replacing a
paper-original result with an assumption or changing a locked statement. Keep
the Paper Claim DAG mathematical and leave execution dependencies to tickets.

## See Also

Use `/lean4:paper-grill` for unresolved policy decisions, then
`/lean4:paper-to-tickets` to derive the independent Ticket DAG.
