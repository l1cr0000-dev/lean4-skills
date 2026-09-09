# Paper Workflow Add-on

Installed as an additive orchestration layer. Existing lean4-skills theorem-level
workflows remain authoritative for proof search, LSP interaction, review, and
checkpointing.

The paper layer adds three durable graphs — Paper Claims, Formal Obligations, and
execution Tickets — plus source dependency coverage, fresh-context contracts,
zero-context dispatch packets, machine-executed evidence, transactional scope
switching, and optional independent comparators. Existing schema-v2 paper projects
remain authoritative and are not migrated.

Entry point: `/lean4:paper-grill`.
Reference: `skills/lean4/references/paper-workflow.md`.

Default policy is target-first: verify the main theorem's full internal dependency
closure first. Full-paper verification is explicit: `skip`, `after-main`, or
`ask`. Proof tickets cannot execute until active-closure dependency coverage is
complete, and obligations cannot be satisfied from a manual PASS assertion.

Final result labels distinguish kernel-closed/formally-imported verification from
verification conditional on approved informal external premises.
