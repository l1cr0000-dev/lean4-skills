---
name: paper-sync
description: Explicitly project local paper spec, ticket DAG, ticket completion, or handoff state to GitHub Issues
user_invocable: true
argument-hint: '--repo=owner/name'
---

# Lean4 Paper GitHub Sync

Local `.formalization/*.json` files are machine truth. GitHub Issues are the
collaboration projection.

## Usage

## Actions

Never publish a newly generated ticket breakdown without explicit user approval.
After approval:

```bash
lean4-skills-paper-workflow github-sync \
  --repo owner/repo --spec --tickets --approved
```

The helper creates blockers first and uses GitHub CLI native `--parent` and
`--blocked-by` relationships when the installed version exposes those flags.
Otherwise it still publishes self-contained issue bodies and records the mapping
locally.

After a ticket is actually verified and locally closed:

```bash
lean4-skills-paper-workflow github-close-ticket T-042
```

After a partial/blocked session:

```bash
lean4-skills-paper-workflow github-sync-handoff T-042
```

Do not import arbitrary tracker edits back into local state automatically; review
and reconcile them as planning changes.

## Safety

The `--approved` flag is mandatory for new issue publication. Failed GitHub CLI
calls leave the local manifests authoritative and must not block local recovery.

## See Also

Use `/lean4:paper-to-spec` and `/lean4:paper-to-tickets` before publishing;
use `/lean4:paper-status` to inspect the durable issue mappings.

Issue titles and bodies include stable local IDs so collaborators can identify
the authoritative record. A manually edited issue is discussion material until
its change is deliberately reconciled into the local plan.

Sync is optional collaboration support, not a project initialization or
verification requirement.
