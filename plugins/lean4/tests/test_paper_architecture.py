from __future__ import annotations

import contextlib
import importlib.util
import io
import json
import tempfile
import unittest
from pathlib import Path

MODULE_PATH = Path(__file__).resolve().parents[1] / "lib" / "paper_architecture.py"
spec = importlib.util.spec_from_file_location("paper_architecture", MODULE_PATH)
assert spec and spec.loader
arch = importlib.util.module_from_spec(spec)
spec.loader.exec_module(arch)


class PaperArchitectureTest(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        d = self.root / ".formalization"
        d.mkdir(parents=True)
        (self.root / "FORMALIZATION_SPEC.md").write_text("# Spec\n", encoding="utf-8")
        (self.root / "PAPER.md").write_text("# Paper source\n", encoding="utf-8")
        source_sha = arch.sha256_text(
            (self.root / "PAPER.md").read_text(encoding="utf-8")
        )
        (self.root / "Paper").mkdir()
        (self.root / "Paper" / "Base.lean").write_text("-- base\n", encoding="utf-8")
        (self.root / "Paper" / "Main.lean").write_text("-- main\n", encoding="utf-8")
        project = {
            "schema_version": 2,
            "title": "Test Paper",
            "phase": "ticketing",
            "targets": ["P-MAIN"],
            "source": {"path": "PAPER.md", "sha256": source_sha},
            "context_budget": {
                "nominal_tokens": 220000,
                "ticket_target_tokens": 140000,
            },
            "spec": {"path": "FORMALIZATION_SPEC.md", "sha256": "abc123"},
        }
        claims = [
            {
                "id": "P-BASE",
                "title": "Base",
                "depends_on": [],
                "uses_assumptions": [],
                "status": "verified",
                "source": {"section": "2"},
                "statement": {
                    "locked": True,
                    "sha256": "base",
                    "lean_file": "Paper/Base.lean",
                },
            },
            {
                "id": "P-MAIN",
                "title": "Main",
                "depends_on": ["P-BASE"],
                "uses_assumptions": [],
                "status": "ready",
                "source": {"section": "5"},
                "statement": {
                    "locked": True,
                    "sha256": "main",
                    "lean_file": "Paper/Main.lean",
                },
            },
        ]
        tickets = []
        self.write_json(d / "project.json", project)
        self.write_json(d / "claims.json", claims)
        self.write_json(d / "tickets.json", tickets)
        self.run_cli("init")

    def tearDown(self) -> None:
        self.tmp.cleanup()

    @staticmethod
    def write_json(path: Path, value) -> None:
        path.write_text(json.dumps(value, indent=2) + "\n", encoding="utf-8")

    def read_json(self, name: str):
        return json.loads(
            (self.root / ".formalization" / name).read_text(encoding="utf-8")
        )

    def run_cli(self, *args: str, expect: int = 0) -> tuple[str, str]:
        stdout = io.StringIO()
        stderr = io.StringIO()
        with contextlib.redirect_stdout(stdout), contextlib.redirect_stderr(stderr):
            code = arch.main(["--root", str(self.root), *args])
        self.assertEqual(
            code, expect, msg=f"stdout={stdout.getvalue()} stderr={stderr.getvalue()}"
        )
        return stdout.getvalue(), stderr.getvalue()

    def add_ticket(
        self, ticket_id: str, *, status: str = "ready", claim: str = "P-MAIN"
    ) -> None:
        path = self.root / ".formalization" / "tickets.json"
        tickets = json.loads(path.read_text(encoding="utf-8"))
        tickets.append(
            {
                "id": ticket_id,
                "title": ticket_id,
                "kind": "prove",
                "objective": f"prove {ticket_id}",
                "claim_ids": [claim],
                "completes_claims": [],
                "blocked_by": [],
                "requires_claims": [],
                "constraints": [],
                "acceptance": ["build passes"],
                "source_refs": ["paper §5"],
                "status": status,
                "estimate_tokens": 120000,
                "last_handoff": None,
            }
        )
        self.write_json(path, tickets)

    def add_obligation(
        self,
        oid: str,
        *,
        claim: str | None = "P-MAIN",
        dep: str | None = None,
        layer: str = "generic",
        kind: str = "generic_lemma",
        owned: str | None = "Paper/Main.lean",
        accept: str | None = "python3 -c \"print('accept-ok')\"",
        draft: bool = False,
    ) -> None:
        args = [
            "add-obligation",
            "--id",
            oid,
            "--title",
            oid,
            "--kind",
            kind,
            "--layer",
            layer,
            "--objective",
            oid,
            "--risk",
            "medium",
            "--hard-unknowns",
            "1",
        ]
        if claim:
            args += ["--claim", claim]
        if dep:
            args += ["--depends-on", dep]
        if owned:
            owned_path = self.root / owned
            owned_path.parent.mkdir(parents=True, exist_ok=True)
            if not owned_path.exists():
                owned_path.write_text(f"-- {oid}\n", encoding="utf-8")
            args += ["--owned-file", owned]
        if accept:
            args += ["--accept", accept]
        if draft:
            args += ["--draft"]
        self.run_cli(*args)

    def bind(
        self,
        tid: str,
        obligations: list[str],
        *,
        completes: list[str] | None = None,
        owned: str | None = None,
        accept: str | None = None,
        approved: bool = True,
        read_only: bool = False,
        locked_claim: str | None = "P-MAIN",
    ) -> None:
        args = ["bind-ticket", tid]
        for oid in obligations:
            args += ["--obligation", oid]
        for oid in completes or []:
            args += ["--completes-obligation", oid]
        if owned:
            args += ["--owned-file", owned]
        if accept:
            args += ["--accept", accept]
        if locked_claim:
            args += ["--requires-locked-claim", locked_claim]
        if approved:
            args += ["--approved"]
        if read_only:
            args += ["--read-only"]
        self.run_cli(*args)

    def close_ticket(self, tid: str) -> None:
        path = self.root / ".formalization" / "tickets.json"
        tickets = json.loads(path.read_text(encoding="utf-8"))
        for t in tickets:
            if t["id"] == tid:
                t["status"] = "closed"
        self.write_json(path, tickets)

    def mark_claim_verified(self, cid: str) -> None:
        path = self.root / ".formalization" / "claims.json"
        claims = json.loads(path.read_text(encoding="utf-8"))
        for c in claims:
            if c["id"] == cid:
                c["status"] = "verified"
        self.write_json(path, claims)
        self.record_coverage(cid)

    def record_coverage(self, cid: str) -> None:
        claims = {c["id"]: c for c in self.read_json("claims.json")}
        claim = claims[cid]
        args = [
            "record-dependency-scan",
            "--claim",
            cid,
            "--source-ref",
            f"paper:{claim.get('source', {}).get('section', cid)}",
            "--complete",
        ]
        for dep in claim.get("depends_on", []):
            args += ["--internal-claim", dep]
        for assumption in claim.get("uses_assumptions", []):
            args += ["--assumption", assumption]
        self.run_cli(*args)

    def make_claim_fully_verified(self, cid: str) -> None:
        path = self.root / ".formalization" / "claims.json"
        claims = json.loads(path.read_text(encoding="utf-8"))
        for c in claims:
            if c["id"] == cid:
                c["status"] = "verified"
                c["proof"] = {
                    "build": "passed",
                    "sorry_count": 0,
                    "axiom_audit": "passed",
                    "trusted": True,
                    "verified_at": "2026-09-09T00:00:00+00:00",
                }
        self.write_json(path, claims)
        self.record_coverage(cid)

    def fix_spec_fingerprint(self) -> None:
        project_path = self.root / ".formalization" / "project.json"
        project = json.loads(project_path.read_text(encoding="utf-8"))
        text = (self.root / "FORMALIZATION_SPEC.md").read_text(encoding="utf-8")
        project["spec"]["sha256"] = arch.sha256_text(text)
        self.write_json(project_path, project)

    def add_extra_claim(self) -> None:
        path = self.root / ".formalization" / "claims.json"
        claims = json.loads(path.read_text(encoding="utf-8"))
        claims.append(
            {
                "id": "P-EXTRA",
                "title": "Extra paper theorem",
                "depends_on": ["P-BASE"],
                "uses_assumptions": [],
                "status": "ready",
                "source": {"section": "8"},
                "statement": {
                    "locked": True,
                    "sha256": "extra",
                    "lean_file": "Paper/Extra.lean",
                },
                "proof": {
                    "build": "unknown",
                    "sorry_count": None,
                    "axiom_audit": "unknown",
                    "trusted": False,
                    "verified_at": None,
                },
            }
        )
        self.write_json(path, claims)

    def ensure_active_coverage(self) -> None:
        store = arch.Store(self.root)
        existing = {item.get("claim_id") for item in store.coverage()}
        for cid in sorted(arch.active_claim_closure(store)):
            if cid not in existing:
                self.record_coverage(cid)

    def satisfy(self, oid: str, tid: str) -> None:
        self.ensure_active_coverage()
        self.close_ticket(tid)
        self.run_cli(
            "satisfy-obligation",
            oid,
            "--ticket",
            tid,
            "--evidence",
            f"{oid} elaborates",
            "--timeout-seconds",
            "30",
        )

    def test_init_is_additive_and_preserves_base_state(self) -> None:
        before = self.read_json("project.json")
        self.run_cli("init")
        self.assertEqual(before, self.read_json("project.json"))
        self.assertEqual(self.read_json("obligations.json")["schema_version"], 1)
        self.assertEqual(self.read_json("ticket_contracts.json")["items"], [])

    def test_obligation_cycle_is_rejected_and_rolled_back(self) -> None:
        self.add_obligation("O-A")
        self.add_obligation("O-B", dep="O-A")
        self.run_cli("set-obligation-deps", "O-A", "--depends-on", "O-B", expect=2)
        items = {x["id"]: x for x in self.read_json("obligations.json")["items"]}
        self.assertEqual(items["O-A"]["depends_on"], [])
        self.run_cli("validate")

    def test_obligation_frontier_respects_dependencies(self) -> None:
        self.add_obligation("O-A")
        self.add_obligation("O-B", dep="O-A")
        out, _ = self.run_cli("obligation-frontier")
        self.assertEqual([x["id"] for x in json.loads(out)], ["O-A"])

    def test_contract_approval_requires_write_ownership_and_acceptance(self) -> None:
        self.add_ticket("T-1")
        self.add_obligation("O-A", owned=None, accept=None)
        self.bind("T-1", ["O-A"], approved=False, owned=None, accept=None)
        self.run_cli("approve-contracts", "--ticket", "T-1", expect=2)
        contract = self.read_json("ticket_contracts.json")["items"][0]
        self.assertEqual(contract["status"], "draft")

    def test_ticket_gate_requires_locked_statement_and_external_obligation(
        self,
    ) -> None:
        self.add_ticket("T-BASE")
        self.add_ticket("T-MAIN")
        self.add_obligation(
            "O-BASE",
            claim="P-BASE",
            owned="Paper/Base.lean",
            accept="python3 -c \"print('accept-ok')\"",
        )
        self.add_obligation("O-MAIN", dep="O-BASE")
        self.bind("T-BASE", ["O-BASE"], completes=["O-BASE"], locked_claim="P-BASE")
        self.bind("T-MAIN", ["O-MAIN"], completes=["O-MAIN"])
        self.run_cli("check-ticket", "T-MAIN", expect=2)
        self.satisfy("O-BASE", "T-BASE")
        out, _ = self.run_cli("check-ticket", "T-MAIN")
        self.assertTrue(json.loads(out)["ready"])

    def test_dispatch_packet_is_zero_context_contract(self) -> None:
        self.add_ticket("T-1")
        self.add_obligation("O-A")
        self.bind("T-1", ["O-A"], completes=["O-A"])
        self.ensure_active_coverage()
        out, _ = self.run_cli("render-dispatch", "T-1")
        packet = json.loads(Path(out.strip()).read_text(encoding="utf-8"))
        self.assertEqual(packet["schema"], "paper-dispatch/v1")
        self.assertEqual(packet["project"]["spec_sha256"], "abc123")
        self.assertEqual(packet["ticket"]["id"], "T-1")
        self.assertEqual(packet["obligations"][0]["id"], "O-A")
        self.assertIn("Paper/Main.lean", packet["contract"]["owned_files"])
        self.assertEqual(packet["claims"][0]["statement"]["sha256"], "main")

    def test_satisfy_obligation_requires_closed_contracted_ticket_and_writes_evidence(
        self,
    ) -> None:
        self.add_ticket("T-1")
        self.add_obligation("O-A")
        self.bind("T-1", ["O-A"], completes=["O-A"])
        self.run_cli(
            "satisfy-obligation",
            "O-A",
            "--ticket",
            "T-1",
            "--verification",
            "passed",
            "--evidence",
            "proof elaborates",
            expect=2,
        )
        self.satisfy("O-A", "T-1")
        item = self.read_json("obligations.json")["items"][0]
        self.assertEqual(item["status"], "satisfied")
        self.assertTrue((self.root / item["evidence"]["path"]).exists())

    def test_parallel_frontier_detects_write_conflicts(self) -> None:
        for tid in ("T-A", "T-B", "T-C"):
            self.add_ticket(tid)
        self.add_obligation("O-A", owned="Paper/Shared.lean")
        self.add_obligation("O-B", owned="Paper/Shared.lean")
        self.add_obligation("O-C", owned="Paper/Other.lean")
        self.bind("T-A", ["O-A"], completes=["O-A"])
        self.bind("T-B", ["O-B"], completes=["O-B"])
        self.bind("T-C", ["O-C"], completes=["O-C"])
        self.ensure_active_coverage()
        out, _ = self.run_cli("parallel-frontier")
        payload = json.loads(out)
        self.assertIn(["T-A", "T-B"], payload["file_conflicts"])
        batches = payload["parallel_batches"]
        self.assertTrue(any("T-A" in b and "T-C" in b for b in batches))
        self.assertFalse(any("T-A" in b and "T-B" in b for b in batches))

    def test_audit_requires_claim_coverage_and_transitive_generic_obligations(
        self,
    ) -> None:
        # With targets but no obligation mapping, architecture is incomplete.
        out, _ = self.run_cli("architecture-audit", "--format", "json")
        audit = json.loads(out)
        self.assertFalse(audit["complete"])
        self.assertEqual(set(audit["uncovered_claims"]), {"P-BASE", "P-MAIN"})

        self.add_ticket("T-G", claim="P-BASE")
        self.add_ticket("T-M")
        self.add_obligation(
            "O-G",
            claim="P-BASE",
            owned="Paper/Generic.lean",
            accept="python3 -c \"print('accept-ok')\"",
        )
        self.add_obligation("O-M", claim="P-MAIN", dep="O-G")
        self.bind("T-G", ["O-G"], completes=["O-G"], locked_claim="P-BASE")
        self.bind("T-M", ["O-M"], completes=["O-M"])
        self.satisfy("O-G", "T-G")
        self.satisfy("O-M", "T-M")
        self.record_coverage("P-BASE")
        self.record_coverage("P-MAIN")
        out, _ = self.run_cli("architecture-audit", "--format", "json")
        audit = json.loads(out)
        self.assertTrue(audit["complete"])
        self.assertEqual(audit["related_obligations"], ["O-G", "O-M"])

    def test_full_paper_promotion_is_blocked_until_main_theorem_gate_passes(
        self,
    ) -> None:
        self.add_extra_claim()
        self.run_cli(
            "configure-verification",
            "--primary-target",
            "P-MAIN",
            "--full-paper-policy",
            "after-main",
            "--full-all-claims",
        )
        self.run_cli("promote-full-paper", "--all-claims", expect=2)
        scope = self.read_json("verification_scope.json")
        self.assertEqual(scope["stage"], "main-theorem")
        self.assertEqual(self.read_json("project.json")["targets"], ["P-MAIN"])

    def test_target_first_gate_promotes_then_exposes_full_paper_work(self) -> None:
        self.add_extra_claim()
        self.run_cli(
            "configure-verification",
            "--primary-target",
            "P-MAIN",
            "--full-paper-policy",
            "after-main",
            "--full-all-claims",
        )

        # An already-planned full-paper ticket is not executable during Stage 1.
        self.add_ticket("T-X", claim="P-EXTRA")
        self.add_obligation(
            "O-X",
            claim="P-EXTRA",
            owned="Paper/Extra.lean",
            accept="python3 -c \"print('accept-ok')\"",
        )
        self.bind("T-X", ["O-X"], completes=["O-X"], locked_claim="P-EXTRA")
        self.run_cli("check-ticket", "T-X", expect=2)

        self.add_ticket("T-B", claim="P-BASE")
        self.add_ticket("T-M")
        self.add_obligation(
            "O-B",
            claim="P-BASE",
            owned="Paper/Base.lean",
            accept="python3 -c \"print('accept-ok')\"",
        )
        self.add_obligation("O-M", claim="P-MAIN", dep="O-B")
        self.bind("T-B", ["O-B"], completes=["O-B"], locked_claim="P-BASE")
        self.bind("T-M", ["O-M"], completes=["O-M"])
        self.satisfy("O-B", "T-B")
        self.satisfy("O-M", "T-M")
        self.make_claim_fully_verified("P-BASE")
        self.make_claim_fully_verified("P-MAIN")
        self.fix_spec_fingerprint()

        out, _ = self.run_cli("verification-gate", "--format", "json")
        gate = json.loads(out)
        self.assertTrue(gate["complete"])
        self.assertTrue(gate["eligible_for_full_paper"])

        self.run_cli("promote-full-paper", "--all-claims")
        scope = self.read_json("verification_scope.json")
        self.assertEqual(scope["stage"], "full-paper")
        self.assertEqual(scope["main_theorem_gate"]["status"], "passed")
        self.assertEqual(
            set(self.read_json("project.json")["targets"]),
            {"P-BASE", "P-MAIN", "P-EXTRA"},
        )

        # Stage 2 is intentionally incomplete until the newly activated paper work closes.
        self.record_coverage("P-EXTRA")
        out, _ = self.run_cli("verification-gate", "--format", "json")
        full_gate = json.loads(out)
        self.assertFalse(full_gate["complete"])
        self.assertIn("P-EXTRA", full_gate["base_audit"]["unverified_claims"])
        self.assertTrue(json.loads(self.run_cli("check-ticket", "T-X")[0])["ready"])

    def test_main_theorem_only_policy_is_a_terminal_valid_scope(self) -> None:
        self.run_cli(
            "configure-verification",
            "--primary-target",
            "P-MAIN",
            "--full-paper-policy",
            "skip",
        )
        self.add_ticket("T-B", claim="P-BASE")
        self.add_ticket("T-M")
        self.add_obligation(
            "O-B",
            claim="P-BASE",
            owned="Paper/Base.lean",
            accept="python3 -c \"print('accept-ok')\"",
        )
        self.add_obligation("O-M", claim="P-MAIN", dep="O-B")
        self.bind("T-B", ["O-B"], completes=["O-B"], locked_claim="P-BASE")
        self.bind("T-M", ["O-M"], completes=["O-M"])
        self.satisfy("O-B", "T-B")
        self.satisfy("O-M", "T-M")
        self.make_claim_fully_verified("P-BASE")
        self.make_claim_fully_verified("P-MAIN")
        self.fix_spec_fingerprint()

        out, _ = self.run_cli("verification-gate", "--format", "json")
        gate = json.loads(out)
        self.assertTrue(gate["complete"])
        self.assertTrue(gate["terminal_for_selected_scope"])
        self.assertFalse(gate["eligible_for_full_paper"])
        self.assertEqual(gate["next_action"], "complete-selected-scope")
        self.run_cli("promote-full-paper", "--all-claims", expect=2)

    def test_full_paper_policy_can_be_enabled_later_without_redoing_stage_one(
        self,
    ) -> None:
        self.add_extra_claim()
        self.run_cli(
            "configure-verification",
            "--primary-target",
            "P-MAIN",
            "--full-paper-policy",
            "skip",
            "--full-all-claims",
        )
        self.add_ticket("T-B", claim="P-BASE")
        self.add_ticket("T-M")
        self.add_obligation(
            "O-B",
            claim="P-BASE",
            owned="Paper/Base.lean",
            accept="python3 -c \"print('accept-ok')\"",
        )
        self.add_obligation("O-M", claim="P-MAIN", dep="O-B")
        self.bind("T-B", ["O-B"], completes=["O-B"], locked_claim="P-BASE")
        self.bind("T-M", ["O-M"], completes=["O-M"])
        self.satisfy("O-B", "T-B")
        self.satisfy("O-M", "T-M")
        self.make_claim_fully_verified("P-BASE")
        self.make_claim_fully_verified("P-MAIN")
        self.fix_spec_fingerprint()

        self.run_cli("set-full-paper-policy", "after-main")
        out, _ = self.run_cli("verification-gate", "--format", "json")
        gate = json.loads(out)
        self.assertTrue(gate["eligible_for_full_paper"])
        self.assertEqual(gate["next_action"], "promote-full-paper")
        self.run_cli("promote-full-paper", "--all-claims")
        scope = self.read_json("verification_scope.json")
        self.assertEqual(scope["stage"], "full-paper")
        self.assertEqual(scope["full_paper_policy"], "after-main")
        obligation_statuses = {
            item["id"]: item["status"]
            for item in self.read_json("obligations.json")["items"]
        }
        self.assertEqual(
            obligation_statuses,
            {"O-B": "satisfied", "O-M": "satisfied"},
        )

    def test_ask_policy_pauses_after_main_theorem_until_user_chooses(self) -> None:
        self.run_cli(
            "configure-verification",
            "--primary-target",
            "P-MAIN",
            "--full-paper-policy",
            "ask",
        )
        self.add_ticket("T-B", claim="P-BASE")
        self.add_ticket("T-M")
        self.add_obligation(
            "O-B",
            claim="P-BASE",
            owned="Paper/Base.lean",
            accept="python3 -c \"print('accept-ok')\"",
        )
        self.add_obligation("O-M", claim="P-MAIN", dep="O-B")
        self.bind("T-B", ["O-B"], completes=["O-B"], locked_claim="P-BASE")
        self.bind("T-M", ["O-M"], completes=["O-M"])
        self.satisfy("O-B", "T-B")
        self.satisfy("O-M", "T-M")
        self.make_claim_fully_verified("P-BASE")
        self.make_claim_fully_verified("P-MAIN")
        self.fix_spec_fingerprint()

        out, _ = self.run_cli("verification-gate", "--format", "json")
        gate = json.loads(out)
        self.assertTrue(gate["complete"])
        self.assertTrue(gate["awaiting_full_paper_decision"])
        self.assertFalse(gate["terminal_for_selected_scope"])
        self.assertEqual(gate["next_action"], "choose-full-paper-policy")
        self.run_cli("promote-full-paper", "--all-claims", expect=2)

    def test_required_comparator_blocks_audit_until_verified(self) -> None:
        # Cover and satisfy both claims first.
        self.add_ticket("T-B", claim="P-BASE")
        self.add_ticket("T-M")
        self.add_obligation(
            "O-B",
            claim="P-BASE",
            owned="Paper/Base.lean",
            accept="python3 -c \"print('accept-ok')\"",
        )
        self.add_obligation("O-M", claim="P-MAIN", dep="O-B")
        self.bind("T-B", ["O-B"], completes=["O-B"], locked_claim="P-BASE")
        self.bind("T-M", ["O-M"], completes=["O-M"])
        self.satisfy("O-B", "T-B")
        self.satisfy("O-M", "T-M")
        self.record_coverage("P-BASE")
        self.record_coverage("P-MAIN")
        self.run_cli(
            "add-comparator",
            "--id",
            "CMP-MAIN",
            "--target-claim",
            "P-MAIN",
            "--reference-source",
            "independent/reference.lean",
            "--reference-declaration",
            "Reference.main",
            "--solution-declaration",
            "Paper.main",
            "--check-command",
            "python3 -c \"print('accept-ok')\"",
            "--required",
        )
        out, _ = self.run_cli("architecture-audit", "--format", "json")
        self.assertEqual(json.loads(out)["unverified_comparators"], ["CMP-MAIN"])
        self.mark_claim_verified("P-MAIN")
        self.run_cli(
            "verify-comparator",
            "CMP-MAIN",
            "--evidence",
            "Comparator elaborated",
            "--timeout-seconds",
            "30",
        )
        out, _ = self.run_cli("architecture-audit", "--format", "json")
        self.assertTrue(json.loads(out)["complete"])

    def test_mixed_stage_ticket_is_rejected_even_if_one_obligation_is_active(
        self,
    ) -> None:
        self.add_extra_claim()
        self.run_cli(
            "configure-verification",
            "--primary-target",
            "P-MAIN",
            "--full-paper-policy",
            "after-main",
            "--full-all-claims",
        )
        self.add_ticket("T-MIX")
        self.add_obligation("O-IN", claim="P-MAIN")
        self.add_obligation("O-OUT", claim="P-EXTRA", owned="Paper/Extra.lean")
        self.bind("T-MIX", ["O-IN", "O-OUT"], completes=["O-IN"])
        self.ensure_active_coverage()
        out, _ = self.run_cli("check-ticket", "T-MIX", expect=2)
        self.assertIn("O-OUT", out)

    def test_machine_verification_failure_cannot_satisfy_obligation(self) -> None:
        self.add_ticket("T-FAIL")
        self.add_obligation("O-FAIL", accept='python3 -c "import sys; sys.exit(7)"')
        self.bind("T-FAIL", ["O-FAIL"], completes=["O-FAIL"])
        self.ensure_active_coverage()
        self.close_ticket("T-FAIL")
        self.run_cli(
            "satisfy-obligation",
            "O-FAIL",
            "--ticket",
            "T-FAIL",
            "--timeout-seconds",
            "30",
            expect=2,
        )
        status = {
            x["id"]: x["status"] for x in self.read_json("obligations.json")["items"]
        }
        self.assertEqual(status["O-FAIL"], "ready")

    def test_tampered_evidence_invalidates_validation(self) -> None:
        self.add_ticket("T-E")
        self.add_obligation("O-E")
        self.bind("T-E", ["O-E"], completes=["O-E"])
        self.satisfy("O-E", "T-E")
        obligation = {x["id"]: x for x in self.read_json("obligations.json")["items"]}[
            "O-E"
        ]
        evidence_path = self.root / obligation["evidence"]["path"]
        evidence_path.write_text("{}\n", encoding="utf-8")
        self.run_cli("validate", expect=2)

    def test_dependency_coverage_is_required_before_ticket_execution(self) -> None:
        self.add_ticket("T-B", claim="P-BASE")
        self.add_obligation("O-B", claim="P-BASE", owned="Paper/Base.lean")
        self.bind("T-B", ["O-B"], completes=["O-B"], locked_claim="P-BASE")
        out, _ = self.run_cli("check-ticket", "T-B", expect=2)
        payload = json.loads(out)
        self.assertFalse(payload["ready"])
        self.assertTrue(
            any(
                "dependency coverage audit is incomplete" in r
                for r in payload["reasons"]
            )
        )
        audit = arch.dependency_coverage_audit(arch.Store(self.root), ["P-MAIN"])
        self.assertFalse(audit["complete"])
        self.assertEqual(set(audit["missing_scans"]), {"P-BASE", "P-MAIN"})

    def test_source_change_stales_dependency_coverage(self) -> None:
        self.record_coverage("P-BASE")
        (self.root / "PAPER.md").write_text("# changed paper\n", encoding="utf-8")
        project = self.read_json("project.json")
        project["source"]["sha256"] = arch.sha256_text(
            (self.root / "PAPER.md").read_text(encoding="utf-8")
        )
        self.write_json(self.root / ".formalization" / "project.json", project)
        audit = arch.dependency_coverage_audit(arch.Store(self.root), ["P-BASE"])
        self.assertFalse(audit["complete"])
        self.assertEqual(audit["stale_scans"], ["P-BASE"])

    def test_trust_level_reports_conditional_external_assumptions(self) -> None:
        assumptions = [
            {
                "id": "A-EXT",
                "category": "trusted_external",
                "approved": True,
                "title": "External theorem",
            }
        ]
        self.write_json(self.root / ".formalization" / "assumptions.json", assumptions)
        claims = self.read_json("claims.json")
        for claim in claims:
            if claim["id"] == "P-BASE":
                claim["uses_assumptions"] = ["A-EXT"]
        self.write_json(self.root / ".formalization" / "claims.json", claims)
        trust = arch.trust_level_for_targets(arch.Store(self.root), ["P-MAIN"])
        self.assertEqual(trust["level"], "CONDITIONAL_TRUSTED_EXTERNAL")

    def test_research_contract_cannot_complete_formal_obligation(self) -> None:
        self.add_ticket("T-R")
        self.add_obligation("O-R")
        self.run_cli(
            "bind-ticket",
            "T-R",
            "--obligation",
            "O-R",
            "--completes-obligation",
            "O-R",
            "--worker",
            "research",
            "--owned-file",
            "Paper/Main.lean",
            "--approved",
            expect=2,
        )

    def test_pending_scope_transaction_is_rolled_back_on_next_command(self) -> None:
        old_project = self.read_json("project.json")
        old_scope = self.read_json("verification_scope.json")
        journal = {
            "schema": "architecture-transaction/v1",
            "operation": "simulated-crash",
            "started_at": "2026-09-09T00:00:00+00:00",
            "old_project": old_project,
            "old_scope": old_scope,
        }
        self.write_json(
            self.root / ".formalization" / "architecture_transaction.json", journal
        )
        broken_project = dict(old_project)
        broken_project["targets"] = ["P-BASE"]
        self.write_json(self.root / ".formalization" / "project.json", broken_project)
        broken_scope = dict(old_scope)
        broken_scope["primary_targets"] = ["P-BASE"]
        self.write_json(
            self.root / ".formalization" / "verification_scope.json", broken_scope
        )
        self.run_cli("status")
        self.assertEqual(self.read_json("project.json"), old_project)
        self.assertEqual(self.read_json("verification_scope.json"), old_scope)
        self.assertFalse(
            (self.root / ".formalization" / "architecture_transaction.json").exists()
        )

    def test_source_change_invalidates_machine_ticket_evidence(self) -> None:
        self.add_ticket("T-SRC")
        self.add_obligation("O-SRC")
        self.bind("T-SRC", ["O-SRC"], completes=["O-SRC"])
        self.satisfy("O-SRC", "T-SRC")
        (self.root / "Paper" / "Main.lean").write_text(
            "-- changed after verify\n", encoding="utf-8"
        )
        self.run_cli("validate", expect=2)

    def test_explicit_full_paper_strategy_does_not_fake_main_gate_pass(self) -> None:
        self.run_cli(
            "configure-verification",
            "--strategy",
            "full-paper",
            "--primary-target",
            "P-MAIN",
            "--full-all-claims",
        )
        scope = self.read_json("verification_scope.json")
        self.assertEqual(scope["stage"], "full-paper")
        self.assertEqual(
            scope["main_theorem_gate"]["status"], "explicit-full-paper-bypass"
        )
        self.assertNotEqual(scope["main_theorem_gate"]["status"], "passed")

    def test_unrecorded_paper_source_change_blocks_dependency_coverage(self) -> None:
        self.record_coverage("P-BASE")
        (self.root / "PAPER.md").write_text(
            "# silently changed paper\n", encoding="utf-8"
        )
        audit = arch.dependency_coverage_audit(arch.Store(self.root), ["P-BASE"])
        self.assertFalse(audit["complete"])
        self.assertFalse(audit["source_integrity"]["ok"])
        self.assertEqual(
            audit["source_integrity"]["error"], "paper source fingerprint mismatch"
        )

    def test_init_auto_freezes_missing_paper_source_fingerprint(self) -> None:
        project = self.read_json("project.json")
        project["source"]["sha256"] = None
        self.write_json(self.root / ".formalization" / "project.json", project)
        self.run_cli("init")
        frozen = self.read_json("project.json")["source"]["sha256"]
        self.assertEqual(frozen, arch.sha256_file(self.root / "PAPER.md"))

    def test_freeze_source_requires_explicit_replace_on_revision(self) -> None:
        old_sha = self.read_json("project.json")["source"]["sha256"]
        (self.root / "PAPER.md").write_text("# revised paper\n", encoding="utf-8")
        self.run_cli("freeze-source", expect=2)
        self.assertEqual(self.read_json("project.json")["source"]["sha256"], old_sha)
        self.run_cli("freeze-source", "--replace")
        self.assertEqual(
            self.read_json("project.json")["source"]["sha256"],
            arch.sha256_file(self.root / "PAPER.md"),
        )


if __name__ == "__main__":
    unittest.main()
