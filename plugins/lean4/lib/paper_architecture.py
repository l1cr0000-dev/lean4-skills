#!/usr/bin/env python3
"""Formalization-architecture companion for the lean4-skills paper workflow.

This module is deliberately additive.  ``paper_workflow.py`` remains the owner of
paper decisions, claims, tickets, statement locks, handoffs, and tracker state.
This companion inserts the missing architecture layer between the Paper Claim DAG
and the Ticket DAG:

    paper claims -> formal obligations -> ticket contracts -> Lean proof engines

It also records optional independent comparator contracts and can derive a
zero-context dispatch packet for one implementation ticket.  The design is
inspired by the public structure of large Lean developments (generic interfaces,
actual parameter instantiation, assembly, bridge/comparator), not by any claim of
access to a private OpenAI orchestration system.
"""

from __future__ import annotations

import argparse
import contextlib
import hashlib
import json
import os
import subprocess
import sys
import tempfile
import time
from collections import Counter, deque
from collections.abc import Iterable
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, cast

ARCH_SCHEMA_VERSION = 1

OBLIGATION_KINDS = {
    "statement",
    "definition_data",
    "generic_lemma",
    "arithmetic_ledger",
    "analytic_estimate",
    "regularity_support",
    "coherence_invariant",
    "actual_instance",
    "assembly",
    "comparator_bridge",
    "audit",
    "other",
}
OBLIGATION_LAYERS = {"spec", "generic", "actual", "assembly", "bridge", "audit"}
OBLIGATION_STATUSES = {"draft", "ready", "blocked", "satisfied", "rejected"}
CONTRACT_STATUSES = {"draft", "approved"}
WORKERS = {
    "formalize",
    "prove",
    "autoprove",
    "disprove",
    "integrate",
    "review",
    "research",
}
RISKS = {"low", "medium", "high"}
COMPARATOR_STATUSES = {"draft", "ready", "verified", "failed"}
VERIFICATION_STRATEGIES = {"target-first", "full-paper"}
VERIFICATION_STAGES = {"main-theorem", "full-paper"}
FULL_PAPER_POLICIES = {"ask", "skip", "after-main"}
GATE_STATUSES = {"pending", "passed", "explicit-full-paper-bypass"}
TRUST_LEVELS = {"KERNEL_CLOSED", "FORMALLY_IMPORTED", "CONDITIONAL_TRUSTED_EXTERNAL"}


class ArchitectureError(RuntimeError):
    pass


def now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def safe_repo_path(root: Path, value: str) -> Path:
    raw = Path(value)
    if raw.is_absolute() or ".." in raw.parts:
        raise ArchitectureError(
            f"repository path must be relative and stay within the project: {value}"
        )
    resolved = (root / raw).resolve()
    try:
        resolved.relative_to(root.resolve())
    except ValueError as exc:
        raise ArchitectureError(
            f"repository path escapes project root: {value}"
        ) from exc
    return resolved


def best_effort_command(root: Path, command: list[str]) -> str | None:
    try:
        result = subprocess.run(
            command, cwd=root, capture_output=True, text=True, timeout=15, check=False
        )
    except (OSError, subprocess.SubprocessError):
        return None
    if result.returncode != 0:
        return None
    return (result.stdout or result.stderr).strip() or None


def read_json(path: Path) -> Any:
    try:
        with path.open("r", encoding="utf-8") as handle:
            return json.load(handle)
    except FileNotFoundError as exc:
        raise ArchitectureError(f"file not found: {path}") from exc
    except json.JSONDecodeError as exc:
        raise ArchitectureError(f"invalid JSON in {path}: {exc}") from exc


def atomic_write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = json.dumps(value, ensure_ascii=False, indent=2, sort_keys=False) + "\n"
    fd, tmp_name = tempfile.mkstemp(prefix=f".{path.name}.", dir=str(path.parent))
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            handle.write(payload)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(tmp_name, path)
    finally:
        with contextlib.suppress(FileNotFoundError):
            os.unlink(tmp_name)


def stable_unique(values: Iterable[str] | None) -> list[str]:
    return list(dict.fromkeys(values or []))


def by_id(items: Iterable[dict[str, Any]], kind: str) -> dict[str, dict[str, Any]]:
    out: dict[str, dict[str, Any]] = {}
    for item in items:
        item_id = item.get("id")
        if not isinstance(item_id, str) or not item_id:
            raise ArchitectureError(f"every {kind} must have a non-empty string id")
        if item_id in out:
            raise ArchitectureError(f"duplicate {kind} id: {item_id}")
        out[item_id] = item
    return out


def find_cycle(index: dict[str, dict[str, Any]], edge_key: str) -> list[str] | None:
    color = dict.fromkeys(index, 0)
    stack: list[str] = []

    def visit(node: str) -> list[str] | None:
        color[node] = 1
        stack.append(node)
        for dep in index[node].get(edge_key, []):
            if dep not in index:
                continue
            if color[dep] == 0:
                cycle = visit(dep)
                if cycle:
                    return cycle
            elif color[dep] == 1:
                pos = stack.index(dep)
                return [*stack[pos:], dep]
        stack.pop()
        color[node] = 2
        return None

    for node in index:
        if color[node] == 0:
            cycle = visit(node)
            if cycle:
                return cycle
    return None


def transitive_closure(
    index: dict[str, dict[str, Any]], roots: Iterable[str], edge_key: str
) -> set[str]:
    seen: set[str] = set()
    queue = deque(roots)
    while queue:
        node = queue.popleft()
        if node in seen or node not in index:
            continue
        seen.add(node)
        queue.extend(index[node].get(edge_key, []))
    return seen


class Store:
    def __init__(self, root: Path) -> None:
        self.root = root.resolve()
        self.dir = self.root / ".formalization"
        self.project_path = self.dir / "project.json"
        self.claims_path = self.dir / "claims.json"
        self.tickets_path = self.dir / "tickets.json"
        self.assumptions_path = self.dir / "assumptions.json"
        self.scope_path = self.dir / "verification_scope.json"
        self.obligations_path = self.dir / "obligations.json"
        self.contracts_path = self.dir / "ticket_contracts.json"
        self.comparators_path = self.dir / "comparators.json"
        self.coverage_path = self.dir / "dependency_coverage.json"
        self.transaction_path = self.dir / "architecture_transaction.json"
        self.generated_dir = self.dir / "generated" / "dispatches"
        self.evidence_dir = self.dir / "evidence"

    def base_initialized(self) -> bool:
        return (
            self.project_path.exists()
            and self.claims_path.exists()
            and self.tickets_path.exists()
        )

    def _manifest(self, path: Path, name: str) -> dict[str, Any]:
        value = read_json(path)
        if not isinstance(value, dict):
            raise ArchitectureError(f"{name} must contain an object")
        if value.get("schema_version") != ARCH_SCHEMA_VERSION:
            raise ArchitectureError(
                f"{name} schema_version must be {ARCH_SCHEMA_VERSION}"
            )
        if not isinstance(value.get("items"), list):
            raise ArchitectureError(f"{name}.items must be a list")
        return value

    def project(self) -> dict[str, Any]:
        value = read_json(self.project_path)
        if not isinstance(value, dict):
            raise ArchitectureError("project.json must contain an object")
        return value

    def claims(self) -> list[dict[str, Any]]:
        value = read_json(self.claims_path)
        if not isinstance(value, list):
            raise ArchitectureError("claims.json must contain a list")
        return value

    def tickets(self) -> list[dict[str, Any]]:
        value = read_json(self.tickets_path)
        if not isinstance(value, list):
            raise ArchitectureError("tickets.json must contain a list")
        return value

    def assumptions(self) -> list[dict[str, Any]]:
        if not self.assumptions_path.exists():
            return []
        value = read_json(self.assumptions_path)
        if not isinstance(value, list):
            raise ArchitectureError("assumptions.json must contain a list")
        return value

    def verification_scope(self) -> dict[str, Any]:
        value = read_json(self.scope_path)
        if not isinstance(value, dict):
            raise ArchitectureError("verification_scope.json must contain an object")
        if value.get("schema_version") != ARCH_SCHEMA_VERSION:
            raise ArchitectureError(
                f"verification_scope.json schema_version must be {ARCH_SCHEMA_VERSION}"
            )
        return value

    def obligations_manifest(self) -> dict[str, Any]:
        return self._manifest(self.obligations_path, "obligations.json")

    def contracts_manifest(self) -> dict[str, Any]:
        return self._manifest(self.contracts_path, "ticket_contracts.json")

    def comparators_manifest(self) -> dict[str, Any]:
        return self._manifest(self.comparators_path, "comparators.json")

    def coverage_manifest(self) -> dict[str, Any]:
        return self._manifest(self.coverage_path, "dependency_coverage.json")

    def obligations(self) -> list[dict[str, Any]]:
        return cast(list[dict[str, Any]], self.obligations_manifest()["items"])

    def contracts(self) -> list[dict[str, Any]]:
        return cast(list[dict[str, Any]], self.contracts_manifest()["items"])

    def comparators(self) -> list[dict[str, Any]]:
        return cast(list[dict[str, Any]], self.comparators_manifest()["items"])

    def coverage(self) -> list[dict[str, Any]]:
        return cast(list[dict[str, Any]], self.coverage_manifest()["items"])


def empty_manifest() -> dict[str, Any]:
    return {"schema_version": ARCH_SCHEMA_VERSION, "items": []}


def default_verification_scope(project: dict[str, Any]) -> dict[str, Any]:
    targets = stable_unique(project.get("targets", []))
    return {
        "schema_version": ARCH_SCHEMA_VERSION,
        "strategy": "target-first",
        "stage": "main-theorem",
        "primary_targets": targets,
        "full_targets": [],
        "full_targets_policy": "explicit",
        "full_paper_policy": "ask",
        "main_theorem_gate": {
            "status": "pending",
            "checked_at": None,
            "base_audit": None,
            "architecture_audit": None,
        },
        "promoted_at": None,
        "updated_at": now_iso(),
    }


def write_project_targets(store: Store, targets: Iterable[str]) -> None:
    project = store.project()
    project["targets"] = stable_unique(targets)
    project["updated_at"] = now_iso()
    atomic_write_json(store.project_path, project)


def scope_targets_from_value(scope: dict[str, Any]) -> list[str]:
    if scope.get("stage") == "full-paper":
        return stable_unique(scope.get("full_targets", []))
    return stable_unique(scope.get("primary_targets", []))


def scope_targets(store: Store) -> list[str]:
    return scope_targets_from_value(store.verification_scope())


def active_claim_closure(
    store: Store, targets: Iterable[str] | None = None
) -> set[str]:
    claim_index = by_id(store.claims(), "claim")
    roots = stable_unique(targets if targets is not None else scope_targets(store))
    return transitive_closure(claim_index, roots, "depends_on") if roots else set()


def active_obligation_ids(
    store: Store, targets: Iterable[str] | None = None
) -> set[str]:
    claim_closure = active_claim_closure(store, targets)
    obligation_index = by_id(store.obligations(), "obligation")
    direct = {
        item_id
        for item_id, item in obligation_index.items()
        if set(item.get("claim_ids", [])) & claim_closure
    }
    return (
        transitive_closure(obligation_index, direct, "depends_on") if direct else set()
    )


def paper_source_path(store: Store, project: dict[str, Any] | None = None) -> Path:
    value = project if project is not None else store.project()
    source = value.get("source", {})
    if not isinstance(source, dict):
        raise ArchitectureError("project.source must be an object")
    source_path = source.get("path")
    if not isinstance(source_path, str) or not source_path:
        raise ArchitectureError("paper source path is missing")
    path = Path(source_path)
    if not path.is_absolute():
        path = store.root / path
    path = path.resolve()
    # Absolute paper inputs outside the Lean repository are supported; the
    # fingerprint, rather than repository ownership, is the trust anchor.
    with contextlib.suppress(ValueError):
        path.relative_to(store.root)
    if not path.exists() or not path.is_file():
        raise ArchitectureError(f"paper source file missing: {source_path}")
    return path


def freeze_source_fingerprint(store: Store, *, replace: bool = False) -> str:
    project = store.project()
    source = project.get("source", {})
    if not isinstance(source, dict):
        raise ArchitectureError("project.source must be an object")
    path = paper_source_path(store, project)
    actual = sha256_file(path)
    existing = source.get("sha256")
    if isinstance(existing, str) and existing:
        if existing == actual:
            return actual
        if not replace:
            raise ArchitectureError(
                "paper source fingerprint mismatch; use freeze-source --replace only after an explicit source revision"
            )
    source["sha256"] = actual
    project["source"] = source
    project["updated_at"] = now_iso()
    atomic_write_json(store.project_path, project)
    return actual


def cmd_freeze_source(store: Store, args: argparse.Namespace) -> None:
    print(freeze_source_fingerprint(store, replace=args.replace))


def cmd_init(store: Store, _args: argparse.Namespace) -> None:
    if not store.base_initialized():
        raise ArchitectureError(
            "base paper workflow is not initialized; run lean4-skills-paper-workflow init first"
        )
    store.generated_dir.mkdir(parents=True, exist_ok=True)
    store.evidence_dir.mkdir(parents=True, exist_ok=True)
    for path in (
        store.obligations_path,
        store.contracts_path,
        store.comparators_path,
        store.coverage_path,
    ):
        if not path.exists():
            atomic_write_json(path, empty_manifest())
    if not store.scope_path.exists():
        atomic_write_json(store.scope_path, default_verification_scope(store.project()))

    # Base paper_workflow.py v2 initializes source.sha256 to null.  Freeze it
    # additively here so a fresh project can enter dependency-coverage audit
    # without hand-editing project.json.  Never overwrite a non-empty mismatch.
    source = store.project().get("source", {})
    if not isinstance(source, dict):
        raise ArchitectureError("project.source must be an object")
    if not source.get("sha256"):
        freeze_source_fingerprint(store)
    else:
        integrity = source_integrity(store)
        if not integrity["ok"]:
            raise ArchitectureError(str(integrity["error"]))

    errors, warnings = validate_state(store)
    if errors:
        raise ArchitectureError("architecture state invalid:\n- " + "\n- ".join(errors))
    for warning in warnings:
        print(f"warning: {warning}", file=sys.stderr)
    print(store.obligations_path)


def new_obligation(args: argparse.Namespace) -> dict[str, Any]:
    return {
        "id": args.id,
        "title": args.title,
        "kind": args.kind,
        "layer": args.layer,
        "objective": args.objective,
        "claim_ids": stable_unique(args.claim),
        "depends_on": stable_unique(args.depends_on),
        "inputs": stable_unique(args.input),
        "outputs": stable_unique(args.output),
        "source_refs": stable_unique(args.source_ref),
        "read_files": stable_unique(args.read_file),
        "owned_files": stable_unique(args.owned_file),
        "acceptance_commands": stable_unique(args.accept),
        "forbidden_changes": stable_unique(args.forbid),
        "risk": args.risk,
        "hard_unknowns": args.hard_unknowns,
        "status": "draft" if args.draft else "ready",
        "blocker": None,
        "evidence": None,
        "created_at": now_iso(),
        "updated_at": now_iso(),
    }


def cmd_add_obligation(store: Store, args: argparse.Namespace) -> None:
    manifest = store.obligations_manifest()
    items = manifest["items"]
    if args.id in by_id(items, "obligation"):
        raise ArchitectureError(f"obligation already exists: {args.id}")
    if not args.id.startswith("O-"):
        raise ArchitectureError("obligation IDs must start with O-")
    items.append(new_obligation(args))
    atomic_write_json(store.obligations_path, manifest)
    errors, _ = validate_state(store)
    if errors:
        items.pop()
        atomic_write_json(store.obligations_path, manifest)
        raise ArchitectureError("obligation rejected:\n- " + "\n- ".join(errors))
    print(args.id)


def cmd_set_obligation_deps(store: Store, args: argparse.Namespace) -> None:
    manifest = store.obligations_manifest()
    index = by_id(manifest["items"], "obligation")
    item = index.get(args.id)
    if not item:
        raise ArchitectureError(f"unknown obligation: {args.id}")
    old = list(item.get("depends_on", []))
    item["depends_on"] = stable_unique(args.depends_on)
    item["updated_at"] = now_iso()
    atomic_write_json(store.obligations_path, manifest)
    errors, _ = validate_state(store)
    if errors:
        item["depends_on"] = old
        atomic_write_json(store.obligations_path, manifest)
        raise ArchitectureError("dependency update rejected:\n- " + "\n- ".join(errors))
    print(args.id)


def cmd_approve_obligations(store: Store, args: argparse.Namespace) -> None:
    manifest = store.obligations_manifest()
    index = by_id(manifest["items"], "obligation")
    ids = list(index) if args.all else stable_unique(args.id)
    if not ids:
        raise ArchitectureError(
            "approve-obligations requires --all or at least one --id"
        )
    for item_id in ids:
        item = index.get(item_id)
        if not item:
            raise ArchitectureError(f"unknown obligation: {item_id}")
        if item["status"] == "draft":
            item["status"] = "ready"
            item["updated_at"] = now_iso()
    atomic_write_json(store.obligations_path, manifest)
    print(json.dumps(ids, ensure_ascii=False))


def obligation_frontier(store: Store) -> list[dict[str, Any]]:
    items = store.obligations()
    index = by_id(items, "obligation")
    active = active_obligation_ids(store)
    out: list[dict[str, Any]] = []
    for item in items:
        if item["id"] not in active:
            continue
        if item.get("status") != "ready":
            continue
        if all(
            index[dep].get("status") == "satisfied"
            for dep in item.get("depends_on", [])
        ):
            out.append(item)
    return out


def cmd_obligation_frontier(store: Store, _args: argparse.Namespace) -> None:
    payload = [
        {
            "id": item["id"],
            "title": item["title"],
            "kind": item["kind"],
            "layer": item["layer"],
            "risk": item["risk"],
            "hard_unknowns": item["hard_unknowns"],
        }
        for item in obligation_frontier(store)
    ]
    print(json.dumps(payload, ensure_ascii=False, indent=2))


def cmd_block_obligation(store: Store, args: argparse.Namespace) -> None:
    manifest = store.obligations_manifest()
    item = by_id(manifest["items"], "obligation").get(args.id)
    if not item:
        raise ArchitectureError(f"unknown obligation: {args.id}")
    item["status"] = "blocked"
    item["blocker"] = {
        "reason": args.reason,
        "next_action": args.next_action,
        "at": now_iso(),
    }
    item["updated_at"] = now_iso()
    atomic_write_json(store.obligations_path, manifest)
    print(args.id)


def new_contract(args: argparse.Namespace) -> dict[str, Any]:
    return {
        "id": f"C-{args.ticket_id}",
        "ticket_id": args.ticket_id,
        "obligation_ids": stable_unique(args.obligation),
        "completes_obligations": stable_unique(args.completes_obligation),
        "worker": args.worker,
        "read_only": args.read_only,
        "requires_locked_claims": stable_unique(args.requires_locked_claim),
        "owned_files": stable_unique(args.owned_file),
        "read_files": stable_unique(args.read_file),
        "acceptance_commands": stable_unique(args.accept),
        "forbidden_changes": stable_unique(args.forbid),
        "risk": args.risk,
        "hard_unknowns": args.hard_unknowns,
        "estimate_tokens": args.estimate_tokens,
        "status": "approved" if args.approved else "draft",
        "created_at": now_iso(),
        "updated_at": now_iso(),
    }


def cmd_bind_ticket(store: Store, args: argparse.Namespace) -> None:
    manifest = store.contracts_manifest()
    contracts = manifest["items"]
    ticket_index = by_id(store.tickets(), "ticket")
    if args.ticket_id not in ticket_index:
        raise ArchitectureError(f"unknown base-workflow ticket: {args.ticket_id}")
    if any(item.get("ticket_id") == args.ticket_id for item in contracts):
        raise ArchitectureError(f"ticket already has a contract: {args.ticket_id}")
    obligations = by_id(store.obligations(), "obligation")
    obligation_ids = stable_unique(args.obligation)
    if not obligation_ids:
        raise ArchitectureError("bind-ticket requires at least one --obligation")
    for item_id in obligation_ids:
        if item_id not in obligations:
            raise ArchitectureError(f"unknown obligation: {item_id}")
    completes = stable_unique(args.completes_obligation)
    if any(item_id not in obligation_ids for item_id in completes):
        raise ArchitectureError(
            "--completes-obligation must be included in --obligation"
        )
    contracts.append(new_contract(args))
    atomic_write_json(store.contracts_path, manifest)
    errors, _ = validate_state(store)
    if errors:
        contracts.pop()
        atomic_write_json(store.contracts_path, manifest)
        raise ArchitectureError("ticket contract rejected:\n- " + "\n- ".join(errors))
    print(args.ticket_id)


def cmd_approve_contracts(store: Store, args: argparse.Namespace) -> None:
    manifest = store.contracts_manifest()
    contracts = manifest["items"]
    by_ticket = {item["ticket_id"]: item for item in contracts}
    ids = list(by_ticket) if args.all else stable_unique(args.ticket)
    if not ids:
        raise ArchitectureError(
            "approve-contracts requires --all or at least one --ticket"
        )
    old_values: dict[str, tuple[str, str | None]] = {}
    for ticket_id in ids:
        item = by_ticket.get(ticket_id)
        if not item:
            raise ArchitectureError(f"ticket has no contract: {ticket_id}")
        old_values[ticket_id] = (item.get("status", "draft"), item.get("updated_at"))
        item["status"] = "approved"
        item["updated_at"] = now_iso()
    atomic_write_json(store.contracts_path, manifest)
    errors, _ = validate_state(store)
    if errors:
        for ticket_id, (status, updated_at) in old_values.items():
            by_ticket[ticket_id]["status"] = status
            by_ticket[ticket_id]["updated_at"] = updated_at
        atomic_write_json(store.contracts_path, manifest)
        raise ArchitectureError(
            "contract approval produced invalid state:\n- " + "\n- ".join(errors)
        )
    print(json.dumps(ids, ensure_ascii=False))


def merged_contract(store: Store, contract: dict[str, Any]) -> dict[str, Any]:
    obligation_index = by_id(store.obligations(), "obligation")
    obligations = [
        obligation_index[item] for item in contract.get("obligation_ids", [])
    ]

    def union(key: str) -> list[str]:
        values: list[str] = []
        for obligation in obligations:
            values.extend(obligation.get(key, []))
        values.extend(contract.get(key, []))
        return stable_unique(values)

    return {
        **contract,
        "owned_files": union("owned_files"),
        "read_files": union("read_files"),
        "acceptance_commands": union("acceptance_commands"),
        "forbidden_changes": union("forbidden_changes"),
    }


def ticket_check_reasons(store: Store, ticket_id: str) -> list[str]:
    ticket_index = by_id(store.tickets(), "ticket")
    claim_index = by_id(store.claims(), "claim")
    obligation_index = by_id(store.obligations(), "obligation")
    contracts = store.contracts()
    contract = next(
        (item for item in contracts if item.get("ticket_id") == ticket_id), None
    )
    reasons: list[str] = []
    ticket = ticket_index.get(ticket_id)
    if not ticket:
        return [f"unknown ticket: {ticket_id}"]
    if ticket.get("status") not in {"ready", "partial", "in_progress"}:
        reasons.append(
            f"base ticket is not startable/resumable: {ticket.get('status')}"
        )
    if not contract:
        return [*reasons, "no architecture ticket contract"]
    if contract.get("status") != "approved":
        reasons.append("architecture ticket contract is not approved")
    internal = set(contract.get("obligation_ids", []))
    active = active_obligation_ids(store)
    coverage = dependency_coverage_audit(store, scope_targets(store))
    if not coverage["complete"]:
        details = stable_unique(
            coverage["missing_scans"]
            + coverage["stale_scans"]
            + coverage["inconsistent_scans"]
        )
        reasons.append(
            "dependency coverage audit is incomplete"
            + (": " + ", ".join(details) if details else "")
        )
    outside = sorted(internal - active)
    if outside:
        reasons.append(
            "ticket contains obligations outside the active verification stage: "
            + ", ".join(outside)
        )
    for obligation_id in internal:
        obligation = obligation_index.get(obligation_id)
        if not obligation:
            reasons.append(f"unknown linked obligation: {obligation_id}")
            continue
        if obligation.get("status") in {"blocked", "rejected"}:
            reasons.append(
                f"linked obligation {obligation_id} is {obligation.get('status')}"
            )
        for dep in obligation.get("depends_on", []):
            dep_item = obligation_index.get(dep)
            if dep_item is None:
                reasons.append(f"unknown obligation dependency: {dep}")
            elif dep not in internal and dep_item.get("status") != "satisfied":
                reasons.append(f"external obligation dependency not satisfied: {dep}")
    for blocker in ticket.get("blocked_by", []):
        if ticket_index.get(blocker, {}).get("status") != "closed":
            reasons.append(f"base ticket blocker open: {blocker}")
    for claim_id in ticket.get("requires_claims", []):
        if claim_index.get(claim_id, {}).get("status") != "verified":
            reasons.append(f"required paper claim not verified: {claim_id}")
    for claim_id in contract.get("requires_locked_claims", []):
        claim = claim_index.get(claim_id)
        if not claim:
            reasons.append(f"unknown locked-claim requirement: {claim_id}")
        elif not claim.get("statement", {}).get("locked"):
            reasons.append(f"required paper statement is not locked: {claim_id}")
    merged = merged_contract(store, contract)
    if not contract.get("read_only") and not merged.get("owned_files"):
        reasons.append("mutating ticket contract has no owned_files")
    if contract.get("worker") != "research" and not merged.get("acceptance_commands"):
        reasons.append("ticket contract has no executable acceptance command")
    return stable_unique(reasons)


def cmd_check_ticket(store: Store, args: argparse.Namespace) -> None:
    reasons = ticket_check_reasons(store, args.ticket_id)
    payload = {"ticket_id": args.ticket_id, "ready": not reasons, "reasons": reasons}
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    if reasons:
        raise ArchitectureError(
            "ticket architecture gate failed:\n- " + "\n- ".join(reasons)
        )


def dispatch_payload(store: Store, ticket_id: str) -> dict[str, Any]:
    reasons = ticket_check_reasons(store, ticket_id)
    if reasons:
        raise ArchitectureError("cannot render dispatch:\n- " + "\n- ".join(reasons))
    ticket = by_id(store.tickets(), "ticket")[ticket_id]
    claim_index = by_id(store.claims(), "claim")
    obligation_index = by_id(store.obligations(), "obligation")
    contract = next(
        item for item in store.contracts() if item["ticket_id"] == ticket_id
    )
    merged = merged_contract(store, contract)
    linked = [obligation_index[item] for item in contract["obligation_ids"]]
    claim_ids = stable_unique(
        [claim_id for item in linked for claim_id in item.get("claim_ids", [])]
        + ticket.get("claim_ids", [])
        + ticket.get("completes_claims", [])
    )
    claims = []
    for claim_id in claim_ids:
        claim = claim_index.get(claim_id)
        if not claim:
            continue
        claims.append(
            {
                "id": claim_id,
                "title": claim.get("title"),
                "status": claim.get("status"),
                "source": claim.get("source"),
                "statement": claim.get("statement"),
            }
        )
    project = store.project()
    spec = project.get("spec", {})
    return {
        "schema": "paper-dispatch/v1",
        "generated_at": now_iso(),
        "project": {
            "title": project.get("title"),
            "phase": project.get("phase"),
            "spec_path": spec.get("path"),
            "spec_sha256": spec.get("sha256"),
            "context_budget": project.get("context_budget"),
            "verification_scope": store.verification_scope(),
        },
        "ticket": {
            "id": ticket_id,
            "title": ticket.get("title"),
            "kind": ticket.get("kind"),
            "objective": ticket.get("objective"),
            "status": ticket.get("status"),
            "source_refs": ticket.get("source_refs", []),
            "last_handoff": ticket.get("last_handoff"),
        },
        "contract": {
            "worker": contract.get("worker"),
            "read_only": contract.get("read_only"),
            "risk": contract.get("risk"),
            "hard_unknowns": contract.get("hard_unknowns"),
            "estimate_tokens": contract.get("estimate_tokens"),
            "owned_files": merged.get("owned_files", []),
            "read_files": merged.get("read_files", []),
            "requires_locked_claims": contract.get("requires_locked_claims", []),
            "acceptance_commands": merged.get("acceptance_commands", []),
            "forbidden_changes": merged.get("forbidden_changes", []),
        },
        "obligations": linked,
        "claims": claims,
        "run_contract_hint": {
            "target": ticket_id,
            "scope": ticket.get("objective"),
            "worker": contract.get("worker"),
            "owned_files": merged.get("owned_files", []),
            "budget": contract.get("estimate_tokens"),
            "evidence_delta": [],
        },
    }


def cmd_render_dispatch(store: Store, args: argparse.Namespace) -> None:
    payload = dispatch_payload(store, args.ticket_id)
    path = (
        Path(args.out) if args.out else store.generated_dir / f"{args.ticket_id}.json"
    )
    if not path.is_absolute():
        path = store.root / path
    atomic_write_json(path, payload)
    print(path)


def contract_fingerprint(store: Store, contract: dict[str, Any]) -> str:
    merged = merged_contract(store, contract)
    payload = {
        "ticket_id": contract.get("ticket_id"),
        "obligation_ids": stable_unique(contract.get("obligation_ids", [])),
        "completes_obligations": stable_unique(
            contract.get("completes_obligations", [])
        ),
        "worker": contract.get("worker"),
        "read_only": bool(contract.get("read_only")),
        "owned_files": stable_unique(merged.get("owned_files", [])),
        "acceptance_commands": stable_unique(merged.get("acceptance_commands", [])),
        "forbidden_changes": stable_unique(merged.get("forbidden_changes", [])),
        "requires_locked_claims": stable_unique(
            contract.get("requires_locked_claims", [])
        ),
    }
    return sha256_text(json.dumps(payload, ensure_ascii=False, sort_keys=True))


def verification_source_paths(store: Store, contract: dict[str, Any]) -> list[str]:
    merged = merged_contract(store, contract)
    obligation_index = by_id(store.obligations(), "obligation")
    claim_index = by_id(store.claims(), "claim")
    claim_ids = stable_unique(
        claim_id
        for obligation_id in contract.get("obligation_ids", [])
        for claim_id in obligation_index.get(obligation_id, {}).get("claim_ids", [])
    )
    paths = stable_unique(merged.get("owned_files", []))
    for claim_id in claim_ids:
        lean_file = claim_index.get(claim_id, {}).get("statement", {}).get("lean_file")
        if isinstance(lean_file, str) and lean_file:
            paths.append(lean_file)
    return stable_unique(paths)


def snapshot_source_hashes(store: Store, contract: dict[str, Any]) -> dict[str, str]:
    hashes: dict[str, str] = {}
    for value in verification_source_paths(store, contract):
        path = safe_repo_path(store.root, value)
        if not path.exists() or not path.is_file():
            raise ArchitectureError(f"verification source file missing: {value}")
        hashes[value] = sha256_file(path)
    return hashes


def run_commands(
    root: Path, commands: list[str], *, timeout_seconds: int
) -> list[dict[str, Any]]:
    results: list[dict[str, Any]] = []
    for command in commands:
        started = time.monotonic()
        try:
            result = subprocess.run(
                command,
                cwd=root,
                shell=True,
                capture_output=True,
                text=True,
                timeout=timeout_seconds,
                check=False,
            )
            timed_out = False
            returncode = result.returncode
            stdout = result.stdout or ""
            stderr = result.stderr or ""
        except subprocess.TimeoutExpired as exc:
            timed_out = True
            returncode = None
            stdout = exc.stdout if isinstance(exc.stdout, str) else ""
            stderr = exc.stderr if isinstance(exc.stderr, str) else ""
        duration = round(time.monotonic() - started, 6)
        entry: dict[str, Any] = {
            "command": command,
            "exit_code": returncode,
            "timed_out": timed_out,
            "duration_seconds": duration,
            "stdout_sha256": sha256_text(stdout),
            "stderr_sha256": sha256_text(stderr),
            "stdout_tail": stdout[-2000:],
            "stderr_tail": stderr[-2000:],
        }
        results.append(entry)
        if timed_out or returncode != 0:
            break
    return results


def evidence_pointer_valid(
    store: Store, pointer: dict[str, Any] | None
) -> tuple[bool, str | None]:
    if not pointer:
        return False, "missing evidence pointer"
    value = pointer.get("path")
    expected = pointer.get("sha256")
    if (
        not isinstance(value, str)
        or not value
        or not isinstance(expected, str)
        or not expected
    ):
        return False, "incomplete evidence pointer"
    try:
        path = safe_repo_path(store.root, value)
    except ArchitectureError as exc:
        return False, str(exc)
    if not path.exists() or not path.is_file():
        return False, f"evidence file missing: {value}"
    if sha256_file(path) != expected:
        return False, f"evidence fingerprint mismatch: {value}"
    return True, None


def ticket_verification_valid(
    store: Store, contract: dict[str, Any]
) -> tuple[bool, str | None, dict[str, Any] | None]:
    pointer = contract.get("verification_evidence")
    valid, reason = evidence_pointer_valid(store, pointer)
    if not valid:
        return False, reason, None
    assert isinstance(pointer, dict)
    record = read_json(safe_repo_path(store.root, pointer["path"]))
    if not isinstance(record, dict) or record.get("schema") != "ticket-verification/v2":
        return False, "invalid ticket verification evidence schema", None
    if record.get("status") != "passed":
        return False, "ticket verification evidence did not pass", record
    if record.get("contract_fingerprint") != contract_fingerprint(store, contract):
        return False, "ticket contract changed after verification", record
    try:
        current_hashes = snapshot_source_hashes(store, contract)
    except ArchitectureError as exc:
        return False, str(exc), record
    if record.get("source_hashes") != current_hashes:
        return False, "Lean/source files changed after ticket verification", record
    return True, None, record


def execute_ticket_verification(
    store: Store, ticket_id: str, *, timeout_seconds: int
) -> dict[str, Any]:
    ticket = by_id(store.tickets(), "ticket").get(ticket_id)
    if not ticket or ticket.get("status") != "closed":
        raise ArchitectureError(
            "machine verification requires a closed base-workflow ticket"
        )
    contract = next(
        (item for item in store.contracts() if item.get("ticket_id") == ticket_id), None
    )
    if not contract or contract.get("status") != "approved":
        raise ArchitectureError(
            "machine verification requires an approved ticket contract"
        )
    internal = set(contract.get("obligation_ids", []))
    active = active_obligation_ids(store)
    coverage = dependency_coverage_audit(store, scope_targets(store))
    if not coverage["complete"]:
        raise ArchitectureError(
            "dependency coverage audit is incomplete; refuse proof acceptance"
        )
    outside = sorted(internal - active)
    if outside:
        raise ArchitectureError(
            "ticket contains obligations outside the active verification stage: "
            + ", ".join(outside)
        )
    obligation_index = by_id(store.obligations(), "obligation")
    for obligation_id in internal:
        obligation = obligation_index[obligation_id]
        for dep in obligation.get("depends_on", []):
            if (
                dep not in internal
                and obligation_index[dep].get("status") != "satisfied"
            ):
                raise ArchitectureError(
                    f"external obligation dependency not satisfied: {dep}"
                )
    merged = merged_contract(store, contract)
    commands = stable_unique(merged.get("acceptance_commands", []))
    if contract.get("worker") != "research" and not commands:
        raise ArchitectureError("ticket contract has no executable acceptance command")
    source_hashes_before = snapshot_source_hashes(store, contract)
    results = run_commands(store.root, commands, timeout_seconds=timeout_seconds)
    passed = all(
        not item["timed_out"] and item["exit_code"] == 0 for item in results
    ) and len(results) == len(commands)
    source_hashes_after = snapshot_source_hashes(store, contract)
    record: dict[str, Any] = {
        "schema": "ticket-verification/v2",
        "ticket_id": ticket_id,
        "at": now_iso(),
        "status": "passed" if passed else "failed",
        "contract_fingerprint": contract_fingerprint(store, contract),
        "commands": results,
        "source_hashes_before": source_hashes_before,
        "source_hashes": source_hashes_after,
        "environment": {
            "git_commit": best_effort_command(store.root, ["git", "rev-parse", "HEAD"]),
            "lean_version": best_effort_command(store.root, ["lean", "--version"]),
            "lake_version": best_effort_command(store.root, ["lake", "--version"]),
            "python_version": sys.version.split()[0],
        },
    }
    stamp = record["at"].replace(":", "").replace("+00:00", "Z")
    path = store.evidence_dir / f"{stamp}-{ticket_id}-verification.json"
    atomic_write_json(path, record)
    pointer: dict[str, Any] = {
        "path": str(path.relative_to(store.root)),
        "sha256": sha256_file(path),
        "verified_at": record["at"],
        "status": record["status"],
    }
    manifest = store.contracts_manifest()
    target = next(
        item for item in manifest["items"] if item.get("ticket_id") == ticket_id
    )
    target["verification_evidence"] = pointer
    target["updated_at"] = now_iso()
    atomic_write_json(store.contracts_path, manifest)
    if not passed:
        failed = next(
            (item for item in results if item["timed_out"] or item["exit_code"] != 0),
            None,
        )
        detail = failed["command"] if failed else "unknown command"
        raise ArchitectureError(f"machine acceptance verification failed: {detail}")
    return pointer


def cmd_verify_ticket(store: Store, args: argparse.Namespace) -> None:
    pointer = execute_ticket_verification(
        store, args.ticket_id, timeout_seconds=args.timeout_seconds
    )
    print(json.dumps(pointer, ensure_ascii=False, indent=2))


def cmd_satisfy_obligation(store: Store, args: argparse.Namespace) -> None:
    if not isinstance(args.ticket, str):
        raise ArchitectureError("satisfying ticket ID must be a string")
    ticket_id = args.ticket
    manifest = store.obligations_manifest()
    obligation_index = by_id(manifest["items"], "obligation")
    obligation = obligation_index.get(args.id)
    if not obligation:
        raise ArchitectureError(f"unknown obligation: {args.id}")
    for dep in obligation.get("depends_on", []):
        if obligation_index[dep].get("status") != "satisfied":
            raise ArchitectureError(f"obligation dependency not satisfied: {dep}")
    ticket = by_id(store.tickets(), "ticket").get(ticket_id)
    if not ticket or ticket.get("status") != "closed":
        raise ArchitectureError("satisfying ticket must exist and be closed")
    contracts_manifest = store.contracts_manifest()
    contract = next(
        (
            item
            for item in contracts_manifest["items"]
            if item.get("ticket_id") == ticket_id
        ),
        None,
    )
    if not contract or contract.get("status") != "approved":
        raise ArchitectureError(
            "satisfying ticket must have an approved architecture contract"
        )
    if args.id not in contract.get("completes_obligations", []):
        raise ArchitectureError(
            f"ticket {ticket_id} is not contracted to complete obligation {args.id}"
        )
    if contract.get("worker") == "research":
        raise ArchitectureError("research contracts may not satisfy formal obligations")
    if args.verification is not None and args.verification != "passed":
        raise ArchitectureError(
            "manual failed verification cannot satisfy an obligation"
        )
    if args.command:
        approved = stable_unique(
            merged_contract(store, contract).get("acceptance_commands", [])
        )
        if stable_unique(args.command) != approved:
            raise ArchitectureError(
                "manual --command evidence may not differ from approved acceptance_commands"
            )
    valid, _, _ = ticket_verification_valid(store, contract)
    if not valid:
        execute_ticket_verification(
            store, ticket_id, timeout_seconds=args.timeout_seconds
        )
        contracts_manifest = store.contracts_manifest()
        contract = next(
            item
            for item in contracts_manifest["items"]
            if item.get("ticket_id") == ticket_id
        )
    valid, reason, verification_record = ticket_verification_valid(store, contract)
    if not valid or verification_record is None:
        raise ArchitectureError(f"ticket lacks valid machine verification: {reason}")
    notes = stable_unique(args.evidence)
    record: dict[str, Any] = {
        "schema": "obligation-evidence/v2",
        "obligation_id": args.id,
        "ticket_id": ticket_id,
        "at": now_iso(),
        "verification": "passed",
        "machine_ticket_evidence": contract["verification_evidence"],
        "notes": notes,
        "source_hashes": verification_record.get("source_hashes", {}),
    }
    stamp = record["at"].replace(":", "").replace("+00:00", "Z")
    path = store.evidence_dir / f"{stamp}-{args.id}.json"
    atomic_write_json(path, record)
    obligation["status"] = "satisfied"
    obligation["blocker"] = None
    obligation["evidence"] = {
        "path": str(path.relative_to(store.root)),
        "ticket_id": ticket_id,
        "verified_at": record["at"],
        "sha256": sha256_file(path),
        "machine_verified": True,
    }
    obligation["updated_at"] = now_iso()
    atomic_write_json(store.obligations_path, manifest)
    print(args.id)


def contract_owned_files(store: Store, contract: dict[str, Any]) -> set[str]:
    if contract.get("read_only"):
        return set()
    return set(merged_contract(store, contract).get("owned_files", []))


def current_parallel_candidates(store: Store) -> list[dict[str, Any]]:
    ticket_index = by_id(store.tickets(), "ticket")
    out: list[dict[str, Any]] = []
    for contract in store.contracts():
        ticket_id = contract.get("ticket_id")
        if not isinstance(ticket_id, str):
            continue
        ticket = ticket_index.get(ticket_id)
        if not ticket or ticket.get("status") not in {"ready", "partial"}:
            continue
        if ticket_check_reasons(store, ticket_id):
            continue
        out.append(contract)
    return sorted(out, key=lambda item: item["ticket_id"])


def cmd_parallel_frontier(store: Store, _args: argparse.Namespace) -> None:
    candidates = current_parallel_candidates(store)
    lanes: list[list[dict[str, Any]]] = []
    for contract in candidates:
        owned = contract_owned_files(store, contract)
        placed = False
        for lane in lanes:
            lane_owned = set().union(
                *(contract_owned_files(store, item) for item in lane)
            )
            if not (owned & lane_owned):
                lane.append(contract)
                placed = True
                break
        if not placed:
            lanes.append([contract])
    conflict_pairs: list[list[str]] = []
    for i, left in enumerate(candidates):
        left_files = contract_owned_files(store, left)
        for right in candidates[i + 1 :]:
            if left_files & contract_owned_files(store, right):
                conflict_pairs.append([left["ticket_id"], right["ticket_id"]])
    payload = {
        "candidates": [item["ticket_id"] for item in candidates],
        "parallel_batches": [[item["ticket_id"] for item in lane] for lane in lanes],
        "file_conflicts": conflict_pairs,
        "note": "Batches are advisory. Use separate worktrees/processes; one writer per owned file remains authoritative.",
    }
    print(json.dumps(payload, ensure_ascii=False, indent=2))


def cmd_add_comparator(store: Store, args: argparse.Namespace) -> None:
    manifest = store.comparators_manifest()
    items = manifest["items"]
    if args.id in by_id(items, "comparator"):
        raise ArchitectureError(f"comparator already exists: {args.id}")
    claim_index = by_id(store.claims(), "claim")
    if args.target_claim not in claim_index:
        raise ArchitectureError(f"unknown target claim: {args.target_claim}")
    items.append(
        {
            "id": args.id,
            "target_claim": args.target_claim,
            "reference_source": args.reference_source,
            "reference_declaration": args.reference_declaration,
            "solution_declaration": args.solution_declaration,
            "check_commands": stable_unique(args.check_command),
            "permitted_axioms": stable_unique(args.permitted_axiom),
            "required": args.required,
            "status": "draft" if args.draft else "ready",
            "evidence": None,
            "created_at": now_iso(),
            "updated_at": now_iso(),
        }
    )
    atomic_write_json(store.comparators_path, manifest)
    errors, _ = validate_state(store)
    if errors:
        items.pop()
        atomic_write_json(store.comparators_path, manifest)
        raise ArchitectureError("comparator rejected:\n- " + "\n- ".join(errors))
    print(args.id)


def cmd_verify_comparator(store: Store, args: argparse.Namespace) -> None:
    manifest = store.comparators_manifest()
    comparator = by_id(manifest["items"], "comparator").get(args.id)
    if not comparator:
        raise ArchitectureError(f"unknown comparator: {args.id}")
    claim = by_id(store.claims(), "claim").get(comparator["target_claim"])
    if not claim or claim.get("status") != "verified":
        raise ArchitectureError("comparator target claim must be verified first")
    if args.verification is not None and args.verification != "passed":
        raise ArchitectureError("manual failed verification cannot verify a comparator")
    commands = stable_unique(comparator.get("check_commands", []))
    if not commands:
        raise ArchitectureError("comparator has no executable check_commands")
    if args.command and stable_unique(args.command) != commands:
        raise ArchitectureError(
            "manual comparator commands must equal registered check_commands"
        )
    results = run_commands(store.root, commands, timeout_seconds=args.timeout_seconds)
    passed = len(results) == len(commands) and all(
        not item["timed_out"] and item["exit_code"] == 0 for item in results
    )
    record: dict[str, Any] = {
        "schema": "comparator-evidence/v2",
        "comparator_id": args.id,
        "at": now_iso(),
        "status": "passed" if passed else "failed",
        "commands": results,
        "environment": {
            "git_commit": best_effort_command(store.root, ["git", "rev-parse", "HEAD"]),
            "lean_version": best_effort_command(store.root, ["lean", "--version"]),
            "lake_version": best_effort_command(store.root, ["lake", "--version"]),
        },
        "notes": stable_unique(args.evidence),
    }
    stamp = record["at"].replace(":", "").replace("+00:00", "Z")
    path = store.evidence_dir / f"{stamp}-{args.id}-comparator.json"
    atomic_write_json(path, record)
    comparator["status"] = "verified" if passed else "failed"
    comparator["evidence"] = {
        "path": str(path.relative_to(store.root)),
        "sha256": sha256_file(path),
        "verified_at": record["at"],
        "machine_verified": True,
    }
    comparator["updated_at"] = now_iso()
    atomic_write_json(store.comparators_path, manifest)
    if not passed:
        raise ArchitectureError("comparator machine verification failed")
    print(args.id)


def source_integrity(store: Store) -> dict[str, Any]:
    project = store.project()
    source = project.get("source", {})
    if not isinstance(source, dict):
        return {
            "ok": False,
            "error": "project.source must be an object",
            "stored_sha256": None,
        }
    stored_sha = source.get("sha256")
    source_path = source.get("path")
    if not isinstance(stored_sha, str) or not stored_sha:
        return {
            "ok": False,
            "error": "paper source fingerprint is missing",
            "stored_sha256": None,
        }
    if not isinstance(source_path, str) or not source_path:
        return {
            "ok": False,
            "error": "paper source path is missing",
            "stored_sha256": stored_sha,
        }
    path = Path(source_path)
    if not path.is_absolute():
        path = store.root / path
    if not path.exists() or not path.is_file():
        return {
            "ok": False,
            "error": f"paper source file missing: {source_path}",
            "stored_sha256": stored_sha,
            "actual_sha256": None,
        }
    actual_sha = sha256_file(path)
    if actual_sha != stored_sha:
        return {
            "ok": False,
            "error": "paper source fingerprint mismatch",
            "stored_sha256": stored_sha,
            "actual_sha256": actual_sha,
        }
    return {
        "ok": True,
        "error": None,
        "path": source_path,
        "stored_sha256": stored_sha,
        "actual_sha256": actual_sha,
    }


def cmd_record_dependency_scan(store: Store, args: argparse.Namespace) -> None:
    claim_index = by_id(store.claims(), "claim")
    claim = claim_index.get(args.claim)
    if not claim:
        raise ArchitectureError(f"unknown paper claim: {args.claim}")
    integrity = source_integrity(store)
    if not integrity["ok"]:
        raise ArchitectureError(str(integrity["error"]))
    source_sha = cast(str, integrity["stored_sha256"])
    internal = stable_unique(args.internal_claim)
    assumptions = stable_unique(args.assumption)
    expected_internal = stable_unique(claim.get("depends_on", []))
    expected_assumptions = stable_unique(claim.get("uses_assumptions", []))
    if set(internal) != set(expected_internal):
        raise ArchitectureError(
            "dependency scan internal claims do not match Claim DAG; update the Claim DAG first"
        )
    if set(assumptions) != set(expected_assumptions):
        raise ArchitectureError(
            "dependency scan assumptions do not match claim uses_assumptions; update the claim first"
        )
    if not args.source_ref:
        raise ArchitectureError("dependency scan requires at least one --source-ref")
    manifest = store.coverage_manifest()
    items = manifest["items"]
    existing = next(
        (item for item in items if item.get("claim_id") == args.claim), None
    )
    record: dict[str, Any] = {
        "id": f"DC-{args.claim}",
        "claim_id": args.claim,
        "source_refs": stable_unique(args.source_ref),
        "source_sha256": source_sha,
        "internal_claims": internal,
        "assumptions": assumptions,
        "complete": bool(args.complete),
        "review_note": args.note,
        "updated_at": now_iso(),
    }
    if existing:
        created = existing.get("created_at", now_iso())
        existing.clear()
        existing.update(record)
        existing["created_at"] = created
    else:
        record["created_at"] = now_iso()
        items.append(record)
    atomic_write_json(store.coverage_path, manifest)
    print(args.claim)


def dependency_coverage_audit(store: Store, targets: Iterable[str]) -> dict[str, Any]:
    claim_index = by_id(store.claims(), "claim")
    closure = transitive_closure(claim_index, stable_unique(targets), "depends_on")
    records = {item.get("claim_id"): item for item in store.coverage()}
    integrity = source_integrity(store)
    current_sha = integrity.get("stored_sha256")
    missing: list[str] = []
    stale: list[str] = []
    inconsistent: list[str] = []
    for claim_id in sorted(closure):
        record = records.get(claim_id)
        if not record or record.get("complete") is not True:
            missing.append(claim_id)
            continue
        if not current_sha or record.get("source_sha256") != current_sha:
            stale.append(claim_id)
        claim = claim_index[claim_id]
        if set(record.get("internal_claims", [])) != set(claim.get("depends_on", [])):
            inconsistent.append(f"{claim_id}: internal claim dependency mismatch")
        if set(record.get("assumptions", [])) != set(claim.get("uses_assumptions", [])):
            inconsistent.append(f"{claim_id}: assumption dependency mismatch")
        if not record.get("source_refs"):
            inconsistent.append(f"{claim_id}: no source references recorded")
    return {
        "complete": bool(closure)
        and bool(integrity["ok"])
        and not missing
        and not stale
        and not inconsistent,
        "claim_closure_size": len(closure),
        "missing_scans": missing,
        "stale_scans": stale,
        "inconsistent_scans": inconsistent,
        "source_sha256": current_sha,
        "source_integrity": integrity,
    }


def trust_level_for_targets(store: Store, targets: Iterable[str]) -> dict[str, Any]:
    claim_index = by_id(store.claims(), "claim")
    closure = transitive_closure(claim_index, stable_unique(targets), "depends_on")
    assumption_index = by_id(store.assumptions(), "assumption")
    used = sorted(
        {
            assumption_id
            for claim_id in closure
            for assumption_id in claim_index[claim_id].get("uses_assumptions", [])
        }
    )
    categories = {
        assumption_id: assumption_index.get(assumption_id, {}).get("category")
        for assumption_id in used
    }
    if any(category == "trusted_external" for category in categories.values()):
        level = "CONDITIONAL_TRUSTED_EXTERNAL"
    elif any(category == "formal_import" for category in categories.values()):
        level = "FORMALLY_IMPORTED"
    else:
        level = "KERNEL_CLOSED"
    return {"level": level, "assumptions": used, "categories": categories}


def validate_state(store: Store) -> tuple[list[str], list[str]]:
    errors: list[str] = []
    warnings: list[str] = []
    try:
        project = store.project()
        claims = store.claims()
        tickets = store.tickets()
        assumptions = store.assumptions()
        scope = store.verification_scope()
        obligations_manifest = store.obligations_manifest()
        contracts_manifest = store.contracts_manifest()
        comparators_manifest = store.comparators_manifest()
        coverage_manifest = store.coverage_manifest()
    except ArchitectureError as exc:
        return [str(exc)], []
    try:
        claim_index = by_id(claims, "claim")
        ticket_index = by_id(tickets, "ticket")
        assumption_index = by_id(assumptions, "assumption")
        obligation_index = by_id(obligations_manifest["items"], "obligation")
        contract_index = by_id(contracts_manifest["items"], "ticket contract")
        comparator_index = by_id(comparators_manifest["items"], "comparator")
        coverage_index = by_id(coverage_manifest["items"], "dependency coverage record")
    except ArchitectureError as exc:
        return [str(exc)], []
    _ = contract_index, comparator_index, assumption_index, coverage_index

    if scope.get("strategy") not in VERIFICATION_STRATEGIES:
        errors.append("verification_scope: invalid strategy")
    if scope.get("stage") not in VERIFICATION_STAGES:
        errors.append("verification_scope: invalid stage")
    if scope.get("full_paper_policy") not in FULL_PAPER_POLICIES:
        errors.append("verification_scope: invalid full_paper_policy")
    primary_targets = scope.get("primary_targets", [])
    full_targets = scope.get("full_targets", [])
    if not isinstance(primary_targets, list) or not all(
        isinstance(x, str) for x in primary_targets
    ):
        errors.append("verification_scope: primary_targets must be a list of strings")
        primary_targets = []
    if not isinstance(full_targets, list) or not all(
        isinstance(x, str) for x in full_targets
    ):
        errors.append("verification_scope: full_targets must be a list of strings")
        full_targets = []
    for claim_id in [*primary_targets, *full_targets]:
        if claim_id not in claim_index:
            errors.append(f"verification_scope: unknown target claim {claim_id}")
    expected_targets = (
        full_targets if scope.get("stage") == "full-paper" else primary_targets
    )
    if stable_unique(project.get("targets", [])) != stable_unique(expected_targets):
        errors.append(
            "verification_scope: project.targets drift from the active verification stage"
        )
    gate = scope.get("main_theorem_gate", {})
    if gate.get("status") not in GATE_STATUSES:
        errors.append("verification_scope: invalid main_theorem_gate status")
    if scope.get("stage") == "full-paper":
        permitted_gate = gate.get("status") == "passed" or (
            scope.get("strategy") == "full-paper"
            and gate.get("status") == "explicit-full-paper-bypass"
        )
        if not permitted_gate:
            errors.append(
                "verification_scope: full-paper stage requires a passed gate or explicit full-paper bypass"
            )
    if (
        scope.get("stage") == "full-paper"
        and scope.get("full_paper_policy") != "after-main"
    ):
        errors.append(
            "verification_scope: full-paper stage requires full_paper_policy=after-main"
        )

    for obligation_id, item in obligation_index.items():
        if not obligation_id.startswith("O-"):
            errors.append(f"{obligation_id}: obligation ID must start with O-")
        if item.get("kind") not in OBLIGATION_KINDS:
            errors.append(f"{obligation_id}: invalid kind")
        if item.get("layer") not in OBLIGATION_LAYERS:
            errors.append(f"{obligation_id}: invalid layer")
        if item.get("status") not in OBLIGATION_STATUSES:
            errors.append(f"{obligation_id}: invalid status")
        if item.get("risk") not in RISKS:
            errors.append(f"{obligation_id}: invalid risk")
        hard_unknowns = item.get("hard_unknowns")
        if not isinstance(hard_unknowns, int) or hard_unknowns < 0:
            errors.append(
                f"{obligation_id}: hard_unknowns must be a nonnegative integer"
            )
        elif hard_unknowns > 2:
            warnings.append(
                f"{obligation_id}: {hard_unknowns} independent hard unknowns; split before ticketing if possible"
            )
        if obligation_id in item.get("depends_on", []):
            errors.append(f"{obligation_id}: self dependency")
        for dep in item.get("depends_on", []):
            if dep not in obligation_index:
                errors.append(f"{obligation_id}: unknown obligation dependency {dep}")
        for claim_id in item.get("claim_ids", []):
            if claim_id not in claim_index:
                errors.append(f"{obligation_id}: unknown paper claim {claim_id}")
        if item.get("status") == "satisfied":
            for dep in item.get("depends_on", []):
                dep_item = obligation_index.get(dep)
                if dep_item is not None and dep_item.get("status") != "satisfied":
                    errors.append(
                        f"{obligation_id}: satisfied obligation depends on unsatisfied {dep}"
                    )
            evidence = item.get("evidence") or {}
            valid, reason = evidence_pointer_valid(store, evidence)
            if not valid:
                errors.append(f"{obligation_id}: invalid obligation evidence: {reason}")
            elif evidence.get("machine_verified") is not True:
                errors.append(
                    f"{obligation_id}: obligation evidence is not machine verified"
                )
            else:
                try:
                    record = read_json(safe_repo_path(store.root, evidence["path"]))
                except ArchitectureError as exc:
                    errors.append(f"{obligation_id}: {exc}")
                else:
                    if (
                        not isinstance(record, dict)
                        or record.get("schema") != "obligation-evidence/v2"
                    ):
                        errors.append(
                            f"{obligation_id}: invalid obligation evidence schema"
                        )
                    if record.get("verification") != "passed":
                        errors.append(
                            f"{obligation_id}: obligation evidence is not passed"
                        )

    cycle = find_cycle(obligation_index, "depends_on")
    if cycle:
        errors.append("obligation dependency cycle: " + " -> ".join(cycle))

    seen_ticket_contracts: set[str] = set()
    for contract in contracts_manifest["items"]:
        contract_id = contract.get("id", "<contract>")
        ticket_id = contract.get("ticket_id")
        if ticket_id in seen_ticket_contracts:
            errors.append(f"duplicate ticket contract for {ticket_id}")
        if isinstance(ticket_id, str):
            seen_ticket_contracts.add(ticket_id)
        if ticket_id not in ticket_index:
            errors.append(f"{contract_id}: unknown ticket {ticket_id}")
        if contract.get("status") not in CONTRACT_STATUSES:
            errors.append(f"{contract_id}: invalid contract status")
        if contract.get("worker") not in WORKERS:
            errors.append(f"{contract_id}: invalid worker")
        if contract.get("risk") not in RISKS:
            errors.append(f"{contract_id}: invalid risk")
        obligation_ids = contract.get("obligation_ids", [])
        for obligation_id in obligation_ids:
            if obligation_id not in obligation_index:
                errors.append(f"{contract_id}: unknown obligation {obligation_id}")
        for obligation_id in contract.get("completes_obligations", []):
            if obligation_id not in obligation_ids:
                errors.append(
                    f"{contract_id}: completes obligation not included in obligation_ids: {obligation_id}"
                )
        if contract.get("worker") == "research" and contract.get(
            "completes_obligations"
        ):
            errors.append(
                f"{contract_id}: research contracts may not complete formal obligations"
            )
        for claim_id in contract.get("requires_locked_claims", []):
            if claim_id not in claim_index:
                errors.append(
                    f"{contract_id}: unknown locked-claim requirement {claim_id}"
                )
        hard_unknowns = contract.get("hard_unknowns")
        if not isinstance(hard_unknowns, int) or hard_unknowns < 0:
            errors.append(f"{contract_id}: hard_unknowns must be a nonnegative integer")
        elif hard_unknowns > 2:
            warnings.append(
                f"{contract_id}: contract contains {hard_unknowns} hard unknowns; one fresh context may be too broad"
            )
        if contract.get("status") == "approved":
            merged = (
                merged_contract(store, contract)
                if all(item in obligation_index for item in obligation_ids)
                else contract
            )
            if not contract.get("read_only") and not merged.get("owned_files"):
                errors.append(
                    f"{contract_id}: approved mutating contract needs owned_files"
                )
            if contract.get("worker") != "research" and not merged.get(
                "acceptance_commands"
            ):
                errors.append(
                    f"{contract_id}: approved contract needs acceptance_commands"
                )
            for path_value in stable_unique(merged.get("owned_files", [])):
                try:
                    safe_repo_path(store.root, path_value)
                except ArchitectureError as exc:
                    errors.append(f"{contract_id}: {exc}")
        if contract.get("verification_evidence"):
            valid, reason, _record = ticket_verification_valid(store, contract)
            if not valid:
                errors.append(
                    f"{contract_id}: invalid ticket verification evidence: {reason}"
                )

    for comparator_id, item in by_id(
        comparators_manifest["items"], "comparator"
    ).items():
        if item.get("target_claim") not in claim_index:
            errors.append(f"{comparator_id}: unknown target claim")
        if item.get("status") not in COMPARATOR_STATUSES:
            errors.append(f"{comparator_id}: invalid status")
        if item.get("required") and not item.get("check_commands"):
            errors.append(f"{comparator_id}: required comparator needs check_commands")
        if item.get("status") == "verified":
            valid, reason = evidence_pointer_valid(store, item.get("evidence"))
            if not valid:
                errors.append(f"{comparator_id}: invalid comparator evidence: {reason}")
            elif item.get("evidence", {}).get("machine_verified") is not True:
                errors.append(
                    f"{comparator_id}: comparator evidence is not machine verified"
                )

    seen_coverage_claims: set[str] = set()
    for record in coverage_manifest["items"]:
        claim_id = record.get("claim_id")
        record_id = record.get("id", "<coverage>")
        if claim_id in seen_coverage_claims:
            errors.append(f"duplicate dependency coverage record for {claim_id}")
        if isinstance(claim_id, str):
            seen_coverage_claims.add(claim_id)
        if claim_id not in claim_index:
            errors.append(f"{record_id}: unknown claim {claim_id}")
            continue
        if record.get("complete") not in {True, False}:
            errors.append(f"{record_id}: complete must be boolean")
        if not isinstance(record.get("source_refs", []), list):
            errors.append(f"{record_id}: source_refs must be a list")
        for dep in record.get("internal_claims", []):
            if dep not in claim_index:
                errors.append(f"{record_id}: unknown internal claim {dep}")
        for assumption_id in record.get("assumptions", []):
            if assumption_id not in assumption_index:
                errors.append(f"{record_id}: unknown assumption {assumption_id}")

    return stable_unique(errors), stable_unique(warnings)


def cmd_validate(store: Store, _args: argparse.Namespace) -> None:
    errors, warnings = validate_state(store)
    for warning in warnings:
        print(f"warning: {warning}", file=sys.stderr)
    if errors:
        raise ArchitectureError("validation failed:\n- " + "\n- ".join(errors))
    print("OK")


def architecture_audit(
    store: Store, targets_override: Iterable[str] | None = None
) -> dict[str, Any]:
    errors, warnings = validate_state(store)
    project = store.project()
    claim_index = by_id(store.claims(), "claim")
    targets = stable_unique(
        targets_override if targets_override is not None else project.get("targets", [])
    )
    claim_closure = (
        transitive_closure(claim_index, targets, "depends_on") if targets else set()
    )
    obligations = store.obligations()
    obligation_index = by_id(obligations, "obligation")
    directly_related_ids = {
        item["id"]
        for item in obligations
        if set(item.get("claim_ids", [])) & claim_closure
    }
    related_ids = (
        transitive_closure(obligation_index, directly_related_ids, "depends_on")
        if directly_related_ids
        else set()
    )
    related = [obligation_index[item_id] for item_id in sorted(related_ids)]
    covered_claims = {
        claim_id
        for item in obligations
        for claim_id in item.get("claim_ids", [])
        if claim_id in claim_closure
    }
    uncovered_claims = sorted(claim_closure - covered_claims)
    incomplete = sorted(
        item["id"] for item in related if item.get("status") != "satisfied"
    )
    ticket_index = by_id(store.tickets(), "ticket")
    open_contract_tickets = sorted(
        contract["ticket_id"]
        for contract in store.contracts()
        if set(contract.get("obligation_ids", [])) & related_ids
        and ticket_index.get(contract["ticket_id"], {}).get("status")
        not in {"closed", "cancelled"}
    )
    required_comparators = [
        item
        for item in store.comparators()
        if item.get("required") and item.get("target_claim") in claim_closure
    ]
    unverified_comparators = sorted(
        item["id"] for item in required_comparators if item.get("status") != "verified"
    )
    coverage = dependency_coverage_audit(store, targets)
    complete = (
        bool(targets)
        and not errors
        and coverage["complete"]
        and not uncovered_claims
        and not incomplete
        and not open_contract_tickets
        and not unverified_comparators
    )
    return {
        "complete": complete,
        "targets": targets,
        "claim_closure_size": len(claim_closure),
        "related_obligations": sorted(item["id"] for item in related),
        "uncovered_claims": uncovered_claims,
        "incomplete_obligations": incomplete,
        "open_contract_tickets": open_contract_tickets,
        "required_comparators": sorted(item["id"] for item in required_comparators),
        "unverified_comparators": unverified_comparators,
        "dependency_coverage": coverage,
        "validation_errors": errors,
        "warnings": warnings,
    }


def base_target_audit(store: Store, targets: Iterable[str]) -> dict[str, Any]:
    roots = stable_unique(targets)
    claim_index = by_id(store.claims(), "claim")
    closure = transitive_closure(claim_index, roots, "depends_on") if roots else set()
    unverified: list[str] = []
    invalid_verified_evidence: list[str] = []
    for claim_id in sorted(closure):
        claim = claim_index[claim_id]
        if claim.get("status") != "verified":
            unverified.append(claim_id)
            continue
        statement = claim.get("statement", {})
        proof = claim.get("proof", {})
        if (
            not statement.get("locked")
            or not statement.get("sha256")
            or proof.get("build") != "passed"
            or proof.get("sorry_count") != 0
            or proof.get("axiom_audit") != "passed"
            or proof.get("trusted") is not True
        ):
            invalid_verified_evidence.append(claim_id)

    assumptions = by_id(store.assumptions(), "assumption")
    used_assumptions = {
        assumption_id
        for claim_id in closure
        for assumption_id in claim_index[claim_id].get("uses_assumptions", [])
    }
    unapproved_assumptions = sorted(
        assumption_id
        for assumption_id in used_assumptions
        if assumption_id not in assumptions
        or not assumptions[assumption_id].get("approved")
    )
    open_tickets = sorted(
        ticket["id"]
        for ticket in store.tickets()
        if ticket.get("status") not in {"closed", "cancelled"}
        and any(
            claim_id in closure
            for claim_id in ticket.get("claim_ids", [])
            + ticket.get("completes_claims", [])
        )
    )
    spec_error = None
    project = store.project()
    spec = project.get("spec", {})
    if spec.get("sha256") and spec.get("path"):
        path = store.root / spec["path"]
        if not path.exists():
            spec_error = f"spec file missing: {spec['path']}"
        else:
            actual = sha256_text(path.read_text(encoding="utf-8"))
            if actual != spec["sha256"]:
                spec_error = "spec fingerprint mismatch"
    complete = (
        bool(roots)
        and not unverified
        and not invalid_verified_evidence
        and not unapproved_assumptions
        and not open_tickets
        and spec_error is None
    )
    trust = trust_level_for_targets(store, roots)
    return {
        "complete": complete,
        "targets": roots,
        "claim_closure_size": len(closure),
        "trust": trust,
        "unverified_claims": unverified,
        "invalid_verified_evidence": invalid_verified_evidence,
        "unapproved_assumptions": unapproved_assumptions,
        "open_related_tickets": open_tickets,
        "spec_error": spec_error,
    }


def verification_gate(store: Store) -> dict[str, Any]:
    scope = store.verification_scope()
    stage = scope.get("stage")
    policy = scope.get("full_paper_policy", "ask")
    targets = scope_targets(store)
    base = base_target_audit(store, targets)
    architecture = architecture_audit(store, targets)
    complete = bool(base["complete"] and architecture["complete"])
    eligible = stage == "main-theorem" and complete and policy == "after-main"
    awaiting_decision = stage == "main-theorem" and complete and policy == "ask"
    terminal_for_selected_scope = complete and (
        stage == "full-paper" or policy == "skip"
    )
    trust_level = base.get("trust", {}).get("level")
    if not complete:
        verification_result = "INCOMPLETE"
    elif trust_level == "CONDITIONAL_TRUSTED_EXTERNAL":
        verification_result = "PASS_CONDITIONAL_TRUSTED_EXTERNAL"
    elif trust_level == "FORMALLY_IMPORTED":
        verification_result = "PASS_FORMALLY_IMPORTED"
    else:
        verification_result = "PASS_KERNEL_CLOSED"
    if not complete:
        next_action = "continue-current-stage"
    elif eligible:
        next_action = "promote-full-paper"
    elif awaiting_decision:
        next_action = "choose-full-paper-policy"
    else:
        next_action = "complete-selected-scope"
    return {
        "strategy": scope.get("strategy"),
        "stage": stage,
        "full_paper_policy": policy,
        "targets": targets,
        "complete": complete,
        "verification_result": verification_result,
        "eligible_for_full_paper": eligible,
        "awaiting_full_paper_decision": awaiting_decision,
        "terminal_for_selected_scope": terminal_for_selected_scope,
        "next_action": next_action,
        "base_audit": base,
        "architecture_audit": architecture,
        "trust_level": trust_level,
        "trust": base.get("trust"),
        "main_theorem_gate": scope.get("main_theorem_gate"),
    }


def recover_pending_transaction(store: Store) -> None:
    if not store.transaction_path.exists():
        return
    journal = read_json(store.transaction_path)
    if not isinstance(journal, dict):
        raise ArchitectureError("invalid architecture transaction journal")
    old_project = journal.get("old_project")
    old_scope = journal.get("old_scope")
    if not isinstance(old_project, dict) or not isinstance(old_scope, dict):
        raise ArchitectureError("transaction journal lacks rollback state")
    atomic_write_json(store.project_path, old_project)
    atomic_write_json(store.scope_path, old_scope)
    store.transaction_path.unlink(missing_ok=True)


def commit_scope_transaction(
    store: Store,
    *,
    new_scope: dict[str, Any],
    new_targets: Iterable[str],
    operation: str,
) -> None:
    old_project = store.project()
    old_scope = store.verification_scope()
    new_project = json.loads(json.dumps(old_project))
    new_project["targets"] = stable_unique(new_targets)
    new_project["updated_at"] = now_iso()
    journal: dict[str, Any] = {
        "schema": "architecture-transaction/v1",
        "operation": operation,
        "started_at": now_iso(),
        "old_project": old_project,
        "old_scope": old_scope,
    }
    atomic_write_json(store.transaction_path, journal)
    try:
        atomic_write_json(store.project_path, new_project)
        atomic_write_json(store.scope_path, new_scope)
        errors, _warnings = validate_state(store)
        if errors:
            raise ArchitectureError(
                f"{operation} produced invalid state:\n- " + "\n- ".join(errors)
            )
    except Exception:
        atomic_write_json(store.project_path, old_project)
        atomic_write_json(store.scope_path, old_scope)
        store.transaction_path.unlink(missing_ok=True)
        raise
    store.transaction_path.unlink(missing_ok=True)


def cmd_configure_verification(store: Store, args: argparse.Namespace) -> None:
    claim_index = by_id(store.claims(), "claim")
    primary = stable_unique(args.primary_target)
    if not primary:
        raise ArchitectureError("configure-verification requires --primary-target")
    for claim_id in primary:
        if claim_id not in claim_index:
            raise ArchitectureError(f"unknown primary target claim: {claim_id}")
    full = stable_unique(args.full_target)
    if args.full_all_claims:
        full = list(claim_index)
    for claim_id in full:
        if claim_id not in claim_index:
            raise ArchitectureError(f"unknown full-paper target claim: {claim_id}")
    scope = store.verification_scope()
    scope = json.loads(json.dumps(scope))
    scope["strategy"] = args.strategy
    scope["full_paper_policy"] = args.full_paper_policy
    scope["primary_targets"] = primary
    scope["full_targets"] = full
    scope["full_targets_policy"] = "all-claims" if args.full_all_claims else "explicit"
    scope["main_theorem_gate"] = {
        "status": "pending",
        "checked_at": None,
        "base_audit": None,
        "architecture_audit": None,
    }
    scope["promoted_at"] = None
    if args.strategy == "full-paper":
        if not full:
            raise ArchitectureError(
                "full-paper strategy requires --full-target or --full-all-claims"
            )
        scope["full_paper_policy"] = "after-main"
        scope["stage"] = "full-paper"
        scope["main_theorem_gate"] = {
            "status": "explicit-full-paper-bypass",
            "checked_at": now_iso(),
            "base_audit": None,
            "architecture_audit": None,
        }
        targets = full
    else:
        scope["stage"] = "main-theorem"
        targets = primary
    scope["updated_at"] = now_iso()
    commit_scope_transaction(
        store, new_scope=scope, new_targets=targets, operation="configure-verification"
    )
    print(json.dumps(scope, ensure_ascii=False, indent=2))


def cmd_set_full_paper_policy(store: Store, args: argparse.Namespace) -> None:
    scope = json.loads(json.dumps(store.verification_scope()))
    if scope.get("stage") == "full-paper" and args.policy != "after-main":
        raise ArchitectureError(
            "cannot disable full-paper policy after promotion; return to planning if scope must shrink"
        )
    scope["full_paper_policy"] = args.policy
    scope["updated_at"] = now_iso()
    commit_scope_transaction(
        store,
        new_scope=scope,
        new_targets=scope_targets_from_value(scope),
        operation="set-full-paper-policy",
    )
    print(json.dumps(scope, ensure_ascii=False, indent=2))


def cmd_verification_gate(store: Store, args: argparse.Namespace) -> None:
    result = verification_gate(store)
    if args.format == "json":
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return
    lines = [
        "# Verification Stage Gate",
        "",
        f"- Strategy: `{result['strategy']}`",
        f"- Stage: `{result['stage']}`",
        f"- Full-paper policy: `{result['full_paper_policy']}`",
        f"- Complete: **{'YES' if result['complete'] else 'NO'}**",
        f"- Verification result: `{result['verification_result']}`",
        f"- Eligible for full-paper promotion: **{'YES' if result['eligible_for_full_paper'] else 'NO'}**",
        f"- Awaiting full-paper decision: **{'YES' if result['awaiting_full_paper_decision'] else 'NO'}**",
        f"- Terminal for selected scope: **{'YES' if result['terminal_for_selected_scope'] else 'NO'}**",
        f"- Next action: `{result['next_action']}`",
        f"- Trust level: `{result['trust_level']}`",
        f"- Targets: {', '.join(result['targets']) if result['targets'] else '(none)'}",
    ]
    print("\n".join(lines))


def cmd_promote_full_paper(store: Store, args: argparse.Namespace) -> None:
    scope = json.loads(json.dumps(store.verification_scope()))
    if scope.get("strategy") != "target-first":
        raise ArchitectureError("promotion applies only to target-first strategy")
    if scope.get("stage") != "main-theorem":
        raise ArchitectureError("project is not in the main-theorem stage")
    policy = scope.get("full_paper_policy", "ask")
    if policy == "skip":
        raise ArchitectureError(
            "full-paper verification is disabled for this project; set full_paper_policy=after-main first"
        )
    if policy == "ask":
        raise ArchitectureError(
            "full-paper policy is undecided; choose after-main or skip before promotion"
        )
    gate = verification_gate(store)
    if not gate["complete"]:
        raise ArchitectureError(
            "main-theorem verification gate is not complete; refusing full-paper promotion"
        )
    claim_index = by_id(store.claims(), "claim")
    full = stable_unique(args.full_target)
    if args.all_claims or not full:
        configured = stable_unique(scope.get("full_targets", []))
        full = configured or list(claim_index)
    for claim_id in full:
        if claim_id not in claim_index:
            raise ArchitectureError(f"unknown full-paper target claim: {claim_id}")
    scope["main_theorem_gate"] = {
        "status": "passed",
        "checked_at": now_iso(),
        "base_audit": gate["base_audit"],
        "architecture_audit": gate["architecture_audit"],
    }
    scope["stage"] = "full-paper"
    scope["full_targets"] = full
    scope["full_targets_policy"] = (
        "all-claims" if args.all_claims or not args.full_target else "explicit"
    )
    scope["promoted_at"] = now_iso()
    scope["updated_at"] = now_iso()
    commit_scope_transaction(
        store, new_scope=scope, new_targets=full, operation="promote-full-paper"
    )
    print(json.dumps(scope, ensure_ascii=False, indent=2))


def cmd_architecture_audit(store: Store, args: argparse.Namespace) -> None:
    result = architecture_audit(store)
    if args.format == "json":
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return
    lines = [
        "# Formalization Architecture Audit",
        "",
        f"- Complete: **{'YES' if result['complete'] else 'NO'}**",
        f"- Targets: {', '.join(result['targets']) if result['targets'] else '(none)'}",
        f"- Related obligations: {', '.join(result['related_obligations']) if result['related_obligations'] else 'none'}",
        f"- Uncovered claims: {', '.join(result['uncovered_claims']) if result['uncovered_claims'] else 'none'}",
        f"- Incomplete obligations: {', '.join(result['incomplete_obligations']) if result['incomplete_obligations'] else 'none'}",
        f"- Open contract tickets: {', '.join(result['open_contract_tickets']) if result['open_contract_tickets'] else 'none'}",
        f"- Unverified required comparators: {', '.join(result['unverified_comparators']) if result['unverified_comparators'] else 'none'}",
        f"- Dependency coverage complete: **{'YES' if result['dependency_coverage']['complete'] else 'NO'}**",
    ]
    if result["validation_errors"]:
        lines.extend(
            ["", "## Validation errors", ""]
            + [f"- {item}" for item in result["validation_errors"]]
        )
    if result["warnings"]:
        lines.extend(
            ["", "## Warnings", ""] + [f"- {item}" for item in result["warnings"]]
        )
    print("\n".join(lines))


def cmd_status(store: Store, _args: argparse.Namespace) -> None:
    obligations = Counter(item["status"] for item in store.obligations())
    contracts = Counter(item["status"] for item in store.contracts())
    comparators = Counter(item["status"] for item in store.comparators())
    gate = verification_gate(store)
    payload = {
        "schema_version": ARCH_SCHEMA_VERSION,
        "verification": {
            "strategy": gate["strategy"],
            "stage": gate["stage"],
            "full_paper_policy": gate["full_paper_policy"],
            "targets": gate["targets"],
            "complete": gate["complete"],
            "verification_result": gate["verification_result"],
            "eligible_for_full_paper": gate["eligible_for_full_paper"],
            "awaiting_full_paper_decision": gate["awaiting_full_paper_decision"],
            "terminal_for_selected_scope": gate["terminal_for_selected_scope"],
            "next_action": gate["next_action"],
            "trust_level": gate["trust_level"],
        },
        "obligations": dict(sorted(obligations.items())),
        "obligation_frontier": [item["id"] for item in obligation_frontier(store)],
        "ticket_contracts": dict(sorted(contracts.items())),
        "parallel_frontier": [
            item["ticket_id"] for item in current_parallel_candidates(store)
        ],
        "comparators": dict(sorted(comparators.items())),
    }
    print(json.dumps(payload, ensure_ascii=False, indent=2))


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="lean4-skills-paper-architecture")
    parser.add_argument("--root", default=".", help="Paper project root")
    sub = parser.add_subparsers(dest="command", required=True)

    p = sub.add_parser("init")
    p.set_defaults(func=cmd_init)

    p = sub.add_parser("freeze-source")
    p.add_argument(
        "--replace",
        action="store_true",
        help="accept an explicitly revised paper source; existing dependency scans become stale",
    )
    p.set_defaults(func=cmd_freeze_source)

    p = sub.add_parser("configure-verification")
    p.add_argument(
        "--strategy", default="target-first", choices=sorted(VERIFICATION_STRATEGIES)
    )
    p.add_argument(
        "--full-paper-policy",
        default="ask",
        choices=sorted(FULL_PAPER_POLICIES),
        help="ask=decide after Stage 1; skip=main theorem only; after-main=continue to full paper after Stage 1",
    )
    p.add_argument("--primary-target", action="append", required=True)
    p.add_argument("--full-target", action="append")
    p.add_argument("--full-all-claims", action="store_true")
    p.set_defaults(func=cmd_configure_verification)

    p = sub.add_parser("set-full-paper-policy")
    p.add_argument("policy", choices=sorted(FULL_PAPER_POLICIES))
    p.set_defaults(func=cmd_set_full_paper_policy)

    p = sub.add_parser("verification-gate")
    p.add_argument("--format", choices=["markdown", "json"], default="markdown")
    p.set_defaults(func=cmd_verification_gate)

    p = sub.add_parser("promote-full-paper")
    p.add_argument("--full-target", action="append")
    p.add_argument("--all-claims", action="store_true")
    p.set_defaults(func=cmd_promote_full_paper)

    p = sub.add_parser("add-obligation")
    p.add_argument("--id", required=True)
    p.add_argument("--title", required=True)
    p.add_argument("--kind", required=True, choices=sorted(OBLIGATION_KINDS))
    p.add_argument("--layer", required=True, choices=sorted(OBLIGATION_LAYERS))
    p.add_argument("--objective", required=True)
    p.add_argument("--claim", action="append")
    p.add_argument("--depends-on", action="append")
    p.add_argument("--input", action="append")
    p.add_argument("--output", action="append")
    p.add_argument("--source-ref", action="append")
    p.add_argument("--read-file", action="append")
    p.add_argument("--owned-file", action="append")
    p.add_argument("--accept", action="append")
    p.add_argument("--forbid", action="append")
    p.add_argument("--risk", default="medium", choices=sorted(RISKS))
    p.add_argument("--hard-unknowns", type=int, default=1)
    p.add_argument("--draft", action="store_true")
    p.set_defaults(func=cmd_add_obligation)

    p = sub.add_parser("set-obligation-deps")
    p.add_argument("id")
    p.add_argument("--depends-on", action="append")
    p.set_defaults(func=cmd_set_obligation_deps)

    p = sub.add_parser("approve-obligations")
    p.add_argument("--id", action="append")
    p.add_argument("--all", action="store_true")
    p.set_defaults(func=cmd_approve_obligations)

    p = sub.add_parser("obligation-frontier")
    p.set_defaults(func=cmd_obligation_frontier)

    p = sub.add_parser("block-obligation")
    p.add_argument("id")
    p.add_argument("--reason", required=True)
    p.add_argument("--next-action")
    p.set_defaults(func=cmd_block_obligation)

    p = sub.add_parser("bind-ticket")
    p.add_argument("ticket_id")
    p.add_argument("--obligation", action="append", required=True)
    p.add_argument("--completes-obligation", action="append")
    p.add_argument("--worker", default="prove", choices=sorted(WORKERS))
    p.add_argument("--read-only", action="store_true")
    p.add_argument("--requires-locked-claim", action="append")
    p.add_argument("--owned-file", action="append")
    p.add_argument("--read-file", action="append")
    p.add_argument("--accept", action="append")
    p.add_argument("--forbid", action="append")
    p.add_argument("--risk", default="medium", choices=sorted(RISKS))
    p.add_argument("--hard-unknowns", type=int, default=1)
    p.add_argument("--estimate-tokens", type=int)
    p.add_argument("--approved", action="store_true")
    p.set_defaults(func=cmd_bind_ticket)

    p = sub.add_parser("approve-contracts")
    p.add_argument("--ticket", action="append")
    p.add_argument("--all", action="store_true")
    p.set_defaults(func=cmd_approve_contracts)

    p = sub.add_parser("check-ticket")
    p.add_argument("ticket_id")
    p.set_defaults(func=cmd_check_ticket)

    p = sub.add_parser("render-dispatch")
    p.add_argument("ticket_id")
    p.add_argument("--out")
    p.set_defaults(func=cmd_render_dispatch)

    p = sub.add_parser("record-dependency-scan")
    p.add_argument("--claim", required=True)
    p.add_argument("--source-ref", action="append", required=True)
    p.add_argument("--internal-claim", action="append")
    p.add_argument("--assumption", action="append")
    p.add_argument("--complete", action="store_true")
    p.add_argument("--note")
    p.set_defaults(func=cmd_record_dependency_scan)

    p = sub.add_parser("verify-ticket")
    p.add_argument("ticket_id")
    p.add_argument("--timeout-seconds", type=int, default=1200)
    p.set_defaults(func=cmd_verify_ticket)

    p = sub.add_parser("satisfy-obligation")
    p.add_argument("id")
    p.add_argument("--ticket", required=True)
    p.add_argument("--verification", choices=["passed", "failed"])
    p.add_argument("--evidence", action="append")
    p.add_argument("--command", action="append")
    p.add_argument("--timeout-seconds", type=int, default=1200)
    p.set_defaults(func=cmd_satisfy_obligation)

    p = sub.add_parser("parallel-frontier")
    p.set_defaults(func=cmd_parallel_frontier)

    p = sub.add_parser("add-comparator")
    p.add_argument("--id", required=True)
    p.add_argument("--target-claim", required=True)
    p.add_argument("--reference-source", required=True)
    p.add_argument("--reference-declaration", required=True)
    p.add_argument("--solution-declaration", required=True)
    p.add_argument("--check-command", action="append")
    p.add_argument("--permitted-axiom", action="append")
    p.add_argument("--required", action="store_true")
    p.add_argument("--draft", action="store_true")
    p.set_defaults(func=cmd_add_comparator)

    p = sub.add_parser("verify-comparator")
    p.add_argument("id")
    p.add_argument("--verification", choices=["passed", "failed"])
    p.add_argument("--evidence", action="append")
    p.add_argument("--command", action="append")
    p.add_argument("--timeout-seconds", type=int, default=1200)
    p.set_defaults(func=cmd_verify_comparator)

    p = sub.add_parser("validate")
    p.set_defaults(func=cmd_validate)

    p = sub.add_parser("architecture-audit")
    p.add_argument("--format", choices=["markdown", "json"], default="markdown")
    p.set_defaults(func=cmd_architecture_audit)

    p = sub.add_parser("status")
    p.set_defaults(func=cmd_status)
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    store = Store(Path(args.root))
    try:
        if args.command != "init":
            if not store.base_initialized():
                raise ArchitectureError("base paper workflow is not initialized")
            for path in (
                store.obligations_path,
                store.contracts_path,
                store.comparators_path,
                store.coverage_path,
                store.scope_path,
            ):
                if not path.exists():
                    raise ArchitectureError(
                        "architecture companion not initialized; run lean4-skills-paper-architecture init"
                    )
            recover_pending_transaction(store)
        args.func(store, args)
    except ArchitectureError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
