# Lean 4 Plugin

> **Native host adapters.** This directory implements the Claude Code plugin
> (hooks, guardrails, slash commands) and the Codex plugin (skill discovery,
> absolute-path SessionStart context, prompt validation, advisory guardrails).
> The underlying SKILL.md, references, wrappers, and scripts remain canonical
> and host-agnostic. See the [root README](../../README.md) for installation.

Unified Lean 4 plugin for theorem proving, interactive learning, and formalization.

## Commands

| Command | Description |
|---------|-------------|
| `/lean4:draft` | Draft Lean declaration skeletons from informal claims |
| `/lean4:formalize` | Interactive formalization — drafting plus guided proving |
| `/lean4:autoformalize` | Autonomous end-to-end formalization from informal sources |
| `/lean4:prove` | Guided cycle-by-cycle theorem proving with explicit checkpoints |
| `/lean4:autoprove` | Autonomous multi-cycle theorem proving with explicit stop budgets |
| `/lean4:disprove` | Guided counterexample search with certified refutation |
| `/lean4:checkpoint` | Save progress with a safe commit checkpoint |
| `/lean4:review` | Read-only code review of Lean proofs |
| `/lean4:refactor` | Leverage mathlib, extract helpers, simplify proof strategies |
| `/lean4:golf` | Improve Lean proofs for directness, clarity, performance, and brevity |
| `/lean4:learn` | Interactive teaching and mathlib exploration |
| `/lean4:diagnose` | Diagnostics, cleanup, and migration help |

### Paper-scale orchestration

| Command | Description |
|---------|-------------|
| `/lean4:paper-grill` | Stateful interview that freezes paper formalization scope, trust boundary, statement policy, and completion criteria |
| `/lean4:paper-to-spec` | Freeze the paper source/target/trust boundary and synthesize the macro Paper Claim DAG |
| `/lean4:paper-to-tickets` | Derive formal obligations, then split them into fresh-context Lean ticket contracts |
| `/lean4:paper-frontier` | Compute contracted paper-formalization tickets that are actually ready for a fresh session |
| `/lean4:paper-implement` | Execute exactly one contracted paper-formalization ticket in a fresh context |
| `/lean4:paper-handoff` | Persist an unfinished Lean paper ticket so a fresh context can resume without reconstructing history |
| `/lean4:paper-status` | Show combined claim, dependency-coverage, obligation, contract, evidence, comparator, and scope state |
| `/lean4:paper-review` | Read-only audit of scope, dependency coverage, three DAGs, machine evidence, trust, and comparators |
| `/lean4:paper-sync` | Explicitly project local paper spec, ticket DAG, ticket completion, or handoff state to GitHub Issues |
| `/lean4:paper-final-audit` | Compute final machine-evidence, trust, and architecture status for the selected target closure |

`/lean4:*` entries are Claude Code aliases; under Codex, invoke `$lean4` and
ask for the named workflow.

Each command's full semantics live in [commands/](commands/); worked
transcripts live in
[command-examples.md](skills/lean4/references/command-examples.md). CLI-like
inputs to the seven parameter-heavy commands are validated by a host-agnostic
parser — see the
[Command Invocation Contract](skills/lean4/references/command-invocation.md).

The paper commands are a durable orchestration layer for work that spans fresh
contexts. They preserve the existing theorem workflows and persist recovery
state under `.formalization/`; GitHub Issues remain a projection of that state.

**Without a command:** editing `.lean` files activates the skill for one
bounded pass — it fixes the immediate issue (a build error, a single sorry),
does not loop or escalate, and ends by suggesting the right command:
`draft`/`formalize` for statement work, `prove`/`autoprove` for proof work.
For a goal that resists the pass, it follows the
[Blocked-Goal Triage loop](skills/lean4/references/sorry-filling.md#blocked-goal-triage).

## The Cycle Engine (Shared)

The proving commands (`prove`, `autoprove`, `formalize`, `autoformalize`) run
one 6-phase cycle — **Plan → Work → Checkpoint → Review → Replan →
Continue/Stop** — discovering sorries via LSP, then per sorry: mathlib search,
tactic attempts, validation, staging only touched files. When stuck (same
blocker seen twice), both force a review + replan regardless of settings.
`prove` asks before continuing; `autoprove` auto-continues under stop budgets.
`disprove` shares the phase skeleton but specializes Phase 5 as **Accumulate**
(per-cycle evidence append) with dynamic evidence-seeded menus.

Commit behavior: `prove` defaults to `--commit=ask`, `autoprove` to
`--commit=auto`; both stage only files actually touched, never `git add -A`.

Full phase semantics, stuck definition, and deep-mode safety:
[cycle-engine.md](skills/lean4/references/cycle-engine.md).

## Safety Guardrails

Guardrails activate only in Lean project context (a directory tree containing
`lakefile.lean`, `lean-toolchain`, or `lakefile.toml`); outside Lean projects
they are silently skipped. Git operations fall into three tiers: **allow**
(status/diff/log/add/commit and other read-or-append ops, no gate),
**soft-gate** (collaboration ops like `git push` / `git commit --amend` /
`gh pr create` and path-scoped destructive ops — policy-controlled per op,
one-shot `LEAN4_GUARDRAILS_BYPASS=1` bypass in `ask` mode), and **hard-block**
(whole-worktree destructive ops like `git reset --hard` and `git clean -f` —
absolute, never bypassable).

The full policy — override environment variables, per-op collaboration
policies and their `host`/`ask`/`allow`/`block` modes, hard-blocked push
variants, destructive-op coverage, and bypass semantics — lives in
[GUARDRAILS.md](GUARDRAILS.md).

## LSP-First Approach

LSP tools are **normative** (required first-pass), not merely preferred:
`lean_goal` for exact goal state, the search ladder
(`lean_local_search` / `lean_leanfinder` / `lean_leansearch` / `lean_loogle`),
and `lean_multi_attempt` for candidate testing. Scripts provide sorry
analysis, axiom checking, and search fallback when LSP is unavailable;
compiler-guided repair is escalation-only. See the
[LSP-first protocol](skills/lean4/references/cycle-engine.md#lsp-first-protocol).

## Helper Runtime Discovery

Claude Code persists `LEAN4_PLUGIN_ROOT`, `LEAN4_SCRIPTS`, `LEAN4_REFS`, and
`LEAN4_PYTHON_BIN` through `CLAUDE_ENV_FILE` at SessionStart, and puts the
`bin/` wrappers on PATH. Native Codex documents no persistent environment:
after the hooks are trusted in `/hooks`, SessionStart injects absolute
`plugin_root` / `bin_dir` / `scripts_dir` / `refs_dir` / `preflight` context —
invoke wrappers by literal absolute path; do not assume shell exports.
To verify or troubleshoot either channel, run `lean4-skills-preflight`
(absolute path under Codex) or the `diagnose` workflow — see
[INSTALLATION.md](../../INSTALLATION.md) for per-host verification steps.

## Upgrading from v3

See [MIGRATION.md](MIGRATION.md) for the upgrade guide (including the
v4.6.0 rename of the diagnostic command to `/lean4:diagnose`).

## See Also

- [SKILL.md](skills/lean4/SKILL.md) - Core skill reference
- [Commands](commands/) - Command documentation
- [GUARDRAILS.md](GUARDRAILS.md) - Full guardrail policy
- [Scripts](lib/scripts/README.md) - Script reference
- [Custom Syntax](skills/lean4/references/lean4-custom-syntax.md) - Notations, macros, elaborators, DSLs
- [DSL Scaffold](skills/lean4/references/scaffold-dsl.md) - Copy-paste DSL template
- [References](skills/lean4/references/) - grind, simprocs, metaprogramming, linters, FFI, verso-docs, profiling
