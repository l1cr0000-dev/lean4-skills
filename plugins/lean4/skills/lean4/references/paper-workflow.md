# Paper Workflow Reference

This add-on wraps the existing lean4-skills theorem-level workflows with durable,
multi-session orchestration for formalizing a whole paper.

## Non-negotiable design rule

> Conversation context is disposable. `.formalization/`, Lean source files, and git must be sufficient for a fresh agent to resume.

The add-on intentionally does **not** replace `/lean4:prove`, `/lean4:autoprove`,
`/lean4:formalize`, `/lean4:disprove`, `/lean4:review`, or `/lean4:checkpoint`.
Those remain the proof engines. Paper workflow decides *what contract* one fresh
session should own and persists what happened.

## Architecture model

Large formalizations should not normally be organized as “paper section 1, then
section 2, then section 3”. Prefer proof-responsibility boundaries:

```text
External target
     ↓
Formal spec / Paper Claim DAG
     ↓
Formal Obligation DAG
     ├─ Generic mechanisms
     ├─ Arithmetic / parameter ledgers
     ├─ Analytic estimates and regularity
     ├─ Coherence / recurrence invariants
     └─ Literal paper data
     ↓
Actual instances
     ↓
Assembly
     ↓
Bridge to external target
     ↓
Independent comparator / final audit when required
```

This pattern is inspired by publicly visible architecture in large Lean
formalizations, including the public OpenAI Navier–Stokes repository: conditional
consumer interfaces, separate arithmetic ledgers, concrete `Actual...`
instantiations, late assembly, and a small final comparator adapter. It is an
**architectural inference from public artifacts**, not a claim about OpenAI's
private agent scheduler or prompts.

## Main command chain

The default paper-scale strategy is **target-first**: prove the main theorem and
its full transitive dependency closure before spending Lean time on unrelated
parts of the paper. Full-paper formalization is an explicit project choice, not
an automatic consequence of Stage 1 passing.

```text
paper-grill
  ↓
paper-to-spec
  ↓
Dependency Coverage Audit
  ↓
Stage 1 — main-theorem closure
  ↓
paper-to-tickets
  ├─ Formal Obligation DAG for the active target closure
  └─ Ticket DAG + ticket contracts
  ↓
paper-frontier → paper-implement → evidence
  ↓
verification-gate
  ├─ FAIL → repair/split/revise; do not expand the paper
  └─ PASS → inspect full_paper_policy
              ├─ skip → finish at main-theorem scope
              ├─ ask → ask user: stop or continue
              └─ after-main → expand Claim map, then promote-full-paper
                                  ↓
Stage 2 — full paper (only when selected)
  ↓
paper-to-tickets again for newly activated claims
  ↓
paper-frontier → paper-implement → evidence
  ↓
paper-final-audit
```

The public slash-command surface stays unchanged. The stage gate is implemented
by the internal architecture helper, so existing host command registries and
wrappers do not need a new command.

`paper-to-tickets` therefore means more than tracker slicing: for paper-scale
proofs it first establishes the formal proof architecture and only then derives
fresh-context execution tickets.


## Two-stage verification strategy

For a completed paper whose main theorem is the first concern, use the default
`target-first` strategy. Stage 1 verifies **the main theorem plus every internal
paper claim in its transitive dependency closure**. It is not the weak mode where
intermediate paper results are silently promoted to assumptions.

After the macro claim(s) for the main theorem have been registered, configure the
active target **and the user's desired stopping scope**:

```bash
python3 <plugin-root>/lib/paper_architecture.py init
python3 <plugin-root>/lib/paper_architecture.py configure-verification \
  --primary-target P-MAIN \
  --full-paper-policy skip
```

`full_paper_policy` is a durable three-state switch:

- `skip`: verify only the main-theorem transitive closure; a passed Stage 1 is a
  valid terminal project result;
- `after-main`: if Stage 1 passes, the project intends to continue to full-paper
  formalization;
- `ask`: defer the decision until Stage 1 passes, then explicitly ask the user
  whether to stop or continue.

The policy can be changed later without deleting Stage-1 Lean proofs:

```bash
python3 <plugin-root>/lib/paper_architecture.py set-full-paper-policy after-main
```

During Stage 1, obligation/ticket frontiers are scope-filtered. A pre-existing
ticket whose obligations belong only to an unrelated paper result fails the
architecture ticket gate with `ticket is outside the active verification stage`.
This prevents opportunistic full-paper work before the main theorem is known to
close.

Check the gate with:

```bash
python3 <plugin-root>/lib/paper_architecture.py verification-gate --format json
```

The Stage-1 gate requires both:

1. the base target closure is verified with locked statements, build pass, zero
   sorry, axiom audit, approved assumptions, current spec fingerprint, and no open
   related base tickets; and
2. every active claim has a completed source-fingerprint-bound dependency scan
   matching its Claim DAG edges and registered assumptions; and
3. the architecture audit is complete for the same closure, including obligation
   coverage, machine evidence, contract completion, and required comparators.

If Stage 1 passes, first inspect the durable policy. With `skip`, stop and run the
final audit at the main-theorem scope. With `ask`, present the user two choices:
**只验证主定理** or **继续整篇文章形式化** and persist the selection with
`set-full-paper-policy`. Only with `after-main` should you do planning-only
expansion of the Paper Claim DAG across the rest of the selected paper. Do not
begin proving the new claims yet. Then promote:

```bash
python3 <plugin-root>/lib/paper_architecture.py promote-full-paper --all-claims
```

Promotion snapshots the passed main-theorem audits in
`verification_scope.json`, switches the active stage to `full-paper`, and changes
`project.targets` to the selected full-paper targets. Newly activated claims are
therefore visible as uncovered/unverified work immediately. Run
`paper-to-tickets` again to create only the new obligations/contracts needed for
Stage 2. Existing verified Stage-1 work is reused.

This ordering deliberately spends cheap source-analysis time before expensive
Lean proof time:

```text
main theorem closure fails  → stop/revise early
main theorem closure passes + skip → finish with a certified main-theorem result
main theorem closure passes + after-main → only then pay for full-paper formalization
```

Projects that intentionally want exhaustive formalization from the beginning can
configure `--strategy full-paper` with explicit full targets. This is recorded as
`main_theorem_gate=explicit-full-paper-bypass`; it never fabricates a passed
Stage-1 gate, and the full selected scope must still pass final audit.

## Additive durable state

The original paper workflow manifests remain authoritative for planning/trust
state. The architecture companion is additive and does not migrate or rewrite
schema-v2 projects.

```text
paper-repo/
├── FORMALIZATION_SPEC.md
├── .formalization/
│   ├── project.json                 # base workflow schema v2
│   ├── CONTEXT.md
│   ├── decisions.json
│   ├── terms.json
│   ├── assumptions.json
│   ├── claims.json                  # Paper Claim DAG
│   ├── tickets.json                 # Ticket DAG
│   ├── obligations.json             # companion schema v1
│   ├── ticket_contracts.json        # companion schema v1
│   ├── comparators.json             # companion schema v1
│   ├── dependency_coverage.json     # source-proof dependency scans
│   ├── verification_scope.json      # stage gate + full-paper policy switch
│   ├── architecture_transaction.json # temporary rollback journal only
│   ├── generated/
│   │   └── dispatches/              # zero-context session packets
│   ├── evidence/                    # append-only obligation evidence
│   └── handoffs/
└── Paper/
    └── *.lean
```

Machine truth lives locally. GitHub Issues are a projection for collaboration,
visibility, and native blocking edges. If GitHub is unavailable, local state and
git remain sufficient to continue.

The architecture helper is invoked directly from the plugin runtime:

```bash
python3 <plugin-root>/lib/paper_architecture.py ...
```

Under native Codex use the absolute `plugin_root` injected at SessionStart; do not
assume a persistent shell variable.

## Grill discipline

`paper-grill` asks one decision question at a time and records every resolved
answer immediately. At minimum settle:

- `scope`: target theorem(s) and dependency closure;
- `trust_boundary`: which external mathematics may be imported or trusted;
- `statement_policy`: what happens when formalization reveals a wrong/missing hypothesis;
- `completion_policy`: what evidence counts as finished.

Before spec synthesis run:

```bash
lean4-skills-paper-workflow grill-check
```

## Trust boundary and target freeze

External inputs are separate from paper claims:

- `foundation`: accepted foundational Lean policy;
- `mathlib`: theorem already available in mathlib;
- `formal_import`: theorem imported from another checked Lean development;
- `trusted_external`: informal external result explicitly accepted as a premise.

A paper-original claim never becomes an assumption merely because it is hard.
It belongs in `claims.json` and must be proved if it lies in the selected target
closure.

Before decomposition, freeze the exact external target: source theorem,
quantifiers, hypotheses, conclusion, domain, and any required reference/comparator
statement. This prevents an internally convenient theorem from silently replacing
the theorem the project set out to verify.

## Dependency Coverage Audit

The Claim DAG is not trusted merely because an agent extracted it once. Before
proof tickets execute, perform a second source pass for every claim in the active
target closure. Record the actual proof references and reconcile them with the
claim's `depends_on` and `uses_assumptions` fields:

```bash
python3 <plugin-root>/lib/paper_architecture.py record-dependency-scan \
  --claim P-MAIN \
  --source-ref "paper §1, proof of Theorem 1.1" \
  --internal-claim P-PROP-3.1 \
  --assumption A-EXT-01 \
  --complete
```

A completed scan is bound to the frozen paper source fingerprint. Architecture
`init` fills the base v2 `project.source.sha256` when that field is empty. It never
silently replaces a non-empty mismatch. An intentional paper revision must run
`freeze-source --replace`, after which existing scans become stale. If the scan
discovers a dependency not present in the Claim DAG or assumption mapping, update
the base planning state first; the helper refuses to record an inconsistent scan.

`check-ticket` and machine acceptance both refuse proof work while dependency
coverage for the active closure is incomplete. This is a completeness guard on
source extraction; it does not claim that automated natural-language dependency
extraction is mathematically infallible.

## Three DAGs

### 1. Paper Claim DAG

`claims.json` records mathematical dependency:

```text
P-LEM-021 → P-PROP-044 → P-THM-001
```

Paper IDs are stable. This graph changes only when source analysis or an explicit
planning revision changes the understood mathematics.

### 2. Formal Obligation DAG

`obligations.json` records proof architecture: what must be established for the
formal construction to close. It may be finer than the paper and may contain
Lean-facing responsibilities that are not named paper lemmas.

Typical kinds:

- `statement`: formal target/interface boundary;
- `definition_data`: primitive structures, objects, and exact data identities;
- `generic_lemma`: reusable abstract theorem independent of final parameters;
- `arithmetic_ledger`: exponent, scale, budget, and parameter inequalities;
- `analytic_estimate`: substantive PDE/analysis estimate;
- `regularity_support`: smoothness, support, integrability, topology;
- `coherence_invariant`: recurrence/state preservation;
- `actual_instance`: instantiate generic APIs with the paper's literal data;
- `assembly`: consume completed obligations to construct a result/witness;
- `comparator_bridge`: connect the internal result to the frozen external target;
- `audit`: build/sorry/axiom/alignment/integration verification.

Typical layers are `spec`, `generic`, `actual`, `assembly`, `bridge`, and `audit`.

The obligation DAG is where conditional-consumer design lives. If final assembly
only needs properties `H1 ... Hn`, define that interface and prove the consumer
first when useful; then solve each `Hi` independently. This reduces coupling and
makes parallel proof search possible.

Separate arithmetic ledgers from analytic estimates when practical. Pure
`ring`/`linarith`/`norm_num` obligations should not force the same worker to hold
all PDE context.

### 3. Ticket DAG

`tickets.json` records execution dependency:

```text
T-031 formalize/lock interface
  ↓
T-032 solve generic estimate
  ↓
T-033 instantiate actual parameters
  ↓
T-034 assemble target bridge
```

One claim can require many obligations and tickets. One ticket can close several
small, coherent obligations. Do not collapse the three DAGs into one.

## Obligation records

Each obligation should be zero-context inspectable. Record:

- stable `O-...` ID, title, kind, layer, objective;
- paper claim IDs it supports;
- formal obligation dependencies;
- explicit mathematical inputs/outputs;
- source references;
- `read_files` and `owned_files` when known;
- executable acceptance commands where applicable;
- forbidden changes;
- risk and count of independent hard unknowns;
- eventual append-only evidence.

An obligation with more than two independent hard unknowns is a strong signal to
split before execution.

A completed obligation must not depend on an incomplete obligation. Satisfaction
is recorded only after its contracted ticket is closed with verification evidence.

## Ticket contracts

The base `tickets.json` record remains the collaboration/execution node. Its
companion `ticket_contracts.json` entry makes the worker boundary explicit:

- linked obligations;
- obligations this ticket is allowed to mark complete;
- selected worker (`formalize`, `prove`, `autoprove`, `disprove`, `integrate`, `review`, `research`);
- read-only vs mutating mode;
- required locked paper statements;
- owned files and read-only files;
- executable acceptance commands;
- forbidden changes;
- risk, hard unknowns, and token estimate.

A mutating approved contract must own files. A non-research approved contract must
have an executable acceptance command. This turns “work on Proposition 4.2” into
a verifiable proof contract rather than a vague session goal.

For human-readable planning, export the Ticket DAG as Markdown:

```bash
lean4-skills-paper-workflow render-tickets
```

This creates `.formalization/generated/tickets/README.md` plus one Markdown file
per ticket. It is a projection for reading and review; `.formalization/*.json`
remains authoritative.

## File ownership and optional parallelism

Default execution remains one fresh context per ticket. For larger projects,
`parallel-frontier` may propose conflict-free groups based on declared file
ownership.

This is advisory only. If parallel workers are actually used:

1. give each worker a separate worktree/process;
2. maintain one writer per file;
3. allow shared read-only dependencies;
4. integrate only after each ticket's own checks pass;
5. create repair/integration tickets for downstream breakage instead of allowing
   workers to edit arbitrary neighboring modules.

Do not interpret “different theorem names” as proof that two workers can safely
edit the same file.

## Ticket sizing

A ticket is sized for one fresh context, not for an exact token count. Default
metadata assumes a 220k nominal window with advisory values:

- target around 140k tokens;
- soft handoff around 175k tokens.

Runtime token accounting is host-dependent. Mathematical uncertainty is the
stronger signal: split when a contract contains multiple independent hard
unknowns, ownership expands repeatedly, or the same parent consumes several full
sessions without converging.

## Statement locks

Translate and review a paper statement, then fingerprint-lock it:

```bash
lean4-skills-paper-workflow set-statement P-LEM-034 \
  --file Paper/Section4.lean \
  --declaration lemma_4_2 \
  --statement-text /tmp/P-LEM-034.statement \
  --lock
```

Proof sessions may change proof bodies and add helpers inside contract ownership,
but may not alter locked paper statements. If a change is mathematically
necessary, unlock deliberately with a reason; this invalidates prior proof trust
and routes the claim back to planning.

## Runnable frontier

Base readiness alone is insufficient after the architecture layer is initialized.
A ticket is runnable only when:

1. base status is `ready` or resumable `partial`;
2. base ticket blockers are closed;
3. base required claims are verified;
4. an approved architecture contract exists;
5. required claim statements are locked;
6. dependency coverage is complete for the active Paper Claim closure;
17. **every** linked obligation belongs to the active verification stage;
8. every external obligation dependency is satisfied;
9. no linked obligation is blocked/rejected;
10. mutating ownership and executable acceptance requirements are met.

Check both:

```bash
lean4-skills-paper-workflow frontier
python3 <plugin-root>/lib/paper_architecture.py check-ticket T-042
```

Obligations linked to the same ticket may depend on one another and be solved
sequentially inside that single contract; only dependencies outside the contract
must already be satisfied.

## Zero-context dispatch packet

Before implementation render:

```bash
python3 <plugin-root>/lib/paper_architecture.py render-dispatch T-042
```

The generated `paper-dispatch/v1` JSON packages:

- project/spec fingerprint and context budget;
- ticket identity, blockers, and base requirements;
- worker/risk/hard unknowns;
- owned/read files, acceptance commands, forbidden changes;
- linked obligations and their dependencies;
- mapped paper claims and statement fingerprints;
- last handoff;
- proof-engine/run-contract hint.

A fresh agent should start from this packet and then read only the relevant paper
fragments and Lean imports. Whole-paper rereads are reserved for contracts that
explicitly require source-wide analysis.

## Compiler/Lean feedback loop

For proof-producing tickets, success is not “the proof looks right”. The inner
loop is deterministic:

```text
inspect exact goal
  ↓
search repo/mathlib
  ↓
edit within owned files
  ↓
LSP/file check or compile
  ↓
read diagnostics
  ↓
repair
  ↺
acceptance commands all pass
```

Use LSP first when available for fast goal/search feedback. Compiler-guided
repair remains the proof loop, but final architecture acceptance is independently
executed by `verify-ticket` / `satisfy-obligation` from the approved contract. A
manual `passed` flag or natural-language confidence cannot discharge an obligation.

## Handoff

Persist before context loss, stop budget, or manual interruption:

```bash
lean4-skills-paper-workflow handoff T-042 \
  --reason context-boundary \
  --completed "proved local coercivity helper" \
  --current-goal "⊢ ..." \
  --failed-approach "linarith: nonlinear term remains" \
  --new-knowledge "equation (4.17) uses μ < 1, already in main assumptions" \
  --remaining "close endpoint estimate" \
  --next-action "search weighted L2 coercivity lemmas" \
  --file Paper/Section4.lean
```

The handoff is embedded in the ticket record and written append-only. A resumed
session renders a new dispatch packet so the latest handoff and durable state are
included automatically.

## Obligation completion evidence

After the base ticket is closed, independently execute the frozen acceptance
commands:

```bash
python3 <plugin-root>/lib/paper_architecture.py verify-ticket T-042
```

The resulting `ticket-verification/v2` evidence records exact commands, exit codes,
stdout/stderr hashes, contract fingerprint, git/toolchain metadata when available,
and hashes of relevant current Lean/source files. A nonzero exit code cannot be
converted into PASS by prose.

Then satisfy only obligations listed in that contract's
`completes_obligations`:

```bash
python3 <plugin-root>/lib/paper_architecture.py satisfy-obligation O-ANA-017 \
  --ticket T-042 \
  --evidence "contracted estimate completed"
```

If valid ticket evidence does not already exist, `satisfy-obligation` runs the
acceptance commands itself. The note is descriptive only. Evidence files are
hashed; contract drift, evidence tampering, or relevant source drift invalidates
the evidence until re-verification. Research contracts may not complete formal
obligations.

## Independent comparator

A comparator is optional unless the spec requires one. It is useful when there is
an independent formal statement of the external theorem/problem and the project
must prove exact alignment rather than only an internal formulation.

A comparator record stores:

- target paper claim;
- reference source/declaration;
- solution declaration;
- executable comparison/check commands;
- permitted axioms;
- whether verification is required for completion;
- append-only machine evidence after verification.

`verify-comparator` executes the registered `check_commands`; it does not accept a
manual PASS as a substitute for process success. When required, keep the reference
target independent of the proof root where
possible. Do not prove a self-authored weakened target and call that external
alignment.

## GitHub projection

Publishing remains explicit:

```bash
lean4-skills-paper-workflow github-sync \
  --repo owner/repo --spec --tickets --approved
```

The local base Ticket DAG remains the tracker source of truth. Obligation and
contract detail should be summarized in issue bodies/updates as useful, but a
tracker edit never silently rewrites local mathematical state.

## Verification and final audit

Paper claims still reach `verified` only through the original statement fingerprint,
build, zero-sorry, axiom, and verified-claim-dependency gate.

Final completion now requires **both** audits:

```bash
lean4-skills-paper-workflow final-audit
python3 <plugin-root>/lib/paper_architecture.py architecture-audit
```

The architecture audit additionally checks:

- dependency coverage is complete and current for every target-closure claim;
- every target-closure claim has obligation coverage;
- all transitive obligations needed by that coverage are satisfied;
- machine evidence is present, untampered, contract-consistent, and current;
- related implementation contracts/tickets are no longer open;
- required comparators are machine verified;
- companion manifests are structurally valid.

The stage gate reports one explicit result label:

```text
PASS_KERNEL_CLOSED
PASS_FORMALLY_IMPORTED
PASS_CONDITIONAL_TRUSTED_EXTERNAL
INCOMPLETE
```

A conditional result must always be reported with its external premises. Only
after both reports are complete, the selected scope is terminal, and the Lean
project checks pass may the project phase be set to `complete`.

## Invariants

1. No remaining-task list exists only in chat.
2. Every settled grill answer is persisted before the next decision question.
3. Paper claim IDs and obligation IDs are stable and never recycled casually.
4. Paper Claim DAG, Formal Obligation DAG, and Ticket DAG remain distinct.
5. Every active claim has completed source dependency coverage before proof execution.
6. Every target-closure claim has explicit obligation coverage before final completion.
7. Proof sessions cannot silently change locked paper statements.
8. Paper-original claims cannot be smuggled into the trust boundary as assumptions.
9. Approved implementation tickets have explicit worker contracts.
10. Mutating contracts have file ownership; non-research contracts have executable acceptance.
11. Research contracts may not complete formal proof obligations.
12. One fresh session owns one ticket contract by default.
13. More than two independent hard unknowns is a split signal, not a reason to consume unlimited contexts.
14. Completed obligations have machine evidence and cannot depend on incomplete obligations.
15. Every unfinished implementation session writes a durable handoff.
16. Parallelism never permits two writers to own the same file in one proposed batch.
17. A required comparator must pass independently before architecture completion.
18. GitHub is a projection; local manifests, evidence, Lean files, and git remain sufficient for recovery.
19. Machine acceptance evidence is produced by executing approved commands, not by agent assertion.
20. Scope transitions are recoverable through the architecture transaction journal.
21. Final reports preserve the exact trust/result label; conditional verification is never called assumption-free.
