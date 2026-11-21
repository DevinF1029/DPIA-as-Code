"""End-to-end unit tests for DPIA-as-Code analysis engines (DFD, Threshold, LINDDUN, Gate)."""

from __future__ import annotations

import copy
import sys
import unittest
from datetime import date
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from dpia_as_code.engines import assess_dataflow  # noqa: E402
from dpia_as_code.loader import load_dataflow, parse_dataflow_yaml  # noqa: E402
from dpia_as_code.models import Jurisdiction, RedLineId, RiskLevel  # noqa: E402


class TestEndToEndExamples(unittest.TestCase):
    def test_facial_recognition_kyc_blocks_on_red_lines_and_high_risks(self) -> None:
        model = load_dataflow(ROOT / "examples" / "facial_recognition_kyc.yaml")
        report = assess_dataflow(model)

        # DFD & RoPA
        self.assertIn("flowchart LR", report.mermaid_dfd)
        self.assertIn("CROSS-BORDER CN->SG", report.mermaid_dfd)
        self.assertEqual(len(report.ropa), 2)

        # Mandatory DPIA/PIA triggered under both GDPR & PIPL
        self.assertTrue(report.threshold.dpia_required)
        by_juris = {r.jurisdiction: r for r in report.threshold.results}
        self.assertTrue(by_juris[Jurisdiction.GDPR].dpia_required)
        self.assertTrue(by_juris[Jurisdiction.PIPL].dpia_required)

        # Red lines RL-03 (cross-border none) and RL-05 (ADM without human review) must fire
        rl_ids = {rl.red_line_id for rl in report.gate.red_line_violations}
        self.assertIn(RedLineId.RL_03, rl_ids)
        self.assertIn(RedLineId.RL_05, rl_ids)

        # Planned mitigation must NOT reduce risk (stays in planned_mitigations)
        adm_finding = next(
            f for f in report.findings if f.finding_id == "LIND-U-risk_scoring_engine"
        )
        self.assertIn("mit_human_review_roadmap", adm_finding.planned_mitigations)
        self.assertEqual(adm_finding.applied_mitigations, [])
        self.assertEqual(adm_finding.inherent_risk.score, adm_finding.residual_risk.score)

        # Gate must BLOCK with exit code 1
        self.assertEqual(report.gate.status, "block")
        self.assertEqual(report.gate.exit_code, 1)

    def test_static_marketing_site_passes_cleanly(self) -> None:
        model = load_dataflow(ROOT / "examples" / "static_marketing_site.yaml")
        report = assess_dataflow(model)

        self.assertFalse(report.threshold.dpia_required)
        self.assertEqual(report.gate.red_line_violations, [])
        self.assertEqual(report.risk_summary.overall_residual_level, RiskLevel.LOW)
        self.assertEqual(report.gate.status, "pass")
        self.assertEqual(report.gate.exit_code, 0)

    def test_banking_retail_credit_ai_triggers_all_three_and_warns(self) -> None:
        model = load_dataflow(ROOT / "examples" / "banking_retail_credit_ai.yaml")
        report = assess_dataflow(model)

        self.assertTrue(report.threshold.dpia_required)
        self.assertTrue(report.threshold.fria_required)
        self.assertTrue(report.threshold.important_data_assessment_required)
        self.assertEqual(report.gate.red_line_violations, [])
        self.assertEqual(report.risk_summary.overall_inherent_level, RiskLevel.HIGH)
        self.assertEqual(report.risk_summary.overall_residual_level, RiskLevel.MEDIUM)
        self.assertEqual(report.gate.status, "warn")
        self.assertEqual(report.gate.exit_code, 0)


class TestGovernancePolicyEdgeCases(unittest.TestCase):
    def setUp(self) -> None:
        raw = (ROOT / "examples" / "static_marketing_site.yaml").read_text(encoding="utf-8")
        self.base_payload = yaml.safe_load(raw)

    def _run(self, payload: dict, as_of: date | None = None):
        model = parse_dataflow_yaml(yaml.safe_dump(payload))
        return assess_dataflow(model, as_of=as_of)

    def test_cross_jurisdiction_legitimate_interests_conflict_blocks(self) -> None:
        payload = copy.deepcopy(self.base_payload)
        payload["processes"][0]["lawful_basis"] = "legitimate_interests"
        report = self._run(payload)

        self.assertTrue(
            any("CONFLICT-LB-LEGITIMATE-INTERESTS" in c for c in report.threshold.jurisdiction_conflicts)
        )
        self.assertEqual(report.gate.status, "block")
        self.assertEqual(report.gate.exit_code, 1)

    def test_waiver_active_vs_expired_gate_behavior(self) -> None:
        payload = copy.deepcopy(self.base_payload)
        # Create a non-red-line HIGH residual risk: large scale + indefinite retention on inquiry_db
        payload["metadata"]["estimated_subjects"] = 200000
        payload["stores"][0]["retention_days"] = None
        # Remove retention mitigation so LIND-NC-inquiry_db stays HIGH (3x3=9)
        payload["mitigations"] = [payload["mitigations"][0]]
        payload["metadata"]["risk_waivers"] = [
            {
                "waiver_id": "waiver_ret_01",
                "target_findings": ["LIND-NC-inquiry_db"],
                "risk_level": "high",
                "business_justification": "Legacy DB archival migration scheduled for Q2 sprint.",
                "compensating_controls": ["Manual monthly purge review"],
                "remediation_ticket": "PRIV-109",
                "owner": "web-infra",
                "approved_by": "dpo@acme-example.eu",
                "approved_at": "2026-01-01",
                "expires_at": "2026-03-01",
            }
        ]

        # Active waiver -> WARN (exit 0)
        active_report = self._run(payload, as_of=date(2026, 2, 1))
        self.assertEqual(active_report.gate.status, "warn")
        self.assertEqual(active_report.gate.exit_code, 0)
        self.assertEqual(active_report.gate.waiver_evaluations[0].status, "active")

        # Expired waiver -> automatically reverts to BLOCK (exit 1)
        expired_report = self._run(payload, as_of=date(2026, 4, 1))
        self.assertEqual(expired_report.gate.status, "block")
        self.assertEqual(expired_report.gate.exit_code, 1)
        self.assertEqual(expired_report.gate.waiver_evaluations[0].status, "expired")

    def test_ai_prohibited_practice_triggers_rl01_and_high_risk_triggers_fria(self) -> None:
        payload = copy.deepcopy(self.base_payload)
        payload["metadata"]["jurisdictions"] = ["GDPR", "EU_AI_ACT"]
        payload["metadata"]["ai_system"] = {
            "is_ai_system": True,
            "risk_tier": "prohibited",
            "prohibited_practices": ["social_scoring"],
            "transparency_notice": True,
        }
        report = self._run(payload)
        self.assertIn(RedLineId.RL_01, {r.red_line_id for r in report.gate.red_line_violations})
        self.assertEqual(report.gate.status, "block")

        # Switch to high_risk (no prohibited practice) -> FRIA required
        payload["metadata"]["ai_system"] = {
            "is_ai_system": True,
            "risk_tier": "high_risk",
            "prohibited_practices": [],
            "transparency_notice": True,
        }
        fria_report = self._run(payload)
        self.assertTrue(fria_report.threshold.fria_required)
        self.assertEqual(fria_report.gate.red_line_violations, [])

    def test_ciio_and_important_data_triggers_cn_dsl_assessment(self) -> None:
        payload = copy.deepcopy(self.base_payload)
        payload["metadata"]["is_ciio"] = True
        payload["data_assets"][0]["data_classification"] = "important"
        report = self._run(payload)
        self.assertTrue(report.threshold.important_data_assessment_required)


if __name__ == "__main__":
    unittest.main()
