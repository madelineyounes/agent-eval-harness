import json
import unittest
from pathlib import Path

from agent_eval.cli import evaluate_suite


class OperationsReportTests(unittest.TestCase):
    def test_summarizes_recorded_telemetry_and_missing_data(self):
        suite = json.loads(Path("datasets/demo/operations.json").read_text())
        report = {"status": "pass", "cases": []}
        evaluate_suite(suite, None, report)
        operations = report["summary"]["operations"]
        self.assertEqual(operations["trace_coverage"], {"recorded_cases": 2, "missing_cases": 0, "rate": 1.0})
        self.assertEqual(operations["telemetry"]["tool_calls"], {"total": 5, "observed_cases": 2, "missing_cases": 0})
        self.assertEqual(operations["telemetry"]["input_tokens"], {"total": None, "observed_cases": 0, "missing_cases": 2})
        self.assertEqual(operations["tool_timeouts"]["total"], 4)
        self.assertEqual(operations["loop_cases"], ["lookup-repeats-without-progress"])
        self.assertEqual(operations["failed_cases"], {"lookup-repeats-without-progress": ["execution-budget", "loop-detection"]})
