from __future__ import annotations

import contextlib
import importlib.util
import io
import json
import tempfile
import unittest
from pathlib import Path

MODULE_PATH = Path(__file__).resolve().parents[1] / "lib" / "paper_workflow.py"
spec = importlib.util.spec_from_file_location("paper_workflow", MODULE_PATH)
assert spec and spec.loader
paper_workflow = importlib.util.module_from_spec(spec)
spec.loader.exec_module(paper_workflow)


class PaperWorkflowTest(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        self.source = self.root / "paper.md"
        self.source.write_text("# Paper\n", encoding="utf-8")
        self.run_cli(
            "init",
            "--source",
            str(self.source),
            "--title",
            "Test Paper",
            "--repo",
            "owner/repo",
        )

    def tearDown(self) -> None:
        self.tmp.cleanup()

    def run_cli(self, *args: str, expect: int = 0) -> tuple[str, str]:
        stdout = io.StringIO()
        stderr = io.StringIO()
        with contextlib.redirect_stdout(stdout), contextlib.redirect_stderr(stderr):
            code = paper_workflow.main(["--root", str(self.root), *args])
        self.assertEqual(
            code, expect, msg=f"stderr={stderr.getvalue()} stdout={stdout.getvalue()}"
        )
        return stdout.getvalue(), stderr.getvalue()

    def json_file(self, name: str):
        return json.loads(
            (self.root / ".formalization" / name).read_text(encoding="utf-8")
        )

    def make_grill_ready(self) -> None:
        for category in sorted(paper_workflow.REQUIRED_GRILL_CATEGORIES):
            self.run_cli(
                "record-decision",
                "--category",
                category,
                "--question",
                f"Question for {category}?",
                "--answer",
                f"Resolved {category}",
            )

    def add_claim(self, claim_id: str, *extra: str) -> None:
        self.run_cli(
            "add-claim",
            "--id",
            claim_id,
            "--title",
            claim_id,
            "--claim-type",
            "lemma",
            *extra,
        )

    def lock_claim(self, claim_id: str) -> None:
        statement = self.statement_path(claim_id)
        statement.write_text(
            f"lemma {claim_id.replace('-', '_')} : True := by\n", encoding="utf-8"
        )
        self.run_cli(
            "set-statement",
            claim_id,
            "--file",
            "Paper/Test.lean",
            "--declaration",
            claim_id.replace("-", "_"),
            "--statement-text",
            str(statement),
            "--lock",
        )

    def statement_path(self, claim_id: str) -> Path:
        return self.root / f"{claim_id}.statement"

    def verify_claim(self, claim_id: str) -> None:
        self.run_cli(
            "verify-claim",
            claim_id,
            "--build",
            "passed",
            "--sorries",
            "0",
            "--axioms",
            "passed",
            "--statement-text",
            str(self.statement_path(claim_id)),
        )

    def test_grill_is_durable_and_readiness_is_gated(self) -> None:
        out, _ = self.run_cli("grill-check")
        self.assertFalse(json.loads(out)["ready"])
        self.make_grill_ready()
        out, _ = self.run_cli("grill-check")
        payload = json.loads(out)
        self.assertTrue(payload["ready"])
        self.assertEqual(payload["missing"], [])
        self.assertEqual(len(self.json_file("decisions.json")), 4)

    def test_terms_render_context_without_polluting_spec(self) -> None:
        self.run_cli(
            "add-term",
            "--term",
            "Paper claim",
            "--definition",
            "A result asserted by the paper.",
        )
        context = (self.root / ".formalization" / "CONTEXT.md").read_text(
            encoding="utf-8"
        )
        self.assertIn("## Paper claim", context)
        self.assertIn("A result asserted by the paper.", context)

    def test_paper_claim_cannot_be_smuggled_into_assumptions(self) -> None:
        self.run_cli(
            "add-assumption",
            "--id",
            "P-LEM-001",
            "--category",
            "trusted_external",
            "--title",
            "bad",
            expect=2,
        )
        self.assertEqual(self.json_file("assumptions.json"), [])

    def test_claim_dag_rejects_cycle(self) -> None:
        self.add_claim("P-A")
        self.add_claim("P-B", "--depends-on", "P-A")
        self.run_cli("set-claim-deps", "P-A", "--depends-on", "P-B", expect=2)
        claims = {item["id"]: item for item in self.json_file("claims.json")}
        self.assertEqual(claims["P-A"]["depends_on"], [])

    def test_verified_requires_lock_and_verified_dependencies(self) -> None:
        self.add_claim("P-A")
        self.add_claim("P-B", "--depends-on", "P-A")
        self.lock_claim("P-A")
        self.lock_claim("P-B")
        self.run_cli(
            "verify-claim",
            "P-B",
            "--build",
            "passed",
            "--sorries",
            "0",
            "--axioms",
            "passed",
            "--statement-text",
            str(self.statement_path("P-B")),
            expect=2,
        )
        self.verify_claim("P-A")
        self.verify_claim("P-B")
        claims = {item["id"]: item for item in self.json_file("claims.json")}
        self.assertEqual(claims["P-B"]["status"], "verified")

    def test_statement_unlock_invalidates_trust(self) -> None:
        self.add_claim("P-A")
        self.lock_claim("P-A")
        self.verify_claim("P-A")
        self.run_cli("unlock-statement", "P-A", "--reason", "source mismatch")
        claim = self.json_file("claims.json")[0]
        self.assertEqual(claim["status"], "needs_revision")
        self.assertFalse(claim["proof"]["trusted"])
        self.assertFalse(claim["statement"]["locked"])

    def test_ticket_frontier_uses_ticket_and_claim_dependencies(self) -> None:
        self.add_claim("P-A")
        self.lock_claim("P-A")
        self.run_cli(
            "add-ticket",
            "--id",
            "T-1",
            "--title",
            "prove A",
            "--objective",
            "prove A",
            "--claim",
            "P-A",
            "--accept",
            "A passes",
        )
        self.run_cli(
            "add-ticket",
            "--id",
            "T-2",
            "--title",
            "integrate",
            "--objective",
            "integrate",
            "--claim",
            "P-A",
            "--blocked-by",
            "T-1",
            "--requires-claim",
            "P-A",
            "--accept",
            "integration passes",
        )
        out, _ = self.run_cli("frontier")
        self.assertEqual([item["id"] for item in json.loads(out)], ["T-1"])
        self.verify_claim("P-A")
        self.run_cli("start-ticket", "T-1")
        self.run_cli("finish-ticket", "T-1", "--verification", "passed")
        out, _ = self.run_cli("frontier")
        self.assertEqual([item["id"] for item in json.loads(out)], ["T-2"])

    def test_handoff_makes_ticket_resumable_and_persists_append_only_record(
        self,
    ) -> None:
        self.run_cli(
            "add-ticket",
            "--id",
            "T-1",
            "--title",
            "task",
            "--objective",
            "task",
            "--accept",
            "done",
        )
        self.run_cli("start-ticket", "T-1")
        out, _ = self.run_cli(
            "handoff",
            "T-1",
            "--reason",
            "context-boundary",
            "--completed",
            "helper H1",
            "--current-goal",
            "⊢ True",
            "--remaining",
            "finish proof",
            "--next-action",
            "exact True.intro",
        )
        path = Path(out.strip())
        self.assertTrue(path.exists())
        ticket = self.json_file("tickets.json")[0]
        self.assertEqual(ticket["status"], "partial")
        out, _ = self.run_cli("frontier")
        self.assertEqual([item["id"] for item in json.loads(out)], ["T-1"])

    def test_split_ticket_adds_children_as_parent_blockers(self) -> None:
        for ticket_id in ("T-P", "T-C1", "T-C2"):
            self.run_cli(
                "add-ticket",
                "--id",
                ticket_id,
                "--title",
                ticket_id,
                "--objective",
                ticket_id,
                "--accept",
                "done",
            )
        self.run_cli(
            "split-ticket",
            "T-P",
            "--child",
            "T-C1",
            "--child",
            "T-C2",
            "--reason",
            "too large",
        )
        tickets = {item["id"]: item for item in self.json_file("tickets.json")}
        self.assertEqual(tickets["T-P"]["status"], "blocked")
        self.assertEqual(tickets["T-P"]["blocked_by"], ["T-C1", "T-C2"])
        out, _ = self.run_cli("frontier")
        self.assertEqual({item["id"] for item in json.loads(out)}, {"T-C1", "T-C2"})

    def test_final_audit_reports_conditional_external_trust(self) -> None:
        self.make_grill_ready()
        self.run_cli(
            "add-assumption",
            "--id",
            "EXT-1",
            "--category",
            "trusted_external",
            "--title",
            "External theorem",
            "--source",
            "Published paper theorem 2.1",
            "--approved",
        )
        self.add_claim("P-MAIN", "--uses-assumption", "EXT-1")
        self.lock_claim("P-MAIN")
        self.verify_claim("P-MAIN")
        self.run_cli("set-targets", "--claim", "P-MAIN")
        out, _ = self.run_cli("final-audit", "--format", "json")
        audit = json.loads(out)
        self.assertTrue(audit["complete"])
        self.assertEqual(
            audit["trust_level"],
            "kernel-checked-conditional-on-trusted-external-results",
        )
        self.assertEqual(audit["trusted_external_assumptions"], ["EXT-1"])

    def test_spec_fingerprint_detects_drift(self) -> None:
        self.root.joinpath("FORMALIZATION_SPEC.md").write_text(
            "# Spec\n", encoding="utf-8"
        )
        self.run_cli("record-spec")
        self.run_cli("check-spec")
        self.root.joinpath("FORMALIZATION_SPEC.md").write_text(
            "# Changed\n", encoding="utf-8"
        )
        self.run_cli("check-spec", expect=2)

    def test_verify_claim_rechecks_statement_fingerprint(self) -> None:
        self.add_claim("P-A")
        self.lock_claim("P-A")
        self.statement_path("P-A").write_text(
            "lemma changed : False := by\n", encoding="utf-8"
        )
        self.run_cli(
            "verify-claim",
            "P-A",
            "--build",
            "passed",
            "--sorries",
            "0",
            "--axioms",
            "passed",
            "--statement-text",
            str(self.statement_path("P-A")),
            expect=2,
        )

    def test_draft_tickets_do_not_enter_frontier_until_approved(self) -> None:
        self.run_cli(
            "add-ticket",
            "--id",
            "T-D",
            "--title",
            "draft",
            "--objective",
            "draft",
            "--accept",
            "done",
            "--draft",
        )
        out, _ = self.run_cli("frontier")
        self.assertEqual(json.loads(out), [])
        self.run_cli("approve-tickets", "--id", "T-D")
        out, _ = self.run_cli("frontier")
        self.assertEqual([item["id"] for item in json.loads(out)], ["T-D"])

    def test_open_related_ticket_keeps_final_audit_incomplete(self) -> None:
        self.add_claim("P-MAIN")
        self.lock_claim("P-MAIN")
        self.verify_claim("P-MAIN")
        self.run_cli("set-targets", "--claim", "P-MAIN")
        self.run_cli(
            "add-ticket",
            "--id",
            "T-MAIN",
            "--title",
            "audit main",
            "--objective",
            "audit main",
            "--claim",
            "P-MAIN",
            "--accept",
            "done",
        )
        out, _ = self.run_cli("final-audit", "--format", "json")
        self.assertFalse(json.loads(out)["complete"])
        self.run_cli("start-ticket", "T-MAIN")
        self.run_cli("finish-ticket", "T-MAIN", "--verification", "passed")
        out, _ = self.run_cli("final-audit", "--format", "json")
        self.assertTrue(json.loads(out)["complete"])

    def test_orphaned_in_progress_ticket_can_be_explicitly_recovered(self) -> None:
        self.run_cli(
            "add-ticket",
            "--id",
            "T-O",
            "--title",
            "orphan",
            "--objective",
            "orphan",
            "--accept",
            "done",
        )
        self.run_cli("start-ticket", "T-O")
        out, _ = self.run_cli("frontier")
        self.assertEqual(json.loads(out), [])
        self.run_cli(
            "recover-ticket",
            "T-O",
            "--reason",
            "previous agent process died before handoff",
        )
        out, _ = self.run_cli("frontier")
        self.assertEqual([item["id"] for item in json.loads(out)], ["T-O"])

    def test_split_cycle_failure_rolls_back_parent(self) -> None:
        self.run_cli(
            "add-ticket",
            "--id",
            "T-A",
            "--title",
            "A",
            "--objective",
            "A",
            "--accept",
            "done",
        )
        self.run_cli(
            "add-ticket",
            "--id",
            "T-B",
            "--title",
            "B",
            "--objective",
            "B",
            "--blocked-by",
            "T-A",
            "--accept",
            "done",
        )
        self.run_cli(
            "split-ticket", "T-A", "--child", "T-B", "--reason", "would cycle", expect=2
        )
        tickets = {item["id"]: item for item in self.json_file("tickets.json")}
        self.assertEqual(tickets["T-A"]["blocked_by"], [])
        self.assertEqual(tickets["T-A"]["status"], "ready")
        self.run_cli("validate")

    def test_github_publication_requires_explicit_approval(self) -> None:
        self.run_cli("github-sync", "--repo", "owner/repo", "--tickets", expect=2)

    def test_planning_handoff_is_persisted(self) -> None:
        out, _ = self.run_cli(
            "planning-handoff",
            "--reason",
            "context-boundary",
            "--completed",
            "sections 1-3 mapped",
            "--remaining",
            "map section 4",
            "--next-action",
            "continue claim extraction",
        )
        self.assertTrue(Path(out.strip()).exists())
        project = self.json_file("project.json")
        self.assertEqual(
            project["last_planning_handoff"]["next_action"], "continue claim extraction"
        )

    def test_validate_clean_initial_state(self) -> None:
        self.run_cli("validate")


if __name__ == "__main__":
    unittest.main()
