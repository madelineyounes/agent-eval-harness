import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from agent_eval.metrics import tool_call_contract


class DocsExampleTests(unittest.TestCase):
    def test_contract_reports_wrong_order_and_forbidden_calls(self):
        first = {"tool": "lookup_doc", "arguments": {"id": "primary"}}
        second = {"tool": "lookup_doc", "arguments": {"id": "related"}}
        forbidden = {"tool": "update_doc", "arguments": {}}
        result = tool_call_contract.evaluate(
            {"required_calls": [first, second], "ordered_calls": True, "forbidden_tools": ["update_doc"]},
            {"tool_calls": [second, first, forbidden]},
        )
        self.assertEqual(result["status"], "fail")
        self.assertEqual(result["details"], {"missing_calls": [], "forbidden_call_steps": [3], "out_of_order": True})

    def test_live_capture_records_success_missing_and_timeout(self):
        with tempfile.TemporaryDirectory() as directory:
            report = Path(directory) / "report.json"
            process = subprocess.run([
                sys.executable, "-m", "agent_eval", "--suite", "datasets/smoke/docs.json", "--mode", "live",
                "--adapter", "mock-docs", "--report", str(report),
            ], capture_output=True, text=True)
            self.assertEqual(process.returncode, 0, process.stderr)
            cases = json.loads(report.read_text())["cases"]
            self.assertEqual([case["run"]["tool_calls"][0]["result"]["status"] for case in cases],
                             ["success", "missing", "timeout"])
            self.assertEqual(len({case["run_id"] for case in cases}), 3)

    def test_correct_replayed_answer_with_skipped_lookup_fails_the_contract(self):
        with tempfile.TemporaryDirectory() as directory:
            report = Path(directory) / "report.json"
            command = [sys.executable, "-m", "agent_eval", "--suite", "datasets/demo/skipped-lookup.json", "--report", str(report)]
            for metric, exit_code in (("response-expectations", 0), ("tool-call-contract", 1), (None, 1)):
                with self.subTest(metric=metric):
                    process = subprocess.run(command + (["--metric", metric] if metric else []), capture_output=True, text=True)
                    self.assertEqual(process.returncode, exit_code, process.stderr)
            results = json.loads(report.read_text())["cases"][0]["metrics"]
            self.assertEqual(results["tool-call-contract"]["details"]["missing_calls"], [
                {"tool": "lookup_doc", "arguments": {"id": "returns"}},
            ])
