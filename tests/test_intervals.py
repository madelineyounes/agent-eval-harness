import unittest

from agent_eval.intervals import judge_interval, suite_interval


class IntervalTests(unittest.TestCase):
    def test_fixed_judge_interval_is_seeded_and_requires_ten_repeats(self):
        small = judge_interval([0.5] * 9)
        self.assertIsNone(small["bounds"])
        self.assertEqual(small["sample_size"], 9)
        scores = [0.25, 0.75] * 5
        interval = judge_interval(scores)
        self.assertEqual(interval, judge_interval(scores))
        self.assertEqual(interval["sampled_unit"], "judge_repeat")
        self.assertLess(interval["bounds"][0], 0.5)
        self.assertGreater(interval["bounds"][1], 0.5)

    def test_suite_resampling_keeps_group_mix_and_rejects_related_cases(self):
        cases = [
            {"group": "main" if index < 15 else "edge", "scenario_family": f"family-{index}",
             "metrics": {"judge": {"status": "pass", "score": int(index < 15)}}}
            for index in range(20)
        ]
        result = suite_interval(cases, "judge", "independent")
        self.assertEqual(result["bounds"], [0.75, 0.75])
        self.assertEqual(result["sampled_unit"], "case")
        self.assertIsNone(suite_interval(cases, "judge", None)["bounds"])
        self.assertIsNone(suite_interval(cases[:-1], "judge", "independent")["bounds"])
        cases[0]["scenario_family"] = cases[-1]["scenario_family"]
        self.assertIn("scenario family", suite_interval(cases, "judge", "independent")["reason"])
