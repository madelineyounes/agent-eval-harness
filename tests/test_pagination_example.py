import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


class PaginationExampleTests(unittest.TestCase):
    def test_replays_the_captured_fix_and_regression(self):
        task = Path("examples/pagination-v1")
        suite = task / "capture.json"
        generated = subprocess.check_output([sys.executable, str(task / "verify.py")])
        self.assertEqual(json.loads(generated), json.loads(suite.read_bytes()))

        with tempfile.TemporaryDirectory() as directory:
            report_path = Path(directory) / "report.json"
            replay = subprocess.run(
                [sys.executable, "-m", "agent_eval", "--suite", str(suite), "--report", str(report_path)],
                capture_output=True,
                text=True,
            )
            self.assertEqual(replay.returncode, 1, replay.stderr)
            results = json.loads(report_path.read_text(encoding="utf-8"))["cases"]

        metrics_by_case = {case["id"]: case["metrics"] for case in results}
        self.assertEqual(
            {
                case_id: {name: result["status"] for name, result in metrics.items()}
                for case_id, metrics in metrics_by_case.items()
            },
            {
                "codex-pagination-fix": {"patch-verification": "pass", "completion-claim": "pass"},
                "pagination-regression-control": {"patch-verification": "fail", "completion-claim": "fail"},
            },
        )
        regression_metrics = metrics_by_case["pagination-regression-control"]
        checks = regression_metrics["patch-verification"]["details"]
        self.assertEqual(checks["fix_checks"]["passed"], ["exact_multiple_has_no_empty_page"])
        self.assertEqual(checks["regression_checks"]["failed"], ["partial_last_page_is_preserved"])
