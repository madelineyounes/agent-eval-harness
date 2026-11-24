import json
import runpy
import tempfile
import unittest
from pathlib import Path


class SearchCalibrationTests(unittest.TestCase):
    def test_selects_only_labeled_searches_and_joins_the_recorded_result(self):
        measure = runpy.run_path("examples/calibration-v1/measure_search_steps.py")
        call = {"id": "search-id", "function": {"name": "search", "arguments": json.dumps({"query": "Sydney trains"})}}
        row = {"total_index": 4, "step_labels": {"0": 1, "3": 0}, "messages": [
            {"role": "assistant", "tool_calls": [call]},
            {"role": "tool", "tool_call_id": "wrong-id", "content": "Sydney trains"},
            {"role": "tool", "tool_call_id": "search-id", "content": "Sydney buses"},
            {"role": "assistant", "tool_calls": [call]},
        ]}
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "test.jsonl"
            path.write_text(json.dumps(row) + "\n", encoding="utf-8")
            self.assertEqual(list(measure["observations"](path, "development", "search-test")), [{
                "id": "search-test:4:0", "split": "development", "scenario_family": "search-test", "label": "pass", "score": 0.5,
            }])
