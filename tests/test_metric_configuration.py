import io
import json
import os
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path
from unittest.mock import patch

from agent_eval.cli import main


class MetricConfigurationTests(unittest.TestCase):
    def test_listing_reports_types_and_modes(self):
        with redirect_stdout(io.StringIO()) as output:
            self.assertEqual(main(["--list-metrics"]), 0)
        self.assertIn("review-findings\tdeterministic\treplay, live", output.getvalue())
        self.assertIn("trajectory-quality\tllm-judge\tlive", output.getvalue())

    def test_yaml_defaults_change_deterministic_results(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            definitions = root / "metrics"
            definitions.mkdir()
            config = definitions / "budget.yaml"
            suite = root / "suite.json"
            report = root / "report.json"
            suite.write_text(json.dumps({"metrics": ["custom-budget"], "cases": [{
                "id": "observed", "expected": {}, "run": {"telemetry": {"tool_calls": 2}},
            }]}), encoding="utf-8")
            args = ["--metrics-dir", str(definitions), "--suite", str(suite), "--report", str(report)]
            for limit, code in ((1, 1), (2, 0)):
                config.write_text(
                    "id: custom-budget\ntype: deterministic\nversion: demo-v1\n"
                    f"evaluator: execution-budget\nexpected:\n  budgets:\n    tool_calls: {limit}\n", encoding="utf-8",
                )
                self.assertEqual(main(args), code)
                result = json.loads(report.read_text())["cases"][0]["metrics"]["custom-budget"]
                self.assertEqual((result["metric_type"], result["metric_version"]), ("deterministic", "demo-v1"))

    def test_custom_judge_uses_yaml_rubric_model_and_threshold(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            definitions = root / "metrics"
            definitions.mkdir()
            (definitions / "judge.yaml").write_text(
                "id: careful-review\ntype: llm-judge\nversion: judge-v2\nprovider: openai\n"
                "model: fixture-model\nthreshold: 0.8\nrubric_version: edited-v2\nrubric: |\n  Inspect the cited evidence.\n",
                encoding="utf-8",
            )
            suite = root / "suite.json"
            report = root / "report.json"
            suite.write_text(json.dumps({"metrics": ["careful-review"], "cases": [{
                "id": "observed", "expected": {}, "run": {"final_response": "Done", "tool_calls": []},
            }]}), encoding="utf-8")
            args = ["--metrics-dir", str(definitions), "--suite", str(suite), "--report", str(report)]
            self.assertEqual(main(args), 2)

            def response(request, timeout):
                payload = json.loads(request.data)
                self.assertIn("Inspect the cited evidence.", payload["instructions"])
                self.assertEqual(payload["model"], "fixture-model")
                grade = json.dumps({"score": 0.75, "reason": "Partial support"})
                return io.BytesIO(json.dumps({"status": "completed", "output": [{"type": "message", "content": [
                    {"type": "output_text", "text": grade},
                ]}]}).encode())

            with patch.dict(os.environ, {"OPENAI_API_KEY": "test-key"}), patch("agent_eval.judge_providers.urlopen", response):
                self.assertEqual(main([*args, "--mode", "live"]), 1)
            result = json.loads(report.read_text())["cases"][0]["metrics"]["careful-review"]
            self.assertEqual((result["metric_type"], result["rubric_version"], result["threshold"]),
                             ("llm-judge", "edited-v2", 0.8))
