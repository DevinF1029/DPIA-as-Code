"""API tests for the FastAPI Governance Workbench (`src/dpia_as_code/web/api.py`)."""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

import httpx

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from dpia_as_code.web.api import app  # noqa: E402


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
