import io
import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from agent_eval.cli import main


class LiveJudgeTests(unittest.TestCase):
    def test_live_cli_scores_saved_run_twice_and_keeps_usage_separate(self):
        with tempfile.TemporaryDirectory() as directory:
            suite, saved, report = (Path(directory) / name for name in ("suite.json", "saved.json", "report.json"))
            suite.write_text(json.dumps({"dataset_version": "v1", "cases": [{"id": "case", "expected": {}}]}))
            run = {"id": "observed", "final_response": "Supported claim", "tool_calls": [], "telemetry": {"input_tokens": 2}}
            saved.write_text(json.dumps({"schema_version": 1, "dataset_version": "v1", "cases": [{"id": "case", "run": run}]}))
            requests = []

            def response(request, timeout):
                requests.append(json.loads(request.data))
                grade = json.dumps({"score": 0.75, "reason": "Evidence supports most of the claim."})
                return io.BytesIO(json.dumps({
                    "status": "completed", "output": [{"type": "message", "content": [{"type": "output_text", "text": grade}]}],
                    "usage": {"input_tokens": 10, "output_tokens": 4},
                }).encode())

            args = ["--suite", str(suite), "--run-file", str(saved), "--report", str(report), "--mode", "live",
                    "--metric", "trajectory-quality", "--judge-model", "fake", "--judge-threshold", "0.5", "--repeats", "2"]
            with patch.dict(os.environ, {"OPENAI_API_KEY": "test-key"}), patch("agent_eval.judge_providers.urlopen", response):
                self.assertEqual(main(args), 0)
                self.assertEqual(len(requests), 2)
                self.assertEqual(requests[0], requests[1])
                case = json.loads(report.read_text())["cases"][0]
                self.assertEqual(case["run"], run)
                result = case["metrics"]["trajectory-quality"]
                self.assertEqual(result["repeats"][0]["usage"]["input_tokens"], 10)
                self.assertEqual(result["score"], 0.75)

                saved.write_text(json.dumps({"schema_version": 1, "dataset_version": "wrong", "cases": []}))
                self.assertEqual(main(args), 2)
                self.assertIn("dataset_version", json.loads(report.read_text())["reason"])
