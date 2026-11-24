"""Unit tests for the `dpia` CLI and Chinese Markdown/JSON/PR-comment renderers."""

from __future__ import annotations

import json
import sys
import unittest
from pathlib import Path

from click.testing import CliRunner

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from dpia_as_code.cli import main


class TestCLI(unittest.TestCase):
    def setUp(self) -> None:
        self.runner = CliRunner()
        self.kyc_path = str(ROOT / "examples" / "facial_recognition_kyc.yaml")
        self.site_path = str(ROOT / "examples" / "static_marketing_site.yaml")

    def test_validate_command(self) -> None:
        res = self.runner.invoke(main, ["validate", self.kyc_path])
        self.assertEqual(res.exit_code, 0, res.output)
        self.assertIn("[OK]", res.output)

    def test_assess_markdown_pass_on_static_site(self) -> None:
        res = self.runner.invoke(main, ["assess", self.site_path, "--format", "md"])
        self.assertEqual(res.exit_code, 0, res.output)
        self.assertIn("综合隐私、数据安全与 AI 影响评估报告", res.output)
        self.assertIn("PASS（自动放行）", res.output)
        self.assertIn("```mermaid", res.output)

    def test_assess_markdown_block_on_kyc(self) -> None:
        res = self.runner.invoke(main, ["assess", self.kyc_path, "--format", "md"])
        self.assertEqual(res.exit_code, 1)
        self.assertIn("BLOCK（阻断合并）", res.output)
        self.assertIn("RL-03", res.output)
        self.assertIn("RL-05", res.output)

    def test_assess_pr_comment_and_json_formats(self) -> None:
        pr_res = self.runner.invoke(
            main, ["assess", self.kyc_path, "--format", "pr-comment", "--no-fail"]
        )
        self.assertEqual(pr_res.exit_code, 0, pr_res.output)
        self.assertIn("DPIA-as-Code 隐私与合规门禁摘要", pr_res.output)

        json_res = self.runner.invoke(
            main, ["assess", self.site_path, "--format", "json"]
        )
        self.assertEqual(json_res.exit_code, 0, json_res.output)
        parsed = json.loads(json_res.output)
        self.assertEqual(parsed["system_id"], "corp-marketing-site")
        self.assertEqual(parsed["gate"]["status"], "pass")


if __name__ == "__main__":
    unittest.main()
