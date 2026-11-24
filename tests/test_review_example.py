import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


class ReviewExampleTests(unittest.TestCase):
    def test_replays_labeled_pr_reviews(self):
        task = Path("examples/review-v1")
        for name, exit_code, status in (("passing", 0, "pass"), ("control", 1, "fail")):
            with self.subTest(suite=name), tempfile.TemporaryDirectory() as directory:
                report_path = Path(directory) / "report.json"
                replay = subprocess.run(
                    [
                        sys.executable, "-m", "agent_eval", "--suite", str(task / f"{name}.json"),
                        "--report", str(report_path),
                    ],
                    capture_output=True,
                    text=True,
                )
                self.assertEqual(replay.returncode, exit_code, replay.stderr)
                report = json.loads(report_path.read_text(encoding="utf-8"))
                self.assertEqual(report["status"], status)
                results = {
                    case["id"]: case["metrics"]["review-findings"] for case in report["cases"]
                }

                if name == "passing":
                    self.assertEqual(
                        {case_id: result["status"] for case_id, result in results.items()},
                        {"clean-catalog-review": "pass", "defective-catalog-review": "pass"},
                    )
                else:
                    self.assertEqual(results.keys(), {"catalog-review-control"})
                    result = results["catalog-review-control"]
                    self.assertEqual(result["status"], "fail")
                    self.assertEqual(result["details"], {
                        "true_positives": 1,
                        "false_positives": 1,
                        "false_negatives": 1,
                        "duplicates": 1,
                        "precision": 0.5,
                        "recall": 0.5,
                        "unexpected": [["catalog.py", "store", "lowercases-keys"]],
                        "missed": [["catalog.py", "has_key", "ignores-present-empty-value"]],
                    })
