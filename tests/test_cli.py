import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


class ReplayCliTests(unittest.TestCase):
    def run_suite(self, case):
        with tempfile.TemporaryDirectory() as directory:
            suite = Path(directory) / "suite.json"
            report = Path(directory) / "report.json"
            suite.write_text(json.dumps({"cases": [case]}), encoding="utf-8")
            process = subprocess.run(
                [
                    sys.executable, "-m", "agent_eval", "--suite", str(suite),
                    "--metric", "review-findings", "--report", str(report),
                ],
                capture_output=True,
                text=True,
                check=False,
            )
            output = json.loads(report.read_text(encoding="utf-8")) if report.exists() else None
            return process, output

    def test_reports_missed_finding_and_returns_evaluation_failure(self):
        process, report = self.run_suite({
            "id": "missed-review",
            "expected": {"review_findings": [["app.py", "lookup", "wrong-default"]]},
            "run": {"review_findings": []},
        })

        self.assertEqual(process.returncode, 1, process.stderr)
        self.assertEqual(report["status"], "fail")
        self.assertEqual(report["cases"][0]["metrics"]["review-findings"]["details"]["false_negatives"], 1)

    def test_reports_invalid_capture_as_execution_error(self):
        process, report = self.run_suite({
            "id": "invalid-review",
            "expected": {"review_findings": []},
            "run": {},
        })

        self.assertEqual(process.returncode, 2, process.stderr)
        self.assertEqual(report["cases"][0]["metrics"]["review-findings"]["status"], "error")

    def test_rejects_report_paths_that_reference_the_suite(self):
        suite_contents = Path("datasets/smoke/review.json").read_bytes()
        for report_name in ("suite.json", "alias.json"):
            with self.subTest(report=report_name), tempfile.TemporaryDirectory() as directory:
                suite = Path(directory) / "suite.json"
                suite.write_bytes(suite_contents)
                report = suite.with_name(report_name)
                if report != suite:
                    os.link(suite, report)

                process = subprocess.run(
                    [sys.executable, "-m", "agent_eval", "--suite", str(suite), "--report", str(report)],
                    capture_output=True,
                    text=True,
                    check=False,
                )

                self.assertEqual(process.returncode, 2, process.stderr)
                self.assertIn("Report path refers to the input suite", process.stderr)
                self.assertEqual(suite.read_bytes(), suite_contents)
