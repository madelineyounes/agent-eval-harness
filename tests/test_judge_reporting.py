import unittest

from agent_eval.cli import evaluate_suite
from agent_eval.reporting import summarize


class JudgeReportingTests(unittest.TestCase):
    def evaluate(self, judge):
        run = {"id": "fixed-run", "final_response": "Found it", "tool_calls": []}
        seen = []

        def score(captured):
            seen.append(captured)
            return judge()

        suite = {"dataset_version": "v1", "metrics": ["trajectory-quality"], "cases": [
            {"id": "fixed", "group": "main", "expected": {}, "run": run},
        ]}
        report = {"status": "pass", "cases": []}
        evaluate_suite(suite, None, report, judge=score, judge_model="fake", judge_threshold=0.5, repeats=2)
        self.assertEqual(len(seen), 2)
        self.assertTrue(all(captured is run for captured in seen))
        self.assertEqual(report["dataset_version"], "v1")
        self.assertEqual(report["cases"][0]["run_id"], "fixed-run")
        return report, report["cases"][0]["metrics"]["trajectory-quality"]

    def test_mean_controls_result_for_one_fixed_run(self):
        scores = iter((0.25, 0.75))
        report, result = self.evaluate(lambda: {"score": next(scores), "reason": "Synthetic grade"})
        self.assertEqual((result["status"], result["score"]), ("pass", 0.5))
        self.assertEqual(result["completed_repeats"], 2)
        self.assertEqual(result["requested_repeats"], 2)
        self.assertEqual([repeat["score"] for repeat in result["repeats"]], [0.25, 0.75])
        self.assertEqual(report["summary"]["metrics"]["trajectory-quality"]["edge"]["pass_rate"], None)

    def test_preserves_completed_scores_when_a_repeat_fails(self):
        def scores():
            yield {"score": 0.25, "reason": "One completed grade"}
            raise RuntimeError("Judge unavailable")

        values = scores()
        report, result = self.evaluate(lambda: next(values))
        self.assertEqual((report["status"], result["status"]), ("error", "error"))
        self.assertEqual(result["completed_repeats"], 1)
        self.assertEqual(result["repeats"][0]["score"], 0.25)
        self.assertIn("Judge unavailable", result["repeats"][1]["error"])

    def test_aggregate_uses_one_mean_per_completed_case(self):
        cases = [{"group": group, "metrics": {"judge": result}} for group, result in (
            ("main", {"status": "pass", "score": 0.8, "completed_repeats": 10}),
            ("edge", {"status": "fail", "score": 0.2, "completed_repeats": 2}),
            ("edge", {"status": "error", "completed_repeats": 1}),
        )]
        overall = summarize(cases, ["judge"])["metrics"]["judge"]["overall"]
        self.assertEqual(overall["mean_score"], 0.5)
        self.assertEqual(overall["pass_rate"], 0.5)
        self.assertAlmostEqual(overall["completion_rate"], 2 / 3)
