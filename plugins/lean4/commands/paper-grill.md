---
name: paper-grill
description: Stateful interview that freezes paper formalization scope, trust boundary, statement policy, and completion criteria
user_invocable: true
argument-hint: '--source=PATH [--title="..."] [--repo=owner/name]'
---

# Lean4 Paper Grill

Use this before a multi-session paper formalization. It is a **decision-making**
workflow, not a proving workflow.

Read [paper-workflow.md](../skills/lean4/references/paper-workflow.md) first.

## Usage

If `.formalization/project.json` does not exist, initialize it:

```bash
lean4-skills-paper-workflow init --source <PATH> --title <TITLE> [--repo owner/name]
```

If it exists, resume from disk. Never ask the user to repeat a decision already
recorded in `.formalization/decisions.json`.

## Actions

Ask **one substantive question at a time**. For each question:

1. inspect the paper/repo first and do not ask what source files can answer;
2. give concrete options when useful;
3. state a recommended option and the consequence of alternatives;
4. wait for the user's answer;
5. immediately persist the resolved answer with `record-decision` before asking the next question;
6. if a project term becomes stable, also persist it with `add-term`.

Do not batch all questions into one message.

At minimum settle:

- `scope`: target theorem(s), what counts as paper-original, and whether Stage 1
  verifies the full transitive internal dependency closure;
- `trust_boundary`: mathlib/formal imports/trusted external results and provenance requirements;
- `statement_policy`: locked statements, missing hypotheses, counterexamples, and who may approve revisions;
- `completion_policy`: build/sorry/axiom/source-mapping requirements and desired final trust level.

As part of `scope`, present an explicit **full-paper continuation choice**. Treat
it like a two-button decision when the host UI supports choices:

- **只验证主定理** → persist policy `skip`;
- **主定理通过后继续整篇文章形式化** → persist policy `after-main`.

If the user does not want to decide yet, allow **主定理通过后再问我** → `ask`.
This is a durable project policy, not an implementation detail. Choosing `skip`
means a verified main-theorem closure is a valid final project result; it does not
mean weakening dependencies inside that closure.

Persist the answer with `record-decision`, for example:

```bash
lean4-skills-paper-workflow record-decision \
  --category scope \
  --question "主定理通过后是否继续整篇文章形式化？" \
  --answer "只验证主定理" \
  --recommendation "full_paper_policy=skip"
```

`paper-to-spec` must translate that durable decision into
`verification_scope.json` via `configure-verification --full-paper-policy ...`.

Useful follow-up categories include source mapping, helper-lemma policy, ticket sizing,
GitHub publishing policy, and concurrency/worktree policy.

Check readiness after every few resolved decisions:

```bash
lean4-skills-paper-workflow grill-check
```

Do not move to spec synthesis until it reports `ready: true`. If planning itself
spans several sessions, all resolved answers are already durable.

## Safety

When ready, summarize the frozen boundary and recommend `/lean4:paper-to-spec`.
Do not start proving claims in this workflow.

Never let a remembered chat answer replace a durable decision. Do not silently
promote `skip` to full-paper work after Stage 1. A later user may explicitly
change the policy, and Stage-1 proof evidence must be reused rather than redone.

Never publish issues, unlock statements, or alter the mathematical trust boundary here.

## See Also

Continue with `/lean4:paper-to-spec` only after `grill-check` reports ready.
For the state schema and invariants, read
[paper-workflow.md](../skills/lean4/references/paper-workflow.md).
