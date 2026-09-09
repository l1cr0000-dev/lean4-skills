#!/usr/bin/env python3
"""Durable multi-session paper formalization orchestration for lean4-skills.

This module deliberately does not prove Lean theorems.  It owns the persistent
planning state around the existing lean4-skills proof engines:

- grill decisions and project vocabulary,
- trust boundary / external assumptions,
- paper-claim DAG,
- session-sized implementation-ticket DAG,
- statement locks and proof evidence,
- handoffs and tracker projection metadata.

The conversational context is disposable.  The files under `.formalization/`
and the Lean source tree are the recoverable state.
"""

from __future__ import annotations

import argparse
import contextlib
import hashlib
import json
import os
import shutil
import subprocess
import sys
import tempfile
from collections import Counter, deque
from collections.abc import Iterable
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

SCHEMA_VERSION = 2
REQUIRED_GRILL_CATEGORIES = {
    "scope",
    "trust_boundary",
    "statement_policy",
    "completion_policy",
}
ASSUMPTION_CATEGORIES = {
    "foundation",
    "mathlib",
    "formal_import",
    "trusted_external",
}
CLAIM_TYPES = {
    "definition",
    "lemma",
    "proposition",
    "theorem",
    "corollary",
    "claim",
    "other",
}
CLAIM_STATUSES = {
    "identified",
    "formalizing",
    "ready",
    "proving",
    "blocked",
    "verified",
    "rejected",
    "needs_revision",
}
TICKET_STATUSES = {
    "draft",
    "ready",
    "in_progress",
    "partial",
    "blocked",
    "closed",
    "cancelled",
}
TICKET_KINDS = {"formalize", "prove", "integrate", "audit", "research", "other"}


class WorkflowError(RuntimeError):
    pass


def now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def read_text(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8")
    except FileNotFoundError as exc:
        raise WorkflowError(f"file not found: {path}") from exc


def read_json(path: Path, *, default: Any = None) -> Any:
    try:
        with path.open("r", encoding="utf-8") as handle:
            return json.load(handle)
    except FileNotFoundError:
        if default is not None:
            return default
        raise WorkflowError(f"state file not found: {path}") from None
    except json.JSONDecodeError as exc:
        raise WorkflowError(f"invalid JSON in {path}: {exc}") from exc


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


def atomic_write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if not text.endswith("\n"):
        text += "\n"
    fd, tmp_name = tempfile.mkstemp(prefix=f".{path.name}.", dir=str(path.parent))
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            handle.write(text)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(tmp_name, path)
    finally:
        with contextlib.suppress(FileNotFoundError):
            os.unlink(tmp_name)


class Store:
    def __init__(self, root: Path):
        self.root = root.resolve()
        self.dir = self.root / ".formalization"
        self.project_path = self.dir / "project.json"
        self.decisions_path = self.dir / "decisions.json"
        self.terms_path = self.dir / "terms.json"
        self.assumptions_path = self.dir / "assumptions.json"
        self.claims_path = self.dir / "claims.json"
        self.tickets_path = self.dir / "tickets.json"
        self.context_path = self.dir / "CONTEXT.md"
        self.handoffs_dir = self.dir / "handoffs"
        self.generated_dir = self.dir / "generated"
        self.spec_path = self.root / "FORMALIZATION_SPEC.md"

    def initialized(self) -> bool:
        return self.project_path.exists()

    def project(self) -> dict[str, Any]:
        value = read_json(self.project_path)
        if not isinstance(value, dict):
            raise WorkflowError("project.json must contain an object")
        return value

    def decisions(self) -> list[dict[str, Any]]:
        value = read_json(self.decisions_path, default=[])
        if not isinstance(value, list):
            raise WorkflowError("decisions.json must contain a list")
        return value

    def terms(self) -> list[dict[str, Any]]:
        value = read_json(self.terms_path, default=[])
        if not isinstance(value, list):
            raise WorkflowError("terms.json must contain a list")
        return value

    def assumptions(self) -> list[dict[str, Any]]:
        value = read_json(self.assumptions_path, default=[])
        if not isinstance(value, list):
            raise WorkflowError("assumptions.json must contain a list")
        return value

    def claims(self) -> list[dict[str, Any]]:
        value = read_json(self.claims_path, default=[])
        if not isinstance(value, list):
            raise WorkflowError("claims.json must contain a list")
        return value

    def tickets(self) -> list[dict[str, Any]]:
        value = read_json(self.tickets_path, default=[])
        if not isinstance(value, list):
            raise WorkflowError("tickets.json must contain a list")
        return value


def by_id(items: Iterable[dict[str, Any]], kind: str) -> dict[str, dict[str, Any]]:
    out: dict[str, dict[str, Any]] = {}
    for item in items:
        item_id = item.get("id")
        if not isinstance(item_id, str) or not item_id:
            raise WorkflowError(f"every {kind} must have a non-empty string id")
        if item_id in out:
            raise WorkflowError(f"duplicate {kind} id: {item_id}")
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
    index: dict[str, dict[str, Any]], roots: list[str], edge_key: str
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


def topo_order(index: dict[str, dict[str, Any]], edge_key: str) -> list[str]:
    indegree = dict.fromkeys(index, 0)
    reverse: dict[str, list[str]] = {key: [] for key in index}
    for node, item in index.items():
        for dep in item.get(edge_key, []):
            if dep in index:
                indegree[node] += 1
                reverse[dep].append(node)
    queue = deque(sorted(key for key, degree in indegree.items() if degree == 0))
    out: list[str] = []
    while queue:
        node = queue.popleft()
        out.append(node)
        for child in sorted(reverse[node]):
            indegree[child] -= 1
            if indegree[child] == 0:
                queue.append(child)
    if len(out) != len(index):
        raise WorkflowError(
            f"cannot topologically order {edge_key} graph: cycle present"
        )
    return out


def render_context(store: Store) -> None:
    terms = sorted(store.terms(), key=lambda x: x["term"].casefold())
    lines = [
        "# Formalization Context",
        "",
        "Durable vocabulary for this paper formalization. Keep planning prose and proof notes elsewhere.",
        "",
    ]
    if not terms:
        lines.append("_No terms recorded yet._")
    else:
        for term in terms:
            lines.extend([f"## {term['term']}", "", term["definition"], ""])
    atomic_write_text(store.context_path, "\n".join(lines))


def default_project(args: argparse.Namespace) -> dict[str, Any]:
    return {
        "schema_version": SCHEMA_VERSION,
        "title": args.title,
        "source": {"path": args.source, "sha256": None},
        "phase": "grill",
        "targets": [],
        "policy": {
            "paper_claims_may_be_assumptions": False,
            "statement_changes": "planner-only",
            "verified_requires_locked_statement": True,
            "verified_requires_zero_sorry": True,
            "verified_requires_axiom_audit": True,
            "tracker_is_projection": True,
        },
        "context_budget": {
            "nominal_tokens": args.nominal_tokens,
            "ticket_target_tokens": args.ticket_target_tokens,
            "handoff_soft_tokens": args.handoff_soft_tokens,
            "note": "Planning estimates only; runtime token counting is host-dependent.",
        },
        "spec": {"path": "FORMALIZATION_SPEC.md", "sha256": None, "github_issue": None},
        "tracker": {"kind": "github", "repo": args.repo, "native_dependencies": None},
        "created_at": now_iso(),
        "updated_at": now_iso(),
    }


def cmd_init(store: Store, args: argparse.Namespace) -> None:
    if store.initialized() and not args.force:
        raise WorkflowError(f"already initialized: {store.project_path}")
    store.dir.mkdir(parents=True, exist_ok=True)
    store.handoffs_dir.mkdir(parents=True, exist_ok=True)
    store.generated_dir.mkdir(parents=True, exist_ok=True)
    atomic_write_json(store.project_path, default_project(args))
    atomic_write_json(store.decisions_path, [])
    atomic_write_json(store.terms_path, [])
    atomic_write_json(store.assumptions_path, [])
    atomic_write_json(store.claims_path, [])
    atomic_write_json(store.tickets_path, [])
    render_context(store)
    print(store.project_path)


def cmd_record_decision(store: Store, args: argparse.Namespace) -> None:
    decisions = store.decisions()
    decision_id = args.id or f"D-{len(decisions) + 1:03d}"
    if decision_id in by_id(decisions, "decision"):
        raise WorkflowError(f"decision already exists: {decision_id}")
    decisions.append(
        {
            "id": decision_id,
            "category": args.category,
            "question": args.question,
            "answer": args.answer,
            "recommendation": args.recommendation,
            "rationale": args.rationale,
            "status": "resolved",
            "created_at": now_iso(),
        }
    )
    atomic_write_json(store.decisions_path, decisions)
    print(decision_id)


def cmd_add_term(store: Store, args: argparse.Namespace) -> None:
    terms = store.terms()
    existing = next(
        (item for item in terms if item["term"].casefold() == args.term.casefold()),
        None,
    )
    if existing:
        existing["definition"] = args.definition
        existing["updated_at"] = now_iso()
    else:
        terms.append(
            {
                "term": args.term,
                "definition": args.definition,
                "created_at": now_iso(),
                "updated_at": now_iso(),
            }
        )
    atomic_write_json(store.terms_path, terms)
    render_context(store)
    print(store.context_path)


def cmd_grill_check(store: Store, _args: argparse.Namespace) -> None:
    decisions = store.decisions()
    resolved = {
        item["category"] for item in decisions if item.get("status") == "resolved"
    }
    missing = sorted(REQUIRED_GRILL_CATEGORIES - resolved)
    payload = {
        "ready": not missing,
        "resolved_categories": sorted(resolved),
        "missing": missing,
    }
    print(json.dumps(payload, ensure_ascii=False, indent=2))


def cmd_set_phase(store: Store, args: argparse.Namespace) -> None:
    project = store.project()
    project["phase"] = args.phase
    project["updated_at"] = now_iso()
    atomic_write_json(store.project_path, project)
    print(args.phase)


def cmd_set_targets(store: Store, args: argparse.Namespace) -> None:
    claims = by_id(store.claims(), "claim")
    unknown = [claim_id for claim_id in args.claim if claim_id not in claims]
    if unknown:
        raise WorkflowError("unknown target claims: " + ", ".join(unknown))
    project = store.project()
    project["targets"] = list(dict.fromkeys(args.claim))
    project["updated_at"] = now_iso()
    atomic_write_json(store.project_path, project)
    print(json.dumps(project["targets"]))


def cmd_add_assumption(store: Store, args: argparse.Namespace) -> None:
    if args.category not in ASSUMPTION_CATEGORIES:
        raise WorkflowError(f"invalid assumption category: {args.category}")
    if args.id.startswith("P-"):
        raise WorkflowError(
            "paper claims may not be registered as assumptions; add them to claims.json"
        )
    assumptions = store.assumptions()
    if args.id in by_id(assumptions, "assumption"):
        raise WorkflowError(f"assumption already exists: {args.id}")
    assumptions.append(
        {
            "id": args.id,
            "category": args.category,
            "title": args.title,
            "source": args.source,
            "formal_ref": args.formal_ref,
            "approved": args.approved,
            "notes": args.note,
            "created_at": now_iso(),
            "updated_at": now_iso(),
        }
    )
    atomic_write_json(store.assumptions_path, assumptions)
    print(args.id)


def new_claim(args: argparse.Namespace) -> dict[str, Any]:
    return {
        "id": args.id,
        "title": args.title,
        "claim_type": args.claim_type,
        "source": {
            "section": args.section,
            "page": args.page,
            "label": args.label,
            "locator": args.locator,
        },
        "depends_on": list(dict.fromkeys(args.depends_on or [])),
        "uses_assumptions": list(dict.fromkeys(args.uses_assumption or [])),
        "status": "identified",
        "statement": {
            "lean_file": args.file,
            "declaration": args.declaration,
            "locked": False,
            "sha256": None,
            "locked_at": None,
        },
        "proof": {
            "build": "unknown",
            "sorry_count": None,
            "axiom_audit": "unknown",
            "trusted": False,
            "verified_at": None,
        },
        "notes": [],
        "created_at": now_iso(),
        "updated_at": now_iso(),
    }


def cmd_add_claim(store: Store, args: argparse.Namespace) -> None:
    if args.claim_type not in CLAIM_TYPES:
        raise WorkflowError(f"invalid claim type: {args.claim_type}")
    claims = store.claims()
    if args.id in by_id(claims, "claim"):
        raise WorkflowError(f"claim already exists: {args.id}")
    assumptions = by_id(store.assumptions(), "assumption")
    unknown_assumptions = [
        item for item in args.uses_assumption or [] if item not in assumptions
    ]
    if unknown_assumptions:
        raise WorkflowError("unknown assumptions: " + ", ".join(unknown_assumptions))
    claims.append(new_claim(args))
    atomic_write_json(store.claims_path, claims)
    errors = validate(store)
    if errors:
        claims.pop()
        atomic_write_json(store.claims_path, claims)
        raise WorkflowError("claim rejected:\n- " + "\n- ".join(errors))
    print(args.id)


def cmd_set_claim_deps(store: Store, args: argparse.Namespace) -> None:
    claims = store.claims()
    index = by_id(claims, "claim")
    if args.id not in index:
        raise WorkflowError(f"unknown claim: {args.id}")
    old = list(index[args.id].get("depends_on", []))
    index[args.id]["depends_on"] = list(dict.fromkeys(args.depends_on or []))
    index[args.id]["updated_at"] = now_iso()
    atomic_write_json(store.claims_path, claims)
    errors = validate(store)
    if errors:
        index[args.id]["depends_on"] = old
        atomic_write_json(store.claims_path, claims)
        raise WorkflowError("dependency update rejected:\n- " + "\n- ".join(errors))
    print(args.id)


def cmd_set_statement(store: Store, args: argparse.Namespace) -> None:
    claims = store.claims()
    index = by_id(claims, "claim")
    claim = index.get(args.id)
    if not claim:
        raise WorkflowError(f"unknown claim: {args.id}")
    if claim["statement"].get("locked"):
        raise WorkflowError(f"statement is already locked: {args.id}")
    statement_text = (
        read_text(Path(args.statement_text)) if args.statement_text else None
    )
    if args.file is not None:
        claim["statement"]["lean_file"] = args.file
    if args.declaration is not None:
        claim["statement"]["declaration"] = args.declaration
    if statement_text is not None:
        claim["statement"]["sha256"] = sha256_text(statement_text)
    if args.lock:
        if statement_text is None:
            raise WorkflowError(
                "--lock requires --statement-text so the lock has a fingerprint"
            )
        claim["statement"]["locked"] = True
        claim["statement"]["locked_at"] = now_iso()
        claim["status"] = "ready"
    else:
        claim["status"] = "formalizing"
    claim["updated_at"] = now_iso()
    atomic_write_json(store.claims_path, claims)
    print(args.id)


def cmd_check_statement(store: Store, args: argparse.Namespace) -> None:
    claim = by_id(store.claims(), "claim").get(args.id)
    if not claim:
        raise WorkflowError(f"unknown claim: {args.id}")
    expected = claim["statement"].get("sha256")
    if not claim["statement"].get("locked") or not expected:
        raise WorkflowError(f"statement is not fingerprint-locked: {args.id}")
    actual = sha256_text(read_text(Path(args.statement_text)))
    if actual != expected:
        raise WorkflowError(
            f"statement fingerprint mismatch for {args.id}: {actual} != {expected}"
        )
    print("MATCH")


def cmd_unlock_statement(store: Store, args: argparse.Namespace) -> None:
    claims = store.claims()
    claim = by_id(claims, "claim").get(args.id)
    if not claim:
        raise WorkflowError(f"unknown claim: {args.id}")
    claim["statement"]["locked"] = False
    claim["statement"]["locked_at"] = None
    claim["status"] = "needs_revision"
    claim["proof"] = {
        "build": "unknown",
        "sorry_count": None,
        "axiom_audit": "unknown",
        "trusted": False,
        "verified_at": None,
    }
    claim["notes"].append(
        {"at": now_iso(), "kind": "statement_unlock", "reason": args.reason}
    )
    claim["updated_at"] = now_iso()
    atomic_write_json(store.claims_path, claims)
    print(args.id)


def cmd_verify_claim(store: Store, args: argparse.Namespace) -> None:
    claims = store.claims()
    index = by_id(claims, "claim")
    claim = index.get(args.id)
    if not claim:
        raise WorkflowError(f"unknown claim: {args.id}")
    if not claim["statement"].get("locked"):
        raise WorkflowError("cannot verify an unlocked paper claim")
    expected_statement = claim["statement"].get("sha256")
    actual_statement = sha256_text(read_text(Path(args.statement_text)))
    if not expected_statement or actual_statement != expected_statement:
        raise WorkflowError(
            "cannot verify claim: statement fingerprint does not match the locked statement"
        )
    if args.build != "passed" or args.sorries != 0 or args.axioms != "passed":
        raise WorkflowError("verified requires build=passed, sorries=0, axioms=passed")
    for dep in claim.get("depends_on", []):
        if index[dep]["status"] != "verified":
            raise WorkflowError(f"dependency not verified: {dep}")
    assumptions = by_id(store.assumptions(), "assumption")
    for assumption_id in claim.get("uses_assumptions", []):
        assumption = assumptions.get(assumption_id)
        if not assumption or not assumption.get("approved"):
            raise WorkflowError(
                f"assumption is missing or not approved: {assumption_id}"
            )
    claim["status"] = "verified"
    claim["proof"] = {
        "build": "passed",
        "sorry_count": 0,
        "axiom_audit": "passed",
        "trusted": True,
        "verified_at": now_iso(),
    }
    claim["updated_at"] = now_iso()
    atomic_write_json(store.claims_path, claims)
    print(args.id)


def new_ticket(args: argparse.Namespace) -> dict[str, Any]:
    return {
        "id": args.id,
        "title": args.title,
        "kind": args.kind,
        "objective": args.objective,
        "claim_ids": list(dict.fromkeys(args.claim or [])),
        "completes_claims": list(dict.fromkeys(args.completes_claim or [])),
        "blocked_by": list(dict.fromkeys(args.blocked_by or [])),
        "requires_claims": list(dict.fromkeys(args.requires_claim or [])),
        "constraints": list(args.constraint or []),
        "acceptance": list(args.accept or []),
        "source_refs": list(args.source_ref or []),
        "status": "draft" if args.draft else "ready",
        "estimate_tokens": args.estimate_tokens,
        "github": {
            "issue_number": None,
            "url": None,
            "native_blockers": None,
            "parent_spec": None,
        },
        "last_handoff": None,
        "verification": {"status": "unknown", "checked_at": None},
        "created_at": now_iso(),
        "updated_at": now_iso(),
    }


def cmd_add_ticket(store: Store, args: argparse.Namespace) -> None:
    if args.kind not in TICKET_KINDS:
        raise WorkflowError(f"invalid ticket kind: {args.kind}")
    tickets = store.tickets()
    if args.id in by_id(tickets, "ticket"):
        raise WorkflowError(f"ticket already exists: {args.id}")
    claims = by_id(store.claims(), "claim")
    for claim_id in (
        (args.claim or []) + (args.completes_claim or []) + (args.requires_claim or [])
    ):
        if claim_id not in claims:
            raise WorkflowError(f"unknown claim in ticket: {claim_id}")
    tickets.append(new_ticket(args))
    atomic_write_json(store.tickets_path, tickets)
    errors = validate(store)
    if errors:
        tickets.pop()
        atomic_write_json(store.tickets_path, tickets)
        raise WorkflowError("ticket rejected:\n- " + "\n- ".join(errors))
    print(args.id)


def cmd_approve_tickets(store: Store, args: argparse.Namespace) -> None:
    tickets = store.tickets()
    index = by_id(tickets, "ticket")
    ids = list(index) if args.all else list(dict.fromkeys(args.id or []))
    if not ids:
        raise WorkflowError("approve-tickets requires --all or at least one --id")
    old_values: dict[str, tuple[str, str | None]] = {}
    for ticket_id in ids:
        ticket = index.get(ticket_id)
        if not ticket:
            raise WorkflowError(f"unknown ticket: {ticket_id}")
        old_values[ticket_id] = (ticket["status"], ticket.get("updated_at"))
        if ticket["status"] != "draft":
            continue
        ticket["status"] = "ready"
        ticket["updated_at"] = now_iso()
    atomic_write_json(store.tickets_path, tickets)
    errors = validate(store)
    if errors:
        for ticket_id, (status, updated_at) in old_values.items():
            index[ticket_id]["status"] = status
            index[ticket_id]["updated_at"] = updated_at
        atomic_write_json(store.tickets_path, tickets)
        raise WorkflowError("ticket approval rejected:\n- " + "\n- ".join(errors))
    print(json.dumps(ids, ensure_ascii=False))


def cmd_set_ticket_blockers(store: Store, args: argparse.Namespace) -> None:
    tickets = store.tickets()
    index = by_id(tickets, "ticket")
    ticket = index.get(args.id)
    if not ticket:
        raise WorkflowError(f"unknown ticket: {args.id}")
    old = list(ticket.get("blocked_by", []))
    ticket["blocked_by"] = list(dict.fromkeys(args.blocked_by or []))
    ticket["updated_at"] = now_iso()
    atomic_write_json(store.tickets_path, tickets)
    errors = validate(store)
    if errors:
        ticket["blocked_by"] = old
        atomic_write_json(store.tickets_path, tickets)
        raise WorkflowError("blocker update rejected:\n- " + "\n- ".join(errors))
    print(args.id)


def ticket_runnable(
    ticket: dict[str, Any],
    ticket_index: dict[str, dict[str, Any]],
    claim_index: dict[str, dict[str, Any]],
) -> tuple[bool, list[str]]:
    reasons: list[str] = []
    for blocker in ticket.get("blocked_by", []):
        if ticket_index[blocker]["status"] != "closed":
            reasons.append(f"ticket blocker open: {blocker}")
    for claim_id in ticket.get("requires_claims", []):
        if claim_index[claim_id]["status"] != "verified":
            reasons.append(f"required claim not verified: {claim_id}")
    return not reasons, reasons


def frontier(store: Store) -> list[dict[str, Any]]:
    tickets = store.tickets()
    ticket_index = by_id(tickets, "ticket")
    claim_index = by_id(store.claims(), "claim")
    out: list[dict[str, Any]] = []
    for ticket in tickets:
        if ticket["status"] not in {"ready", "partial"}:
            continue
        runnable, _ = ticket_runnable(ticket, ticket_index, claim_index)
        if runnable:
            out.append(ticket)
    return out


def cmd_frontier(store: Store, _args: argparse.Namespace) -> None:
    payload = [
        {
            "id": ticket["id"],
            "title": ticket["title"],
            "status": ticket["status"],
            "estimate_tokens": ticket.get("estimate_tokens"),
            "github_issue": ticket.get("github", {}).get("issue_number"),
        }
        for ticket in frontier(store)
    ]
    print(json.dumps(payload, ensure_ascii=False, indent=2))


def cmd_start_ticket(store: Store, args: argparse.Namespace) -> None:
    tickets = store.tickets()
    ticket_index = by_id(tickets, "ticket")
    claim_index = by_id(store.claims(), "claim")
    ticket = ticket_index.get(args.id)
    if not ticket:
        raise WorkflowError(f"unknown ticket: {args.id}")
    if ticket["status"] not in {"ready", "partial"}:
        raise WorkflowError(f"ticket is not startable from status {ticket['status']}")
    runnable, reasons = ticket_runnable(ticket, ticket_index, claim_index)
    if not runnable:
        raise WorkflowError("ticket is not on frontier:\n- " + "\n- ".join(reasons))
    ticket["status"] = "in_progress"
    ticket["updated_at"] = now_iso()
    atomic_write_json(store.tickets_path, tickets)
    print(args.id)


def cmd_recover_ticket(store: Store, args: argparse.Namespace) -> None:
    tickets = store.tickets()
    ticket = by_id(tickets, "ticket").get(args.id)
    if not ticket:
        raise WorkflowError(f"unknown ticket: {args.id}")
    if ticket["status"] != "in_progress":
        raise WorkflowError(
            f"recover-ticket only applies to in_progress tickets, got {ticket['status']}"
        )
    record = {
        "at": now_iso(),
        "reason": "orphaned-session-recovery",
        "blocker": None,
        "next_action": args.next_action
        or "inspect worktree/git state and resume from the last verified Lean state",
        "note": args.reason,
    }
    ticket["status"] = "partial"
    ticket["last_handoff"] = record
    ticket["updated_at"] = now_iso()
    atomic_write_json(store.tickets_path, tickets)
    print(args.id)


def cmd_finish_ticket(store: Store, args: argparse.Namespace) -> None:
    tickets = store.tickets()
    ticket = by_id(tickets, "ticket").get(args.id)
    if not ticket:
        raise WorkflowError(f"unknown ticket: {args.id}")
    if args.verification != "passed":
        raise WorkflowError("ticket cannot close without --verification=passed")
    ticket["status"] = "closed"
    ticket["verification"] = {
        "status": "passed",
        "checked_at": now_iso(),
        "note": args.note,
    }
    ticket["updated_at"] = now_iso()
    atomic_write_json(store.tickets_path, tickets)
    print(args.id)


def cmd_block_ticket(store: Store, args: argparse.Namespace) -> None:
    tickets = store.tickets()
    ticket = by_id(tickets, "ticket").get(args.id)
    if not ticket:
        raise WorkflowError(f"unknown ticket: {args.id}")
    ticket["status"] = "blocked"
    ticket["last_handoff"] = {
        "at": now_iso(),
        "reason": args.reason,
        "blocker": args.blocker,
        "next_action": args.next_action,
    }
    ticket["updated_at"] = now_iso()
    atomic_write_json(store.tickets_path, tickets)
    print(args.id)


def cmd_split_ticket(store: Store, args: argparse.Namespace) -> None:
    tickets = store.tickets()
    index = by_id(tickets, "ticket")
    parent = index.get(args.id)
    if not parent:
        raise WorkflowError(f"unknown ticket: {args.id}")
    children = args.child or []
    if not children:
        raise WorkflowError(
            "split requires at least one --child ticket id that already exists"
        )
    for child in children:
        if child not in index:
            raise WorkflowError(f"unknown child ticket: {child}")
        if child == args.id:
            raise WorkflowError("ticket cannot block itself")
    old = {
        "blocked_by": list(parent.get("blocked_by", [])),
        "status": parent.get("status"),
        "last_handoff": parent.get("last_handoff"),
        "updated_at": parent.get("updated_at"),
    }
    parent["blocked_by"] = list(dict.fromkeys(parent.get("blocked_by", []) + children))
    parent["status"] = "blocked"
    parent["last_handoff"] = {
        "at": now_iso(),
        "reason": "split",
        "blocker": args.reason,
        "next_action": "complete child tickets, then resume parent",
    }
    parent["updated_at"] = now_iso()
    atomic_write_json(store.tickets_path, tickets)
    errors = validate(store)
    if errors:
        for key, value in old.items():
            parent[key] = value
        atomic_write_json(store.tickets_path, tickets)
        raise WorkflowError("split rejected:\n- " + "\n- ".join(errors))
    print(args.id)


def cmd_handoff(store: Store, args: argparse.Namespace) -> None:
    tickets = store.tickets()
    ticket = by_id(tickets, "ticket").get(args.id)
    if not ticket:
        raise WorkflowError(f"unknown ticket: {args.id}")
    record = {
        "schema_version": SCHEMA_VERSION,
        "ticket_id": args.id,
        "at": now_iso(),
        "reason": args.reason,
        "completed": args.completed or [],
        "current_goal": args.current_goal,
        "failed_approaches": args.failed_approach or [],
        "new_knowledge": args.new_knowledge or [],
        "remaining": args.remaining or [],
        "blocker": args.blocker,
        "next_action": args.next_action,
        "files": args.file or [],
    }
    stamp = record["at"].replace(":", "").replace("+00:00", "Z")
    path = store.handoffs_dir / f"{stamp}-{args.id}.json"
    atomic_write_json(path, record)
    ticket["last_handoff"] = {**record, "path": str(path.relative_to(store.root))}
    ticket["status"] = "blocked" if args.blocked else "partial"
    ticket["updated_at"] = now_iso()
    atomic_write_json(store.tickets_path, tickets)
    print(path)


def cmd_planning_handoff(store: Store, args: argparse.Namespace) -> None:
    project = store.project()
    record = {
        "schema_version": SCHEMA_VERSION,
        "phase": project.get("phase"),
        "at": now_iso(),
        "reason": args.reason,
        "completed": args.completed or [],
        "remaining": args.remaining or [],
        "blocker": args.blocker,
        "next_action": args.next_action,
    }
    stamp = record["at"].replace(":", "").replace("+00:00", "Z")
    path = (
        store.handoffs_dir / f"{stamp}-planning-{project.get('phase', 'unknown')}.json"
    )
    atomic_write_json(path, record)
    project["last_planning_handoff"] = {
        **record,
        "path": str(path.relative_to(store.root)),
    }
    project["updated_at"] = now_iso()
    atomic_write_json(store.project_path, project)
    print(path)


def cmd_record_spec(store: Store, args: argparse.Namespace) -> None:
    path = Path(args.path)
    if not path.is_absolute():
        path = store.root / path
    text = read_text(path)
    project = store.project()
    project["spec"]["path"] = str(path.relative_to(store.root))
    project["spec"]["sha256"] = sha256_text(text)
    project["phase"] = "ticketing"
    project["updated_at"] = now_iso()
    atomic_write_json(store.project_path, project)
    print(project["spec"]["sha256"])


def cmd_check_spec(store: Store, _args: argparse.Namespace) -> None:
    project = store.project()
    spec = project.get("spec", {})
    expected = spec.get("sha256")
    if not expected:
        raise WorkflowError("no recorded spec fingerprint")
    path = store.root / spec["path"]
    actual = sha256_text(read_text(path))
    if actual != expected:
        raise WorkflowError(f"spec fingerprint mismatch: {actual} != {expected}")
    print("MATCH")


def render_ticket_body(store: Store, ticket: dict[str, Any]) -> str:
    project = store.project()
    spec_issue = project.get("spec", {}).get("github_issue")
    lines = [
        f"# {ticket['id']} — {ticket['title']}",
        "",
        f"**Local ticket ID:** `{ticket['id']}`",
        f"**Kind:** `{ticket['kind']}`",
        f"**Parent spec:** `{project.get('spec', {}).get('path', 'FORMALIZATION_SPEC.md')}`"
        + (f" / #{spec_issue}" if spec_issue else ""),
        "",
        "## Objective",
        "",
        ticket.get("objective") or "_Objective not supplied._",
        "",
        "## Paper claims",
        "",
    ]
    claims = ticket.get("claim_ids", [])
    lines.extend([f"- `{item}`" for item in claims] or ["- None"])
    lines.extend(["", "## Blocking edges", ""])
    blockers = ticket.get("blocked_by", [])
    lines.extend(
        [f"- `{item}`" for item in blockers]
        or ["- None — this ticket may be on the frontier."]
    )
    lines.extend(["", "## Required verified claims", ""])
    required = ticket.get("requires_claims", [])
    lines.extend([f"- `{item}`" for item in required] or ["- None"])
    lines.extend(["", "## Source references", ""])
    lines.extend(
        [f"- {item}" for item in ticket.get("source_refs", [])]
        or ["- See parent spec / mapped claim sources."]
    )
    lines.extend(["", "## Constraints", ""])
    constraints = ticket.get("constraints", [])
    lines.extend(
        [f"- {item}" for item in constraints]
        or ["- Do not change locked paper statements."]
    )
    lines.extend(["", "## Acceptance criteria", ""])
    acceptance = ticket.get("acceptance", [])
    lines.extend(
        [f"- [ ] {item}" for item in acceptance]
        or ["- [ ] Ticket-specific verification evidence is recorded."]
    )
    if ticket.get("estimate_tokens"):
        lines.extend(
            [
                "",
                "## Session sizing",
                "",
                f"Planning estimate: ~{ticket['estimate_tokens']} tokens. This is advisory, not a runtime counter.",
            ]
        )
    lines.extend(
        [
            "",
            "## Handoff rule",
            "",
            "If the ticket cannot finish safely in this fresh context, do not silently broaden scope. Persist a paper handoff with completed work, current Lean goal, failed approaches, new mathematical knowledge, remaining work, blocker, and exact next action. If the ticket contains multiple independent hard unknowns, split it into child tickets and make this ticket depend on them.",
            "",
            "## Statement safety",
            "",
            "Proof sessions may not strengthen hypotheses, weaken conclusions, or otherwise edit a locked paper-claim statement. Route statement changes back to planning with `needs_revision`.",
        ]
    )
    return "\n".join(lines) + "\n"


def cmd_render_ticket(store: Store, args: argparse.Namespace) -> None:
    ticket = by_id(store.tickets(), "ticket").get(args.id)
    if not ticket:
        raise WorkflowError(f"unknown ticket: {args.id}")
    text = render_ticket_body(store, ticket)
    if args.out:
        path = Path(args.out)
        if not path.is_absolute():
            path = store.root / path
        atomic_write_text(path, text)
        print(path)
    else:
        print(text, end="")


def ticket_markdown_filename(ticket_id: str) -> str:
    safe = "".join(
        character if character.isalnum() or character in ".-_" else "-"
        for character in ticket_id
    ).strip("-.")
    return f"{safe or 'ticket'}.md"


def markdown_cell(value: object) -> str:
    return str(value).replace("|", "\\|").replace("\n", " ").strip()


def render_ticket_index(
    store: Store,
    ordered_tickets: list[dict[str, Any]],
    filenames: dict[str, str],
) -> str:
    project = store.project()
    lines = [
        "# Paper Ticket Breakdown",
        "",
        f"**Project:** {project.get('title', 'Untitled paper')}",
        "",
        "This directory is a readable Markdown projection of the durable Ticket DAG.",
        "The authoritative state remains `.formalization/tickets.json`; regenerate this",
        "view after changing tickets.",
        "",
        "| Order | Ticket | Status | Kind | Blocked by | Claims |",
        "| ---: | --- | --- | --- | --- | --- |",
    ]
    for order, ticket in enumerate(ordered_tickets, start=1):
        ticket_id = ticket["id"]
        blockers = ", ".join(ticket.get("blocked_by", [])) or "—"
        claims = ", ".join(ticket.get("claim_ids", [])) or "—"
        lines.append(
            "| "
            + " | ".join(
                [
                    str(order),
                    f"[{markdown_cell(ticket_id)}]({filenames[ticket_id]})",
                    markdown_cell(ticket.get("status", "")),
                    markdown_cell(ticket.get("kind", "")),
                    markdown_cell(blockers),
                    markdown_cell(claims),
                ]
            )
            + " |"
        )
    if not ordered_tickets:
        lines.extend(["", "_No tickets have been created yet._"])
    return "\n".join(lines) + "\n"


def cmd_render_tickets(store: Store, args: argparse.Namespace) -> None:
    errors = validate(store)
    if errors:
        raise WorkflowError(
            "cannot render invalid workflow state:\n- " + "\n- ".join(errors)
        )
    tickets = by_id(store.tickets(), "ticket")
    ordered_ids = topo_order(tickets, "blocked_by")
    ordered_tickets = [tickets[ticket_id] for ticket_id in ordered_ids]
    filenames = {
        ticket_id: ticket_markdown_filename(ticket_id) for ticket_id in tickets
    }
    if len(set(filenames.values())) != len(filenames):
        raise WorkflowError("ticket IDs collide after Markdown filename sanitization")

    output_dir = Path(args.out_dir) if args.out_dir else store.generated_dir / "tickets"
    if not output_dir.is_absolute():
        output_dir = store.root / output_dir
    output_dir.mkdir(parents=True, exist_ok=True)
    for ticket in ordered_tickets:
        atomic_write_text(
            output_dir / filenames[ticket["id"]], render_ticket_body(store, ticket)
        )
    index_path = output_dir / "README.md"
    atomic_write_text(
        index_path, render_ticket_index(store, ordered_tickets, filenames)
    )
    print(index_path)


def validate(store: Store) -> list[str]:
    errors: list[str] = []
    try:
        project = store.project()
        decisions = store.decisions()
        assumptions = store.assumptions()
        claims = store.claims()
        tickets = store.tickets()
    except WorkflowError as exc:
        return [str(exc)]

    if project.get("schema_version") != SCHEMA_VERSION:
        errors.append(f"project schema_version must be {SCHEMA_VERSION}")
    try:
        decision_index = by_id(decisions, "decision")
        assumption_index = by_id(assumptions, "assumption")
        claim_index = by_id(claims, "claim")
        ticket_index = by_id(tickets, "ticket")
    except WorkflowError as exc:
        return [str(exc)]
    _ = decision_index

    for assumption_id, assumption in assumption_index.items():
        if assumption.get("category") not in ASSUMPTION_CATEGORIES:
            errors.append(f"{assumption_id}: invalid assumption category")
        if assumption_id.startswith("P-"):
            errors.append(f"{assumption_id}: paper claim encoded as assumption")

    for claim_id, claim in claim_index.items():
        if claim.get("claim_type") not in CLAIM_TYPES:
            errors.append(f"{claim_id}: invalid claim_type")
        if claim.get("status") not in CLAIM_STATUSES:
            errors.append(f"{claim_id}: invalid status {claim.get('status')!r}")
        deps = claim.get("depends_on", [])
        if not isinstance(deps, list) or not all(
            isinstance(item, str) for item in deps
        ):
            errors.append(f"{claim_id}: depends_on must be a list of strings")
            continue
        if claim_id in deps:
            errors.append(f"{claim_id}: self dependency")
        for dep in deps:
            if dep not in claim_index:
                errors.append(f"{claim_id}: unknown dependency {dep}")
        for assumption_id in claim.get("uses_assumptions", []):
            if assumption_id not in assumption_index:
                errors.append(f"{claim_id}: unknown assumption {assumption_id}")
        statement = claim.get("statement", {})
        if claim.get("status") == "verified":
            proof = claim.get("proof", {})
            if statement.get("locked") is not True or not statement.get("sha256"):
                errors.append(
                    f"{claim_id}: verified claim must have a fingerprint-locked statement"
                )
            if proof.get("trusted") is not True:
                errors.append(
                    f"{claim_id}: verified claim must have proof.trusted=true"
                )
            if (
                proof.get("build") != "passed"
                or proof.get("sorry_count") != 0
                or proof.get("axiom_audit") != "passed"
            ):
                errors.append(f"{claim_id}: verified proof evidence incomplete")

    claim_cycle = find_cycle(claim_index, "depends_on")
    if claim_cycle:
        errors.append("claim dependency cycle: " + " -> ".join(claim_cycle))

    for ticket_id, ticket in ticket_index.items():
        if ticket.get("status") not in TICKET_STATUSES:
            errors.append(f"{ticket_id}: invalid ticket status")
        if ticket.get("kind") not in TICKET_KINDS:
            errors.append(f"{ticket_id}: invalid ticket kind")
        blockers = ticket.get("blocked_by", [])
        if ticket_id in blockers:
            errors.append(f"{ticket_id}: self blocker")
        for blocker in blockers:
            if blocker not in ticket_index:
                errors.append(f"{ticket_id}: unknown ticket blocker {blocker}")
        for key in ("claim_ids", "completes_claims", "requires_claims"):
            for claim_id in ticket.get(key, []):
                if claim_id not in claim_index:
                    errors.append(f"{ticket_id}: unknown claim {claim_id} in {key}")

    ticket_cycle = find_cycle(ticket_index, "blocked_by")
    if ticket_cycle:
        errors.append("ticket dependency cycle: " + " -> ".join(ticket_cycle))

    for target in project.get("targets", []):
        if target not in claim_index:
            errors.append(f"unknown project target: {target}")

    return errors


def cmd_validate(store: Store, _args: argparse.Namespace) -> None:
    errors = validate(store)
    if errors:
        raise WorkflowError("validation failed:\n- " + "\n- ".join(errors))
    print("OK")


def final_audit(store: Store) -> dict[str, Any]:
    errors = validate(store)
    project = store.project()
    claims = store.claims()
    assumptions = store.assumptions()
    tickets = store.tickets()
    claim_index = by_id(claims, "claim")
    targets = project.get("targets", [])
    closure = (
        transitive_closure(claim_index, targets, "depends_on") if targets else set()
    )
    unverified = sorted(
        item for item in closure if claim_index[item]["status"] != "verified"
    )
    external_ids: set[str] = set()
    for claim_id in closure:
        external_ids.update(claim_index[claim_id].get("uses_assumptions", []))
    assumption_index = by_id(assumptions, "assumption")
    unapproved = sorted(
        item for item in external_ids if not assumption_index[item].get("approved")
    )
    trusted_external = sorted(
        item
        for item in external_ids
        if assumption_index[item].get("category") == "trusted_external"
    )
    open_tickets = sorted(
        ticket["id"]
        for ticket in tickets
        if ticket["status"] not in {"closed", "cancelled"}
        and any(
            claim_id in closure
            for claim_id in ticket.get("claim_ids", [])
            + ticket.get("completes_claims", [])
        )
    )
    spec_error = None
    spec = project.get("spec", {})
    if spec.get("sha256") and spec.get("path"):
        try:
            actual_spec = sha256_text(read_text(store.root / spec["path"]))
        except WorkflowError as exc:
            spec_error = str(exc)
        else:
            if actual_spec != spec["sha256"]:
                spec_error = "spec fingerprint mismatch"
    if spec_error:
        errors = [*errors, spec_error]
    complete = (
        bool(targets)
        and not errors
        and not unverified
        and not unapproved
        and not open_tickets
    )
    if complete and trusted_external:
        trust_level = "kernel-checked-conditional-on-trusted-external-results"
    elif complete:
        trust_level = "kernel-checked-without-trusted-external-results"
    else:
        trust_level = "incomplete"
    return {
        "complete": complete,
        "trust_level": trust_level,
        "targets": targets,
        "claim_closure_size": len(closure),
        "unverified_claims": unverified,
        "trusted_external_assumptions": trusted_external,
        "unapproved_assumptions": unapproved,
        "open_related_tickets": open_tickets,
        "validation_errors": errors,
    }


def cmd_final_audit(store: Store, args: argparse.Namespace) -> None:
    result = final_audit(store)
    if args.format == "json":
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return
    lines = [
        "# Paper Final Audit",
        "",
        f"- Complete: **{'YES' if result['complete'] else 'NO'}**",
        f"- Trust level: `{result['trust_level']}`",
        f"- Targets: {', '.join(result['targets']) if result['targets'] else '(none)'}",
        f"- Claim closure size: {result['claim_closure_size']}",
        f"- Unverified claims: {', '.join(result['unverified_claims']) if result['unverified_claims'] else 'none'}",
        f"- Trusted external assumptions: {', '.join(result['trusted_external_assumptions']) if result['trusted_external_assumptions'] else 'none'}",
        f"- Unapproved assumptions: {', '.join(result['unapproved_assumptions']) if result['unapproved_assumptions'] else 'none'}",
        f"- Open related tickets: {', '.join(result['open_related_tickets']) if result['open_related_tickets'] else 'none'}",
    ]
    if result["validation_errors"]:
        lines.extend(
            ["", "## Validation errors", ""]
            + [f"- {item}" for item in result["validation_errors"]]
        )
    print("\n".join(lines))


def cmd_status(store: Store, _args: argparse.Namespace) -> None:
    project = store.project()
    claim_counts = Counter(item["status"] for item in store.claims())
    ticket_counts = Counter(item["status"] for item in store.tickets())
    payload = {
        "title": project.get("title"),
        "phase": project.get("phase"),
        "targets": project.get("targets", []),
        "grill": json.loads(capture_grill_check(store)),
        "claims": dict(sorted(claim_counts.items())),
        "tickets": dict(sorted(ticket_counts.items())),
        "frontier": [item["id"] for item in frontier(store)],
        "spec": project.get("spec"),
        "tracker": project.get("tracker"),
        "last_planning_handoff": project.get("last_planning_handoff"),
    }
    print(json.dumps(payload, ensure_ascii=False, indent=2))


def capture_grill_check(store: Store) -> str:
    decisions = store.decisions()
    resolved = {
        item["category"] for item in decisions if item.get("status") == "resolved"
    }
    missing = sorted(REQUIRED_GRILL_CATEGORIES - resolved)
    return json.dumps(
        {
            "ready": not missing,
            "resolved_categories": sorted(resolved),
            "missing": missing,
        }
    )


def gh_run(args: list[str], *, input_text: str | None = None) -> str:
    if shutil.which("gh") is None:
        raise WorkflowError(
            "GitHub CLI `gh` not found; local manifests remain authoritative"
        )
    proc = subprocess.run(
        ["gh", *args],
        input=input_text,
        text=True,
        capture_output=True,
        check=False,
    )
    if proc.returncode != 0:
        raise WorkflowError(
            f"gh {' '.join(args)} failed ({proc.returncode}): {proc.stderr.strip()}"
        )
    return proc.stdout.strip()


def gh_has_flag(command: list[str], flag: str) -> bool:
    try:
        out = gh_run([*command, "--help"])
    except WorkflowError:
        return False
    return flag in out


def parse_issue_url(output: str) -> tuple[int, str]:
    url = output.strip().splitlines()[-1]
    tail = url.rstrip("/").split("/")[-1]
    if not tail.isdigit():
        raise WorkflowError(f"could not parse issue number from gh output: {output!r}")
    return int(tail), url


def cmd_github_sync(store: Store, args: argparse.Namespace) -> None:
    if not args.approved:
        raise WorkflowError(
            "refusing tracker publication without explicit --approved; "
            "re-run with --approved and select --spec and/or --tickets"
        )
    errors = validate(store)
    if errors:
        raise WorkflowError(
            "cannot sync invalid workflow state:\n- " + "\n- ".join(errors)
        )
    project = store.project()
    repo = args.repo or project.get("tracker", {}).get("repo")
    if not repo:
        raise WorkflowError(
            "GitHub repo required via --repo=owner/name or project tracker config"
        )
    project["tracker"]["repo"] = repo

    spec = project["spec"]
    if args.spec and spec.get("github_issue") is None:
        spec_path = store.root / spec["path"]
        body = read_text(spec_path)
        title = f"[SPEC][Lean] {project['title']}"
        output = gh_run(
            ["issue", "create", "--repo", repo, "--title", title, "--body", body]
        )
        number, url = parse_issue_url(output)
        spec["github_issue"] = number
        spec["github_url"] = url
        project["updated_at"] = now_iso()
        atomic_write_json(store.project_path, project)
        print(f"spec #{number}: {url}")
    elif args.spec:
        print(f"spec already mapped: #{spec['github_issue']}")

    if not args.tickets:
        if not args.spec:
            print("nothing to publish: select --spec and/or --tickets")
        project["updated_at"] = now_iso()
        atomic_write_json(store.project_path, project)
        return
    tickets = store.tickets()
    index = by_id(tickets, "ticket")
    if not tickets:
        print("tickets: no tickets available to publish")
        project["updated_at"] = now_iso()
        atomic_write_json(store.project_path, project)
        return
    parent_supported = gh_has_flag(["issue", "create"], "--parent")
    blockers_supported = gh_has_flag(["issue", "create"], "--blocked-by")
    project["tracker"]["native_dependencies"] = blockers_supported
    order = topo_order(index, "blocked_by")
    published_tickets: list[str] = []
    skipped_drafts = 0
    skipped_mapped = 0
    for ticket_id in order:
        ticket = index[ticket_id]
        if ticket["status"] == "draft" and not args.include_drafts:
            skipped_drafts += 1
            continue
        if ticket["github"].get("issue_number") is not None:
            skipped_mapped += 1
            continue
        body = render_ticket_body(store, ticket)
        cmd = [
            "issue",
            "create",
            "--repo",
            repo,
            "--title",
            f"[Lean][{ticket_id}] {ticket['title']}",
            "--body",
            body,
        ]
        spec_issue = project["spec"].get("github_issue")
        if parent_supported and spec_issue:
            cmd.extend(["--parent", str(spec_issue)])
        blocker_numbers = [
            index[item]["github"].get("issue_number")
            for item in ticket.get("blocked_by", [])
        ]
        if blockers_supported and blocker_numbers and all(blocker_numbers):
            cmd.extend(
                ["--blocked-by", ",".join(str(item) for item in blocker_numbers)]
            )
        output = gh_run(cmd)
        number, url = parse_issue_url(output)
        ticket["github"] = {
            "issue_number": number,
            "url": url,
            "native_blockers": bool(
                blockers_supported and blocker_numbers and all(blocker_numbers)
            ),
            "parent_spec": spec_issue if parent_supported else None,
        }
        ticket["updated_at"] = now_iso()
        atomic_write_json(store.tickets_path, tickets)
        published_tickets.append(ticket_id)
        print(f"{ticket_id} -> #{number}: {url}")
    if published_tickets:
        print(f"tickets: published {len(published_tickets)} new issue(s)")
    else:
        print(
            "tickets: no new issues published "
            f"(drafts skipped: {skipped_drafts}; already mapped: {skipped_mapped})"
        )
    project["updated_at"] = now_iso()
    atomic_write_json(store.project_path, project)


def cmd_github_close_ticket(store: Store, args: argparse.Namespace) -> None:
    project = store.project()
    ticket = by_id(store.tickets(), "ticket").get(args.id)
    if not ticket:
        raise WorkflowError(f"unknown ticket: {args.id}")
    repo = args.repo or project.get("tracker", {}).get("repo")
    number = ticket.get("github", {}).get("issue_number")
    if not repo or not number:
        raise WorkflowError("ticket has no GitHub mapping")
    gh_run(["issue", "close", str(number), "--repo", repo, "--comment", args.comment])
    print(f"closed #{number}")


def format_handoff_comment(record: dict[str, Any]) -> str:
    lines = [
        f"## Lean session handoff — {record['at']}",
        "",
        f"**Reason:** {record['reason']}",
        "",
    ]
    sections = [
        ("Completed", record.get("completed", [])),
        ("Failed approaches", record.get("failed_approaches", [])),
        ("New knowledge", record.get("new_knowledge", [])),
        ("Remaining", record.get("remaining", [])),
        ("Files", record.get("files", [])),
    ]
    if record.get("current_goal"):
        lines.extend(
            ["### Current Lean goal", "", "```lean", record["current_goal"], "```", ""]
        )
    for title, values in sections:
        if values:
            lines.extend([f"### {title}", ""] + [f"- {item}" for item in values] + [""])
    if record.get("blocker"):
        lines.extend(["### Blocker", "", record["blocker"], ""])
    if record.get("next_action"):
        lines.extend(["### Exact next action", "", record["next_action"], ""])
    return "\n".join(lines)


def cmd_github_sync_handoff(store: Store, args: argparse.Namespace) -> None:
    project = store.project()
    ticket = by_id(store.tickets(), "ticket").get(args.id)
    if not ticket:
        raise WorkflowError(f"unknown ticket: {args.id}")
    record = ticket.get("last_handoff")
    if not record:
        raise WorkflowError("ticket has no handoff to sync")
    repo = args.repo or project.get("tracker", {}).get("repo")
    number = ticket.get("github", {}).get("issue_number")
    if not repo or not number:
        raise WorkflowError("ticket has no GitHub mapping")
    body = format_handoff_comment(record)
    gh_run(["issue", "comment", str(number), "--repo", repo, "--body", body])
    print(f"commented on #{number}")


def add_common_root(parser: argparse.ArgumentParser) -> None:
    parser.add_argument(
        "--root", default=".", help="Paper project root (default: current directory)"
    )


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="lean4-skills-paper-workflow")
    add_common_root(parser)
    sub = parser.add_subparsers(dest="command", required=True)

    p = sub.add_parser("init")
    p.add_argument("--source", required=True)
    p.add_argument("--title", required=True)
    p.add_argument("--repo")
    p.add_argument("--nominal-tokens", type=int, default=220000)
    p.add_argument("--ticket-target-tokens", type=int, default=140000)
    p.add_argument("--handoff-soft-tokens", type=int, default=175000)
    p.add_argument("--force", action="store_true")
    p.set_defaults(func=cmd_init)

    p = sub.add_parser("record-decision")
    p.add_argument("--id")
    p.add_argument("--category", required=True)
    p.add_argument("--question", required=True)
    p.add_argument("--answer", required=True)
    p.add_argument("--recommendation")
    p.add_argument("--rationale")
    p.set_defaults(func=cmd_record_decision)

    p = sub.add_parser("add-term")
    p.add_argument("--term", required=True)
    p.add_argument("--definition", required=True)
    p.set_defaults(func=cmd_add_term)

    p = sub.add_parser("grill-check")
    p.set_defaults(func=cmd_grill_check)

    p = sub.add_parser("set-phase")
    p.add_argument(
        "phase",
        choices=["grill", "spec", "ticketing", "implementation", "audit", "complete"],
    )
    p.set_defaults(func=cmd_set_phase)

    p = sub.add_parser("add-assumption")
    p.add_argument("--id", required=True)
    p.add_argument("--category", required=True, choices=sorted(ASSUMPTION_CATEGORIES))
    p.add_argument("--title", required=True)
    p.add_argument("--source")
    p.add_argument("--formal-ref")
    p.add_argument("--approved", action="store_true")
    p.add_argument("--note", action="append")
    p.set_defaults(func=cmd_add_assumption)

    p = sub.add_parser("add-claim")
    p.add_argument("--id", required=True)
    p.add_argument("--title", required=True)
    p.add_argument("--claim-type", required=True, choices=sorted(CLAIM_TYPES))
    p.add_argument("--section")
    p.add_argument("--page")
    p.add_argument("--label")
    p.add_argument("--locator")
    p.add_argument("--depends-on", action="append")
    p.add_argument("--uses-assumption", action="append")
    p.add_argument("--file")
    p.add_argument("--declaration")
    p.set_defaults(func=cmd_add_claim)

    p = sub.add_parser("set-claim-deps")
    p.add_argument("id")
    p.add_argument("--depends-on", action="append")
    p.set_defaults(func=cmd_set_claim_deps)

    p = sub.add_parser("set-targets")
    p.add_argument("--claim", action="append", required=True)
    p.set_defaults(func=cmd_set_targets)

    p = sub.add_parser("set-statement")
    p.add_argument("id")
    p.add_argument("--file")
    p.add_argument("--declaration")
    p.add_argument("--statement-text")
    p.add_argument("--lock", action="store_true")
    p.set_defaults(func=cmd_set_statement)

    p = sub.add_parser("check-statement")
    p.add_argument("id")
    p.add_argument("--statement-text", required=True)
    p.set_defaults(func=cmd_check_statement)

    p = sub.add_parser("unlock-statement")
    p.add_argument("id")
    p.add_argument("--reason", required=True)
    p.set_defaults(func=cmd_unlock_statement)

    p = sub.add_parser("verify-claim")
    p.add_argument("id")
    p.add_argument("--build", choices=["passed", "failed"], required=True)
    p.add_argument("--sorries", type=int, required=True)
    p.add_argument("--axioms", choices=["passed", "failed"], required=True)
    p.add_argument("--statement-text", required=True)
    p.set_defaults(func=cmd_verify_claim)

    p = sub.add_parser("add-ticket")
    p.add_argument("--id", required=True)
    p.add_argument("--title", required=True)
    p.add_argument("--kind", default="prove", choices=sorted(TICKET_KINDS))
    p.add_argument("--objective", required=True)
    p.add_argument("--claim", action="append")
    p.add_argument("--completes-claim", action="append")
    p.add_argument("--blocked-by", action="append")
    p.add_argument("--requires-claim", action="append")
    p.add_argument("--constraint", action="append")
    p.add_argument("--accept", action="append")
    p.add_argument("--source-ref", action="append")
    p.add_argument("--estimate-tokens", type=int)
    p.add_argument("--draft", action="store_true")
    p.set_defaults(func=cmd_add_ticket)

    p = sub.add_parser("approve-tickets")
    p.add_argument("--id", action="append")
    p.add_argument("--all", action="store_true")
    p.set_defaults(func=cmd_approve_tickets)

    p = sub.add_parser("set-ticket-blockers")
    p.add_argument("id")
    p.add_argument("--blocked-by", action="append")
    p.set_defaults(func=cmd_set_ticket_blockers)

    p = sub.add_parser("frontier")
    p.set_defaults(func=cmd_frontier)

    p = sub.add_parser("start-ticket")
    p.add_argument("id")
    p.set_defaults(func=cmd_start_ticket)

    p = sub.add_parser("recover-ticket")
    p.add_argument("id")
    p.add_argument("--reason", required=True)
    p.add_argument("--next-action")
    p.set_defaults(func=cmd_recover_ticket)

    p = sub.add_parser("finish-ticket")
    p.add_argument("id")
    p.add_argument("--verification", choices=["passed", "failed"], required=True)
    p.add_argument("--note")
    p.set_defaults(func=cmd_finish_ticket)

    p = sub.add_parser("block-ticket")
    p.add_argument("id")
    p.add_argument("--reason", required=True)
    p.add_argument("--blocker")
    p.add_argument("--next-action")
    p.set_defaults(func=cmd_block_ticket)

    p = sub.add_parser("split-ticket")
    p.add_argument("id")
    p.add_argument("--child", action="append", required=True)
    p.add_argument("--reason", required=True)
    p.set_defaults(func=cmd_split_ticket)

    p = sub.add_parser("handoff")
    p.add_argument("id")
    p.add_argument("--reason", required=True)
    p.add_argument("--completed", action="append")
    p.add_argument("--current-goal")
    p.add_argument("--failed-approach", action="append")
    p.add_argument("--new-knowledge", action="append")
    p.add_argument("--remaining", action="append")
    p.add_argument("--blocker")
    p.add_argument("--next-action")
    p.add_argument("--file", action="append")
    p.add_argument("--blocked", action="store_true")
    p.set_defaults(func=cmd_handoff)

    p = sub.add_parser("planning-handoff")
    p.add_argument("--reason", required=True)
    p.add_argument("--completed", action="append")
    p.add_argument("--remaining", action="append")
    p.add_argument("--blocker")
    p.add_argument("--next-action")
    p.set_defaults(func=cmd_planning_handoff)

    p = sub.add_parser("record-spec")
    p.add_argument("--path", default="FORMALIZATION_SPEC.md")
    p.set_defaults(func=cmd_record_spec)

    p = sub.add_parser("check-spec")
    p.set_defaults(func=cmd_check_spec)

    p = sub.add_parser("render-ticket")
    p.add_argument("id")
    p.add_argument("--out")
    p.set_defaults(func=cmd_render_ticket)

    p = sub.add_parser("render-tickets")
    p.add_argument("--out-dir")
    p.set_defaults(func=cmd_render_tickets)

    p = sub.add_parser("status")
    p.set_defaults(func=cmd_status)

    p = sub.add_parser("validate")
    p.set_defaults(func=cmd_validate)

    p = sub.add_parser("final-audit")
    p.add_argument("--format", choices=["markdown", "json"], default="markdown")
    p.set_defaults(func=cmd_final_audit)

    p = sub.add_parser("github-sync")
    p.add_argument("--repo")
    p.add_argument("--approved", action="store_true")
    p.add_argument("--spec", action="store_true")
    p.add_argument("--tickets", action="store_true")
    p.add_argument("--include-drafts", action="store_true")
    p.set_defaults(func=cmd_github_sync)

    p = sub.add_parser("github-close-ticket")
    p.add_argument("id")
    p.add_argument("--repo")
    p.add_argument(
        "--comment",
        default="Lean ticket acceptance criteria verified; local workflow state is closed.",
    )
    p.set_defaults(func=cmd_github_close_ticket)

    p = sub.add_parser("github-sync-handoff")
    p.add_argument("id")
    p.add_argument("--repo")
    p.set_defaults(func=cmd_github_sync_handoff)

    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    store = Store(Path(args.root))
    try:
        if args.command != "init" and not store.initialized():
            raise WorkflowError(f"paper workflow not initialized under {store.root}")
        args.func(store, args)
    except WorkflowError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
