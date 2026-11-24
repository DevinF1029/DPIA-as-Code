"""API tests for the FastAPI Governance Workbench (`src/dpia_as_code/web/api.py`)."""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

import httpx

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from dpia_as_code.web.api import app


class TestWebWorkbenchAPI(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self) -> None:
        transport = httpx.ASGITransport(app=app)
        self.client = httpx.AsyncClient(transport=transport, base_url="http://test")

    async def asyncTearDown(self) -> None:
        await self.client.aclose()

    async def test_index_and_static_assets(self) -> None:
        res = await self.client.get("/")
        self.assertEqual(res.status_code, 200)
        self.assertIn("DPIA-as-Code", res.text)

        js_res = await self.client.get("/static/app.js")
        self.assertEqual(js_res.status_code, 200)
        self.assertIn("function workbench()", js_res.text)

    async def test_meta_endpoint(self) -> None:
        res = await self.client.get("/api/meta")
        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertEqual(len(data["controls"]), 25)
        self.assertEqual(len(data["red_lines"]), 5)
        example_ids = {e["id"] for e in data["examples"]}
        self.assertIn("banking_retail_credit_ai", example_ids)
        self.assertIn("facial_recognition_kyc", example_ids)
        self.assertIn("static_marketing_site", example_ids)

    async def test_load_example_assess_and_export_yaml_roundtrip(self) -> None:
        ex_res = await self.client.get("/api/examples/banking_retail_credit_ai")
        self.assertEqual(ex_res.status_code, 200)
        spec = ex_res.json()["spec"]

        assess_res = await self.client.post("/api/assess", json={"spec": spec})
        self.assertEqual(assess_res.status_code, 200)
        payload = assess_res.json()
        self.assertEqual(payload["report"]["gate"]["status"], "warn")
        self.assertTrue(payload["report"]["threshold"]["fria_required"])
        self.assertTrue(payload["report"]["threshold"]["important_data_assessment_required"])
        self.assertIn("flowchart LR", payload["report"]["mermaid_dfd"])
        self.assertIn("综合隐私、数据安全与 AI 影响评估报告", payload["markdown"])
        self.assertGreaterEqual(len(payload["default_remediations"]), 1)
        self.assertEqual(len(payload["default_signoffs"]), 3)

        # Verify human review sheet supplements compile directly into final Markdown
        review_payload = {
            "assessment_id": "DPIA-20261122-BANK01",
            "business_owner": "零售金融总部 / 张明",
            "lawful_basis_rationale": "已全部核验单独同意与合同必需。",
            "necessity_proportionality": "仅保留必要风控衍生指标。",
            "data_subject_rights_sla": "15 个工作日内闭环响应。",
            "fria_affected_groups": "成年个人信贷客户。",
            "fria_fairness_bias": "跨群体偏差小于 2%。",
            "fria_human_oversight": "具备 7x24 人工复核与一键中止。",
            "important_data_impact": "重要数据境内专网闭环存储。",
            "important_data_filing_ref": "IMP-2026-009",
            "remediations": payload["default_remediations"],
            "signoffs": payload["default_signoffs"],
        }
        enriched_res = await self.client.post(
            "/api/assess", json={"spec": spec, "review": review_payload}
        )
        self.assertEqual(enriched_res.status_code, 200)
        enriched_md = enriched_res.json()["markdown"]
        self.assertIn("DPIA-20261122-BANK01", enriched_md)
        self.assertIn("零售金融总部 / 张明", enriched_md)
        self.assertIn("跨群体偏差小于 2%", enriched_md)
        self.assertIn("IMP-2026-009", enriched_md)
        self.assertIn("6.2 整改追踪与行动计划", enriched_md)
        self.assertNotIn("<请", enriched_md)

        export_res = await self.client.post("/api/export-yaml", json={"spec": spec})
        self.assertEqual(export_res.status_code, 200)
        yaml_text = export_res.json()["yaml_text"]
        self.assertIn("bank-retail-ai-credit", yaml_text)

        parse_res = await self.client.post("/api/parse-yaml", json={"yaml_text": yaml_text})
        self.assertEqual(parse_res.status_code, 200)
        self.assertEqual(parse_res.json()["spec"]["metadata"]["system_id"], "bank-retail-ai-credit")

    async def test_kyc_example_blocks_via_api(self) -> None:
        spec = (await self.client.get("/api/examples/facial_recognition_kyc")).json()["spec"]
        res = await self.client.post("/api/assess", json={"spec": spec})
        self.assertEqual(res.status_code, 200)
        gate = res.json()["report"]["gate"]
        self.assertEqual(gate["status"], "block")
        self.assertEqual(gate["exit_code"], 1)
        rl_ids = {v["red_line_id"] for v in gate["red_line_violations"]}
        self.assertIn("RL-03", rl_ids)
        self.assertIn("RL-05", rl_ids)

    async def test_invalid_spec_returns_422_with_errors(self) -> None:
        res = await self.client.post("/api/assess", json={"spec": {"metadata": {}}})
        self.assertEqual(res.status_code, 422)
        body = res.json()
        self.assertIn("errors", body)
        self.assertTrue(len(body["errors"]) > 0)


if __name__ == "__main__":
    unittest.main()
