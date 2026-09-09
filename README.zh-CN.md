# Lean 4 Skills

[English](README.md)

面向 AI 编程代理的 Lean 4 工作流工具集，提供有结构的证明、审查、重构、
mathlib 搜索、axiom 检查与安全护栏。核心工作流可用于 Claude Code、Codex、
Gemini CLI、Cursor 等不同宿主；差异主要在命令入口和运行时集成方式。

## 来源与致谢

本仓库是 [Cameron Freer 的 lean4-skills](https://github.com/cameronfreer/lean4-skills)
的下游 fork。原项目及其贡献者提供了本项目的基础实现、文档和工作流设计。

我们保留原项目的 MIT 许可证、版权声明、作者署名和引用信息。本 fork 不代表
上游作者或上游项目的官方发布；如需原始项目、上游版本或上游议题，请访问
[cameronfreer/lean4-skills](https://github.com/cameronfreer/lean4-skills)。

本 fork 的仓库地址为
[l1cr0000-dev/lean4-skills](https://github.com/l1cr0000-dev/lean4-skills)。除同步
上游更新外，它增加了可选的论文级形式化编排层。该层是增量能力，不替换任何
上游的 theorem-level workflow。

## 快速开始

| 宿主 | 推荐安装方式 | 获得的能力 |
|---|---|---|
| Claude Code | 原生插件 | Skill、`/lean4:*` 命令、hooks、护栏与辅助运行时 |
| Codex | 原生插件 | Skill、受信任 hooks 与绝对路径辅助运行时 |
| 其他 Agent Skill 宿主 | 仅安装 skill | 指令与参考文档 |
| 任意宿主 | Portable checkout | 完整辅助运行时 |

Claude Code 中执行：

```text
/plugin marketplace add l1cr0000-dev/lean4-skills
/plugin install lean4
```

Codex 终端中执行：

```bash
codex plugin marketplace add l1cr0000-dev/lean4-skills --ref main
codex plugin add lean4@lean4-skills
```

完整的宿主安装说明见 [INSTALLATION.md](INSTALLATION.md)。如果你只需要上游
原版，请使用上游仓库的安装说明。

## 核心工作流

| 工作流 | 用途 |
|---|---|
| `draft` | 根据非形式化陈述起草 Lean 声明骨架 |
| `formalize` | 交互式形式化：起草并引导证明 |
| `autoformalize` | 从来源到证明的自动化端到端形式化 |
| `prove` | 按周期推进的交互式证明 |
| `autoprove` | 带停止预算的自动化证明 |
| `disprove` | 寻找并认证反例 |
| `checkpoint` | 保存检查点并运行构建/axiom 验证 |
| `review` | 只读 Lean 证明质量审查 |
| `refactor` | 利用 mathlib、抽取辅助引理、改进结构 |
| `golf` | 改进已编译证明的清晰度、直接性和性能 |
| `learn` | 交互式学习与仓库/Mathlib 探索 |
| `diagnose` | 诊断环境、构建与迁移问题 |

典型流程是：`draft`（或 `formalize` / `autoformalize`）→ `prove`（或
`autoprove`）→ `review` → `refactor` → `golf` → `checkpoint`。

Claude Code 使用 `/lean4:<workflow>`；在 Codex 中使用 `$lean4` 并说明希望
执行的工作流。完整语义见
[SKILL.md](plugins/lean4/skills/lean4/SKILL.md)。

## 本 fork 的论文级形式化层

适用于需要跨越多个新会话、持续数周或更久的论文形式化项目：

```text
paper-grill
  → paper-to-spec
  → paper-to-tickets
  → paper-frontier
  → paper-implement
  → paper-final-audit
```

辅助命令包括 `paper-handoff`、`paper-status`、`paper-review` 与 `paper-sync`。

这个层级具有以下边界：

- 保留并调用既有的 `prove`、`autoprove`、`formalize`、`disprove`、`review` 与
  `checkpoint`，不重新实现底层定理证明器。
- 将数学上的 **Paper Claim DAG** 与执行上的 **Ticket DAG** 分开；一个 claim
  可以对应多个 ticket。
- 将跨会话状态保存到 `FORMALIZATION_SPEC.md` 和 `.formalization/`，而不是依赖
  聊天记录。
- 使用 statement fingerprint lock 防止证明会话暗中修改已确认的命题。
- 显式记录 `foundation`、`mathlib`、`formal_import` 与 `trusted_external` 的
  信任边界；论文原始 claim 不能伪装成 assumption。
- GitHub Issues 只是协作投影；本地 `.formalization/*.json` 才是权威机器状态。

入口是 `/lean4:paper-grill`。在 Codex 中，可请 `$lean4` 执行 paper-grill
workflow；命令行辅助工具是 `lean4-skills-paper-workflow`。

最终审计会将目标 claim 闭包标记为以下之一：

- `kernel-checked-without-trusted-external-results`
- `kernel-checked-conditional-on-trusted-external-results`
- `incomplete`

详见 [论文级工作流参考](plugins/lean4/skills/lean4/references/paper-workflow.md)。

## 质量与验证

持续集成覆盖文档与契约检查、Python 测试、ruff、mypy、shellcheck、wrapper
smoke test、macOS Bash 3.2 兼容性测试，以及 Lean 文件门禁集成测试。

提交前请保持变更范围清晰，并运行与改动有关的测试。论文级工作流的单元测试为：

```bash
python3 plugins/lean4/tests/test_paper_workflow.py
```

## 文档

- [安装指南](INSTALLATION.md)
- [核心 Skill](plugins/lean4/skills/lean4/SKILL.md)
- [命令文档](plugins/lean4/commands/)
- [参考资料](plugins/lean4/skills/lean4/references/)
- [更新记录](CHANGELOG.md)
- [从 v3 迁移](plugins/lean4/MIGRATION.md)

## 贡献

Fork 专属问题与改动请在
[l1cr0000-dev/lean4-skills](https://github.com/l1cr0000-dev/lean4-skills) 提交。
若改动适用于更广泛的 Lean 4 社区，请优先考虑向
[上游项目](https://github.com/cameronfreer/lean4-skills) 反馈或贡献。

## 许可证与引用

本项目遵循 [MIT License](LICENSE)。请在复制、分发或派生作品时保留原有版权
与许可证文本。

引用本项目时，请尊重原作者并使用原项目的引用信息：

```bibtex
@software{lean4-skills,
  author = {Cameron Freer},
  title = {Lean 4 {Skills}: Theorem proving skill and workflow pack for {AI} coding agents},
  url = {https://github.com/cameronfreer/lean4-skills},
  month = oct,
  year = {2025}
}
```
