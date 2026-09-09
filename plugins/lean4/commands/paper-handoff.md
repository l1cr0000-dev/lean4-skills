---
name: paper-handoff
description: Persist an unfinished Lean paper ticket so a fresh context can resume without reconstructing history
user_invocable: true
argument-hint: '<ticket-id>'
---

# Lean4 Paper Handoff

Use before context loss, a session stop, a long-blocker boundary, or manual
interruption. The goal is to make the next fresh session independent of this chat.

## Usage

## Actions

Persist at least:

- what was completed;
- exact current Lean goal (when available);
- failed approaches and why they failed;
- new mathematical/source knowledge discovered this session;
- remaining work;
- blocker, if any;
- exact next action;
- files touched.

Example:

```bash
lean4-skills-paper-workflow handoff T-042 \
  --reason context-boundary \
  --completed "proved H-042-01" \
  --current-goal "⊢ C₁ * ‖u‖ ^ 2 ≤ ..." \
  --failed-approach "nlinarith timed out after normalization" \
  --new-knowledge "paper equation (4.17) uses μ < 1, already available" \
  --remaining "prove H-042-02" \
  --next-action "search weighted L2 coercivity lemmas" \
  --file Paper/Section4.lean
```

Use `--blocked` only when the ticket cannot proceed until an external/new ticket
resolves something; ordinary context exhaustion should leave it resumable `partial`.

If the ticket is mapped to GitHub, project the handoff as an issue comment:

```bash
lean4-skills-paper-workflow github-sync-handoff T-042
```

## Safety

Do not rely on the GitHub comment as the sole record; the local handoff is primary.
Use `--blocked` only for a genuine external dependency, never to hide an
unfinished proof or a missing statement-review decision.

## See Also

Resume through `/lean4:paper-implement`; use `/lean4:paper-status` to inspect
the resulting partial or blocked ticket state.
