import json
import tempfile
import unittest
from pathlib import Path

from agent_eval.cli import main
from agent_eval.harbor_import import import_trial


EXAMPLE = Path("examples/harbor-v1")


class HarborImportTests(unittest.TestCase):
    def test_import_replay_and_promote_saved_trial(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            suite, report = root / "suite.json", root / "report.json"
            dataset = EXAMPLE / "dataset"
            self.assertEqual(main([
                "import-harbor", "--trial", str(EXAMPLE / "saved-trial"), "--dataset", str(dataset),
                "--case-id", "hello-file", "--output", str(suite),
            ]), 0)
            source = json.loads((EXAMPLE / "saved-trial/result.json").read_text())
            run = json.loads(suite.read_text())["cases"][0]["run"]
            self.assertEqual(run["id"], source["id"])
            self.assertEqual(run["task_version"], source["task_checksum"])
            self.assertEqual(run["verifier_rewards"], source["verifier_result"]["rewards"])
            self.assertEqual([call["arguments"]["command"] for call in run["tool_calls"]], ["write hello.txt", "read hello.txt"])
            self.assertEqual(run["telemetry"]["tool_calls"], 2)
            self.assertIsNone(run["telemetry"]["input_tokens"])
            self.assertEqual(main(["--suite", str(suite), "--report", str(report)]), 0)
            self.assertEqual(main([
                "promote", "--dataset", str(dataset), "--report", str(report), "--run-id", run["id"],
                "--reason", "Reviewed synthetic verification", "--output", str(root / "proposal"),
            ]), 0)

    def test_missing_verifier_result_is_an_import_error(self):
        trial = EXAMPLE / "saved-trial"
        result = json.loads((trial / "result.json").read_text())
        trajectory = json.loads((trial / "agent/trajectory.json").read_text())
        result["verifier_result"] = None
        with self.assertRaisesRegex(ValueError, "rewards"):
            import_trial(result, trajectory)
