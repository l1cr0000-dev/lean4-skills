# Lean 4 Skills

Lean 4 workflow pack for AI coding agents. Gives your agent a structured
prove/review/golf loop, mathlib search, axiom checking, and safety guardrails.
The workflows are host-agnostic — Claude Code, Codex, Gemini CLI, Cursor, and
others all use the same core skill; only the invocation surface differs.

[简体中文](README.zh-CN.md)

## About This Fork

This repository is a downstream fork of
[Cameron Freer's lean4-skills](https://github.com/cameronfreer/lean4-skills).
The upstream project, its contributors, and its original documentation are the
foundation of this work. This fork preserves the upstream MIT license, copyright
notice, authorship, and citation information.

In addition to synchronized upstream releases, this fork adds an optional
paper-scale formalization layer: durable planning state, Paper Claim and Ticket
DAGs, statement locks, explicit trust-boundary tracking, cross-session handoffs,
and final audits. It is additive: upstream theorem-level workflows remain
authoritative and are not replaced.

For the original project, upstream releases, and upstream issues, visit
[cameronfreer/lean4-skills](https://github.com/cameronfreer/lean4-skills).
Fork-specific work and issues belong in
[l1cr0000-dev/lean4-skills](https://github.com/l1cr0000-dev/lean4-skills).

## Quick Start

| Host | Recommended installation | What you get | Details |
|---|---|---|---|
| Claude Code | Native plugin (Tier 3) | Skill + `/lean4:*` commands, hooks, guardrails, subagents, helper runtime | [Claude Code](INSTALLATION.md#claude-code-native-plugin) |
| Codex | Native plugins (Tier 3) | Full Lean runtime plus optional friendly paper-skill adapter | [Codex](INSTALLATION.md#openai-codex-cli) |
| Other Agent Skills hosts (Gemini, Antigravity, Copilot, Cursor, Windsurf, OpenCode, …) | Skill-only quick install | Instructions + references (documented, not CI-verified) | [Installation guide](INSTALLATION.md) |
| Any host, full runtime | Portable checkout (Tier 2) | Skill + wrappers + helper scripts | [Portable](INSTALLATION.md#portable-checkout--helper-runtime-all-hosts) |

**Claude Code** (run in chat):

```text
/plugin marketplace add l1cr0000-dev/lean4-skills
/plugin install lean4
```

**Codex** (in your shell):

```bash
codex plugin marketplace add l1cr0000-dev/lean4-skills --ref main
codex plugin add lean4@lean4-skills
codex plugin add lean4-codex@lean4-skills
```

> Host-native skill installers generally provide the instructions and
> references only. Use the portable runtime when you also need the bundled
> wrappers and scripts; Claude Code and Codex provide native full-plugin
> installations.

## Workflows

| Workflow | Description |
|---|---|
| draft | Draft Lean declaration skeletons from informal claims |
| formalize | Interactive formalization — drafting plus guided proving |
| autoformalize | Autonomous end-to-end formalization from informal sources |
| prove | Guided cycle-by-cycle theorem proving |
| autoprove | Autonomous multi-cycle proving with explicit stop budgets |
| disprove | Guided counterexample search with certified refutation |
| checkpoint | Save point (per-file + project build, axiom check, commit) |
| review | Read-only quality review |
| refactor | Leverage mathlib, extract helpers, simplify proof strategies |
| golf | Improve proofs for directness, clarity, performance, and brevity |
| learn | Interactive teaching and mathlib exploration |
| diagnose | Diagnostics and migration help |

**Claude Code:** invoke as `/lean4:<name>`. **Other hosts:** follow the corresponding workflow in [SKILL.md](plugins/lean4/skills/lean4/SKILL.md).

Typical session: `draft` (or `formalize` / `autoformalize`) → `prove` (or `autoprove`) → `review` → `refactor` → `golf` → `checkpoint` → `git push`. Use `disprove` instead of `prove` to refute a statement rather than prove it.

For paper-scale work across fresh contexts, use the additive orchestration
layer: `paper-grill` → `paper-to-spec` → `paper-to-tickets` →
`paper-frontier` → `paper-implement` → `paper-final-audit`. It preserves the
theorem-level workflows and records durable planning state in `.formalization/`.

CLI-like inputs to the seven parameter-heavy commands are validated by a host-agnostic parser — see the [Command Invocation Contract](plugins/lean4/skills/lean4/references/command-invocation.md).

## The Shared Proof Cycle

The proving workflows (`prove`, `autoprove`, `formalize`, and `autoformalize`) share one cycle — **Plan → Work → Checkpoint → Review → Replan → Continue/Stop** — where each sorry gets a mathlib search, tactic attempts, and validation, and being stuck forces a review + replan. Statement and header changes belong to the synthesis workflows (`formalize` / `autoformalize`); `prove` and `autoprove` keep declaration headers immutable. Editing `.lean` files without a command runs one bounded pass — fix the immediate issue, then hand off to the right workflow — with the [Blocked-Goal Triage loop](plugins/lean4/skills/lean4/references/sorry-filling.md#blocked-goal-triage) for a goal that resists it. Details: [cycle-engine.md](plugins/lean4/skills/lean4/references/cycle-engine.md).

## Verification

CI gates every PR: full documentation lint, semantic contract suites, hook and wrapper runtime tests on Linux and macOS Bash 3.2, and pinned shellcheck/ruff/mypy/actionlint. Hosts marked "documented" in the Quick Start table follow verified setup patterns but are not CI-tested.

## Lean LSP MCP (Optional, Recommended)

The skill works standalone, but pairs best with [lean-lsp-mcp](https://github.com/oOo0oOo/lean-lsp-mcp): live goal inspection, mathlib search, and typically much faster feedback than repeated full builds. See [INSTALLATION.md → MCP Server](INSTALLATION.md#lean-lsp-mcp-server-all-hosts) for registration on any host, including the Claude Code scope trade-off for subagent visibility.

## Documentation

- [INSTALLATION.md](INSTALLATION.md) — installation tiers, host sections, MCP setup
- [SKILL.md](plugins/lean4/skills/lean4/SKILL.md) — core skill reference
- [Commands](plugins/lean4/commands/) — command documentation
- [References](plugins/lean4/skills/lean4/references/) — cycle engine, mathlib style, proof golfing, tactic patterns, grind, metaprogramming, and more
- [lean4-contribute](plugins/lean4-contribute/README.md) — opt-in helper for filing bug reports, feature requests, and insights from your editor
- [CHANGELOG.md](CHANGELOG.md) — version history
- [MIGRATION.md](plugins/lean4/MIGRATION.md) — migrating from v3 (Claude Code)

## Contributing

For fork-specific work, open issues and pull requests at
https://github.com/l1cr0000-dev/lean4-skills. Improvements that are broadly
useful beyond this fork should also be considered for the
[upstream project](https://github.com/cameronfreer/lean4-skills). With the
`lean4-contribute` plugin installed, your agent may suggest filing upstream bug
reports, feature requests, or insights at natural stopping points — drafting
starts only after you opt in, and every draft is shown in full before anything
is sent.

## License & Citation

MIT licensed. See [LICENSE](LICENSE) for more information.

Citing this repository is highly appreciated but not required by the license. See also [CITATION.cff](CITATION.cff).

```bibtex
@software{lean4-skills,
  author = {Cameron Freer},
  title = {Lean 4 {Skills}: Theorem proving skill and workflow pack for {AI} coding agents},
  url = {https://github.com/cameronfreer/lean4-skills},
  month = oct,
  year = {2025}
}
```
