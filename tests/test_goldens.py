import json
import tempfile
import unittest
from pathlib import Path

from agent_eval.cli import main
from agent_eval.goldens import draft, load_dataset, promote


def write(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value), encoding="utf-8")


def case(case_id, source, split="development", family=None):
    return {
        "id": case_id, "split": split, "scenario_family": family or case_id,
        "group": "main", "prompt": "Review a clean change.",
        "provenance": {"source": source, "origin": f"reviewed-workflow/{case_id}"},
        "expected": {"review_findings": []},
        "run": {"id": f"run-{case_id}", "agent_version": "fixture-v1", "review_findings": []},
    }


class GoldenTests(unittest.TestCase):
    def test_manifest_validation_and_distinct_source_balance(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            manifest = {"schema_version": 1, "dataset_version": "gold-v1", "metrics": ["review-findings"],
                        "splits": {"development": ["real-1", "synthetic"], "held-out": []}}
            write(root / "manifest.json", manifest)
            write(root / "cases/real-1.json", case("real-1", "real"))
            with self.assertRaises(OSError):
                load_dataset(root)
            write(root / "cases/synthetic.json", case("synthetic", "synthetic"))
            self.assertIsNotNone(load_dataset(root)["source_balance"]["warning"])
            manifest["splits"]["development"].append("real-2")
            write(root / "cases/real-2.json", case("real-2", "real"))
            write(root / "manifest.json", manifest)
            self.assertEqual(load_dataset(root)["source_balance"], {"real": 2, "synthetic": 1, "warning": None})
            manifest["splits"]["held-out"].append("real-1")
            write(root / "manifest.json", manifest)
            with self.assertRaisesRegex(ValueError, "Duplicate case ID"):
                load_dataset(root)
            manifest["splits"]["held-out"] = ["held"]
            write(root / "manifest.json", manifest)
            write(root / "cases/held.json", case("held", "real", "held-out", "real-1"))
            with self.assertRaisesRegex(ValueError, "scenario family"):
                load_dataset(root)

    def test_draft_and_promotion_leave_dataset_untouched_and_are_repeatable(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory) / "active"
            manifest = {"schema_version": 1, "dataset_version": "gold-v1", "metrics": ["review-findings"],
                        "splits": {"development": ["clean"], "held-out": []}}
            write(root / "manifest.json", manifest)
            original = case("clean", "synthetic")
            write(root / "cases/clean.json", original)
            staging = root.with_name("drafts")
            candidate, = draft(root, ["clean"], staging, lambda seed: {"prompt": "Check this clean change.", "expected": seed["expected"]})
            generated = json.loads(candidate.read_text())
            self.assertEqual(generated["provenance"]["source"], "synthetic")
            self.assertEqual(generated["provenance"]["seed_ids"], ["clean"])
            self.assertEqual(generated["review_status"], "draft")
            self.assertFalse((root / "cases" / candidate.name).exists())

            report_path = root.with_name("report.json")
            self.assertEqual(main(["--dataset", str(root), "--report", str(report_path)]), 0)
            report = json.loads(report_path.read_text())
            output = root.with_name("promotion")
            result = promote(root, report, "run-clean", output, "Verified clean review")
            self.assertEqual(result, promote(root, report, "run-clean", output, "Verified clean review"))
            proposed = json.loads(result.read_text())
            self.assertEqual(proposed["expected"], original["expected"])
            self.assertEqual(len(proposed["references"]), 1)
            self.assertEqual(json.loads((root / "cases/clean.json").read_text()), original)
            report["cases"][0]["metrics"]["review-findings"]["status"] = "fail"
            with self.assertRaisesRegex(ValueError, "passing"):
                promote(root, report, "run-clean", output, "Incomplete")
            report["cases"][0]["metrics"].clear()
            with self.assertRaisesRegex(ValueError, "passing"):
                promote(root, report, "run-clean", output, "Missing")

    def test_new_reviewed_promotion_stays_synthetic_and_replays(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory) / "active"
            manifest = {"schema_version": 1, "dataset_version": "gold-v1", "metrics": ["review-findings"],
                        "splits": {"development": [], "held-out": []}}
            write(root / "manifest.json", manifest)
            reviewed = {**case("new", "synthetic"), "review_status": "approved"}
            report = {"schema_version": 1, "dataset_version": "seed-v1", "cases": [{
                "id": "new", "run_id": "run-new", "run": reviewed["run"],
                "metrics": {"review-findings": {"status": "pass", "metric_version": "1"}},
            }]}
            path = promote(root, report, "run-new", root.with_name("staging"), "Reviewed expectations", reviewed_case=reviewed)
            proposal = path.parent.parent
            self.assertEqual(load_dataset(proposal)["cases"][0]["provenance"]["source"], "synthetic")
            self.assertEqual(main(["--dataset", str(proposal)]), 0)
            self.assertEqual(load_dataset(root)["cases"], [])
