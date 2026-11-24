"""Unit tests for DPIA-as-Code core data models, loader, and JSON Schema."""

from __future__ import annotations

import copy
import json
import sys
import unittest
from datetime import date
from pathlib import Path

import yaml
from jsonschema import Draft202012Validator

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from dpia_as_code.loader import (
    DataFlowValidationError,
    export_json_schema,
    load_dataflow,
    parse_dataflow_yaml,
)
from dpia_as_code.models import (
    AIRiskTier,
    DataAsset,
    DataCategory,
    DataClassification,
    DataFlowModel,
    FinancialDataLevel,
    IdentifiabilityLevel,
    IndustrySector,
    Jurisdiction,
    ProcessingScale,
    RiskLevel,
    RiskScore,
)


class TestExamplesAndHelpers(unittest.TestCase):
    def test_load_facial_recognition_example(self) -> None:
        model = load_dataflow(ROOT / "examples" / "facial_recognition_kyc.yaml")
        self.assertEqual(model.metadata.system_id, "cross-border-face-kyc")
        self.assertEqual(model.metadata.scale, ProcessingScale.LARGE)
        self.assertEqual(model.resolve_region("kyc_gateway"), "CN")
        self.assertEqual(model.resolve_region("sg_ai_vendor"), "SG")

        # Cross-border & third-party detection
        cb_flows = model.get_cross_border_flows()
        self.assertEqual([f.id for f in cb_flows], ["flow_kyc_to_sg_ai"])

        tp_flows = model.get_third_party_flows()
        self.assertEqual([f.id for f in tp_flows], ["flow_kyc_to_sg_ai"])

        # Mitigation resolution includes both wildcard and targeted controls
        vault_mits = [m.id for m in model.get_mitigations_for("biometric_vault")]
        self.assertEqual(set(vault_mits), {"mit_kms_vault", "mit_tls_global"})

        # No DFD topology warnings on clean architecture
        self.assertEqual(model.topology_warnings(), [])

    def test_load_static_marketing_example(self) -> None:
        model = load_dataflow(ROOT / "examples" / "static_marketing_site.yaml")
        self.assertEqual(model.metadata.scale, ProcessingScale.SMALL)
        self.assertEqual(model.resolve_region("contact_api"), "EU-DE")
        self.assertEqual(model.get_cross_border_flows(), [])
        self.assertEqual(model.get_third_party_flows(), [])

        inquiry = model.data_asset_map()["inquiry_contact"]
        self.assertTrue(inquiry.is_personal_data)
        self.assertFalse(inquiry.is_sensitive_for(Jurisdiction.GDPR))
        self.assertFalse(inquiry.is_sensitive_for(Jurisdiction.PIPL))

    def test_sensitivity_taxonomy_gdpr_vs_pipl(self) -> None:
        financial = DataAsset(
            id="bank_card",
            name="Bank Card Number",
            categories=[DataCategory.FINANCIAL_ACCOUNT],
        )
        # Financial accounts are explicitly sensitive under PIPL Art. 28,
        # whereas GDPR Art. 9 special categories exclude financial data.
        self.assertTrue(financial.is_sensitive_for(Jurisdiction.PIPL))
        self.assertFalse(financial.is_sensitive_for(Jurisdiction.GDPR))

        anonymized_bio = DataAsset(
            id="anon_stats",
            name="Anonymized Biometric Benchmark",
            categories=[DataCategory.BIOMETRIC],
            identifiability=IdentifiabilityLevel.ANONYMIZED,
        )
        self.assertFalse(anonymized_bio.is_personal_data)
        self.assertFalse(anonymized_bio.is_sensitive_any)

    def test_risk_score_matrix(self) -> None:
        self.assertEqual(RiskScore.from_matrix(1, 4).level, RiskLevel.LOW)
        self.assertEqual(RiskScore.from_matrix(2, 3).level, RiskLevel.MEDIUM)
        self.assertEqual(RiskScore.from_matrix(3, 3).level, RiskLevel.HIGH)
        self.assertEqual(RiskScore.from_matrix(3, 4).level, RiskLevel.HIGH)
        self.assertEqual(RiskScore.from_matrix(4, 4).level, RiskLevel.CRITICAL)


class TestValidationErrors(unittest.TestCase):
    def setUp(self) -> None:
        raw = (ROOT / "examples" / "static_marketing_site.yaml").read_text(encoding="utf-8")
        self.base_payload = yaml.safe_load(raw)

    def _validate(self, payload: dict) -> DataFlowModel:
        return parse_dataflow_yaml(yaml.safe_dump(payload))

    def test_unknown_field_is_rejected(self) -> None:
        payload = copy.deepcopy(self.base_payload)
        payload["stores"][0]["enrypted_at_rest"] = True  # intentional typo
        with self.assertRaises(DataFlowValidationError) as ctx:
            self._validate(payload)
        self.assertIn("enrypted_at_rest", str(ctx.exception))

    def test_undefined_flow_target_is_rejected(self) -> None:
        payload = copy.deepcopy(self.base_payload)
        payload["flows"][0]["target"] = "nonexistent_service"
        with self.assertRaises(DataFlowValidationError) as ctx:
            self._validate(payload)
        self.assertIn("nonexistent_service", str(ctx.exception))

    def test_undefined_data_asset_in_store_is_rejected(self) -> None:
        payload = copy.deepcopy(self.base_payload)
        payload["stores"][0]["data"].append("ghost_asset")
        with self.assertRaises(DataFlowValidationError) as ctx:
            self._validate(payload)
        self.assertIn("ghost_asset", str(ctx.exception))

    def test_undefined_mitigation_target_is_rejected(self) -> None:
        payload = copy.deepcopy(self.base_payload)
        payload["mitigations"][0]["applies_to"] = ["missing_node"]
        with self.assertRaises(DataFlowValidationError) as ctx:
            self._validate(payload)
        self.assertIn("missing_node", str(ctx.exception))

    def test_verified_mitigation_requires_evidence(self) -> None:
        payload = copy.deepcopy(self.base_payload)
        payload["mitigations"][0]["evidence"] = None
        with self.assertRaises(DataFlowValidationError) as ctx:
            self._validate(payload)
        self.assertIn("evidence", str(ctx.exception))

    def test_self_loop_flow_is_rejected(self) -> None:
        payload = copy.deepcopy(self.base_payload)
        payload["flows"][0]["source"] = "contact_api"
        payload["flows"][0]["target"] = "contact_api"
        with self.assertRaises(DataFlowValidationError) as ctx:
            self._validate(payload)
        self.assertIn("identical source and target", str(ctx.exception))

    def test_duplicate_node_ids_rejected(self) -> None:
        payload = copy.deepcopy(self.base_payload)
        payload["stores"][0]["id"] = "contact_api"
        with self.assertRaises(DataFlowValidationError) as ctx:
            self._validate(payload)
        self.assertIn("Duplicate IDs", str(ctx.exception))

    def test_dpo_signoff_requires_reviewer(self) -> None:
        payload = copy.deepcopy(self.base_payload)
        payload["metadata"]["dpo_signoff"] = {"approved": True}
        with self.assertRaises(DataFlowValidationError) as ctx:
            self._validate(payload)
        self.assertIn("reviewer", str(ctx.exception))

    def test_topology_warning_for_direct_entity_to_store(self) -> None:
        payload = copy.deepcopy(self.base_payload)
        payload["flows"].append(
            {
                "id": "flow_direct_db_access",
                "source": "site_visitor",
                "target": "inquiry_db",
                "data": ["inquiry_contact"],
            }
        )
        model = self._validate(payload)
        warnings = model.topology_warnings()
        self.assertEqual(len(warnings), 1)
        self.assertIn("without an intermediate Process", warnings[0])


class TestJsonSchemaExport(unittest.TestCase):
    def test_exported_schema_validates_examples(self) -> None:
        schema_path = ROOT / "schemas" / "dataflow.schema.json"
        schema = export_json_schema()
        Draft202012Validator.check_schema(schema)
        validator = Draft202012Validator(schema)

        for example_name in (
            "facial_recognition_kyc.yaml",
            "static_marketing_site.yaml",
            "banking_retail_credit_ai.yaml",
        ):
            raw = yaml.safe_load((ROOT / "examples" / example_name).read_text(encoding="utf-8"))
            errors = list(validator.iter_errors(raw))
            self.assertEqual(errors, [], f"JSON Schema errors in {example_name}: {errors}")

        if schema_path.is_file():
            on_disk = json.loads(schema_path.read_text(encoding="utf-8"))
            self.assertEqual(on_disk, schema)


class TestStep2GovernanceExtensions(unittest.TestCase):
    def setUp(self) -> None:
        raw = (ROOT / "examples" / "static_marketing_site.yaml").read_text(encoding="utf-8")
        self.base_payload = yaml.safe_load(raw)

    def _validate(self, payload: dict) -> DataFlowModel:
        return parse_dataflow_yaml(yaml.safe_dump(payload))

    def test_ciio_classification_ai_and_financial_hooks(self) -> None:
        payload = copy.deepcopy(self.base_payload)
        payload["metadata"]["jurisdictions"] = ["GDPR", "PIPL", "EU_AI_ACT", "CN_DSL_NDSR"]
        payload["metadata"]["is_ciio"] = True
        payload["metadata"]["industry_sector"] = "banking"
        payload["metadata"]["ai_system"] = {
            "is_ai_system": True,
            "risk_tier": "high_risk",
            "prohibited_practices": [],
            "transparency_notice": True,
            "model_card_ref": "docs/model_cards/credit_v2.md",
        }
        payload["data_assets"][0]["data_classification"] = "important"
        payload["data_assets"][0]["financial_data_level"] = "L4"
        payload["mitigations"][0]["control_id"] = "PC-ENC-01"

        model = self._validate(payload)
        self.assertTrue(model.metadata.is_ciio)
        self.assertEqual(model.metadata.industry_sector, IndustrySector.BANKING)
        self.assertIsNotNone(model.metadata.ai_system)
        self.assertEqual(model.metadata.ai_system.risk_tier, AIRiskTier.HIGH_RISK)
        self.assertTrue(model.has_important_or_core_data)
        self.assertEqual(model.data_assets[0].data_classification, DataClassification.IMPORTANT)
        self.assertEqual(model.data_assets[0].financial_data_level, FinancialDataLevel.L4)
        self.assertEqual(model.mitigations[0].control_id, "PC-ENC-01")

    def test_invalid_control_id_rejected(self) -> None:
        payload = copy.deepcopy(self.base_payload)
        payload["mitigations"][0]["control_id"] = "INVALID-99"
        with self.assertRaises(DataFlowValidationError) as ctx:
            self._validate(payload)
        self.assertIn("control_id", str(ctx.exception))

    def test_valid_waiver_and_expiry_check(self) -> None:
        payload = copy.deepcopy(self.base_payload)
        payload["metadata"]["risk_waivers"] = [
            {
                "waiver_id": "waiver_high_01",
                "target_findings": ["LIND-D-inquiry_db"],
                "risk_level": "high",
                "business_justification": "Quarterly migration window required for KMS rollout.",
                "compensating_controls": ["Restricted VPC ingress", "Hourly SIEM alert"],
                "remediation_ticket": "SEC-2026-401",
                "owner": "platform-team",
                "approved_by": "dpo@company.com",
                "approved_at": "2026-01-01",
                "expires_at": "2026-03-15",
            }
        ]
        model = self._validate(payload)
        self.assertEqual(len(model.get_active_waivers(as_of=date(2026, 2, 1))), 1)
        self.assertEqual(len(model.get_active_waivers(as_of=date(2026, 4, 1))), 0)

    def test_waiver_exceeding_max_duration_rejected(self) -> None:
        payload = copy.deepcopy(self.base_payload)
        payload["metadata"]["risk_waivers"] = [
            {
                "waiver_id": "waiver_too_long",
                "target_findings": ["LIND-D-inquiry_db"],
                "risk_level": "critical",
                "business_justification": "Attempting a 60-day critical waiver which violates policy.",
                "compensating_controls": ["Extra logging"],
                "remediation_ticket": "SEC-2026-402",
                "owner": "platform-team",
                "approved_by": "ciso@company.com",
                "approved_at": "2026-01-01",
                "expires_at": "2026-03-02",  # 60 days > 30 day max for critical
            }
        ]
        with self.assertRaises(DataFlowValidationError) as ctx:
            self._validate(payload)
        self.assertIn("maximum 30 days", str(ctx.exception))

    def test_waiver_targeting_red_line_rejected(self) -> None:
        payload = copy.deepcopy(self.base_payload)
        payload["metadata"]["risk_waivers"] = [
            {
                "waiver_id": "waiver_rl_illegal",
                "target_findings": ["RL-01"],
                "risk_level": "high",
                "business_justification": "Illegal attempt to waive EU AI Act Art. 5 red line.",
                "compensating_controls": ["None"],
                "remediation_ticket": "SEC-2026-403",
                "owner": "ai-team",
                "approved_by": "dpo@company.com",
                "approved_at": "2026-01-01",
                "expires_at": "2026-02-01",
            }
        ]
        with self.assertRaises(DataFlowValidationError) as ctx:
            self._validate(payload)
        self.assertIn("RL-01", str(ctx.exception))

    def test_non_personal_important_data_still_triggers_cross_border(self) -> None:
        payload = copy.deepcopy(self.base_payload)
        payload["data_assets"][0]["categories"] = ["non_personal"]
        payload["data_assets"][0]["data_classification"] = "important"
        payload["entities"][0]["region"] = "US"
        model = self._validate(payload)
        self.assertFalse(model.data_assets[0].is_personal_data)
        self.assertTrue(model.data_assets[0].is_important_or_core)
        self.assertEqual([f.id for f in model.get_cross_border_flows()], ["flow_submit_inquiry"])


if __name__ == "__main__":
    unittest.main()
