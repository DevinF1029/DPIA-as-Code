"""Unit tests for Policy-as-Code YAML rule packs (`rules/*.yaml`) and `rules_loader.py`."""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from dpia_as_code.models import (
    DFDElementType,
    Jurisdiction,
    PETType,
    RedLineId,
)
from dpia_as_code.rules_loader import load_rule_bundle


class TestRulePackBundle(unittest.TestCase):
    def test_load_default_rule_bundle(self) -> None:
        bundle = load_rule_bundle()

        # 1. Red lines (RL-01..RL-05)
        self.assertFalse(bundle.red_lines.waivable)
        rl_ids = {r.id for r in bundle.red_lines.red_lines}
        self.assertEqual(rl_ids, set(RedLineId))

        # 2. Multi-jurisdiction thresholds
        j_rules = bundle.thresholds.jurisdiction_rules
        self.assertEqual(len(j_rules[Jurisdiction.GDPR].criteria), 9)
        self.assertEqual(len(j_rules[Jurisdiction.PIPL].criteria), 5)
        self.assertGreaterEqual(len(j_rules[Jurisdiction.EU_AI_ACT].criteria), 3)
        self.assertGreaterEqual(len(j_rules[Jurisdiction.CN_DSL_NDSR].criteria), 3)
        self.assertGreaterEqual(len(bundle.thresholds.cross_jurisdiction_conflicts), 2)

        # 3. LINDDUN DFD matrix covers all 4 DFD element types
        self.assertEqual(set(bundle.linddun_matrix.dfd_linddun_matrix.keys()), set(DFDElementType))
        self.assertEqual(bundle.linddun_matrix.maturity_discounting.planned.likelihood_factor, 0.0)
        self.assertTrue(bundle.linddun_matrix.maturity_discounting.verified.requires_evidence)
        self.assertEqual(bundle.linddun_matrix.risk_appetite_gate.high.max_waiver_days, 90)
        self.assertEqual(bundle.linddun_matrix.risk_appetite_gate.critical.max_waiver_days, 30)

        # 4. Control catalog (25 controls across 6 domains, including PC-GOV-06)
        controls_by_id = bundle.control_catalog.by_id()
        self.assertEqual(len(controls_by_id), 25)
        self.assertIn("PC-GOV-06", controls_by_id)
        self.assertIn("PC-AI-01", controls_by_id)
        self.assertIn("PC-XBD-02", controls_by_id)

        # Verify PET lookup helper
        enc_controls = bundle.control_catalog.by_pet_type(PETType.ENCRYPTION_AT_REST)
        self.assertEqual([c.id for c in enc_controls], ["PC-ENC-02"])


if __name__ == "__main__":
    unittest.main()
