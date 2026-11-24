import unittest

from agent_eval.metrics import execution_budget, loop_detection


class OperationalMetricTests(unittest.TestCase):
    def test_budget_accepts_exact_limit_and_reports_overage(self):
        expected = {"budgets": {"input_tokens": 20}}
        self.assertEqual(execution_budget.evaluate(expected, {"telemetry": {"input_tokens": 20}})["status"], "pass")
        result = execution_budget.evaluate(expected, {"telemetry": {"input_tokens": 21}})
        self.assertEqual(result["status"], "fail")
        self.assertEqual(result["details"]["breaches"], {"input_tokens": {"limit": 20, "observed": 21}})
        for telemetry in ({}, {"input_tokens": None}, {"input_tokens": True}):
            with self.subTest(telemetry=telemetry), self.assertRaisesRegex(ValueError, "input_tokens"):
                execution_budget.evaluate(expected, {"telemetry": telemetry})

    def test_loop_counts_retries_after_first_call_and_resets_on_progress(self):
        expected = {"allowed_identical_retries": 1}
        timeout = {"tool": "lookup", "arguments": {"id": "item"}, "result": {"status": "timeout"}}
        success = {**timeout, "result": {"status": "success"}}
        other = {**timeout, "arguments": {"id": "other"}}
        for calls in ([timeout, timeout], [timeout, timeout, success], [timeout, timeout, other, timeout]):
            with self.subTest(calls=calls):
                self.assertEqual(loop_detection.evaluate(expected, {"tool_calls": calls})["status"], "pass")
        result = loop_detection.evaluate(expected, {"tool_calls": [timeout, timeout, timeout]})
        self.assertEqual(result["status"], "fail")
        self.assertEqual(result["details"]["loops"], [
            {"first_call": 1, "tool": "lookup", "arguments": {"id": "item"}, "retries": 2},
        ])
        with self.assertRaises(ValueError):
            loop_detection.evaluate(expected, {"tool_calls": [{"tool": "lookup", "arguments": {}}]})
