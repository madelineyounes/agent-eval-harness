import json
import tempfile
import unittest
from pathlib import Path

from agent_eval.calibration import calibrate, draft_metric
from agent_eval.metric_config import load_metrics


class CalibrationTests(unittest.TestCase):
    def test_draft_writes_reviewable_files_outside_registry(self):
        with tempfile.TemporaryDirectory() as directory:
            before = load_metrics()
            seen = []

            def generator(metric_id, behavior, tool):
                seen.append((metric_id, behavior, tool))
                return {"metric.py": "def evaluate(expected, run):\n    raise NotImplementedError\n",
                        "test_metric.py": "import unittest\n", "rubric.md": "# Review this rubric\n"}

            draft = draft_metric(Path(directory), "lookup-required", "Look up the catalog", "lookup", generator)
            self.assertEqual(seen, [("lookup-required", "Look up the catalog", "lookup")])
            self.assertEqual({path.name for path in draft.iterdir()}, {"metric.py", "test_metric.py", "rubric.md"})
            self.assertEqual(load_metrics(), before)
            self.assertNotIn("lookup-required", before)

    def test_selects_threshold_on_development_and_reports_both_held_out_errors(self):
        fixture = json.loads(Path("examples/calibration-v1/scores.json").read_text())
        report = calibrate(fixture)
        self.assertEqual(report["threshold"], 0.75)
        self.assertEqual(report["development"]["agreement"], 1)
        self.assertEqual(report["held-out"]["false_passes"], ["held-false-pass"])
        self.assertEqual(report["held-out"]["false_failures"], ["held-false-fail"])
        fixture["cases"][-1]["scenario_family"] = fixture["cases"][0]["scenario_family"]
        with self.assertRaisesRegex(ValueError, "scenario family"):
            calibrate(fixture)
