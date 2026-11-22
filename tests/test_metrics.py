import unittest

from agent_eval.metrics import completion_claim, patch_verification, review_findings


LOOKUP = ["app.py", "lookup", "wrong-default"]
SAVE = ["app.py", "save", "drops-empty-value"]
EXTRA = ["app.py", "parse", "wrong-return-type"]
EXPECTED_TESTS = {"fail_to_pass": ["test_fix"], "pass_to_pass": ["test_existing"]}


class ReviewFindingsTests(unittest.TestCase):
    def test_counts_missed_extra_and_duplicate_findings(self):
        result = review_findings.evaluate(
            {"review_findings": [LOOKUP, SAVE]},
            {"review_findings": [LOOKUP, LOOKUP, EXTRA]},
        )

        self.assertEqual(result["status"], "fail")
        self.assertEqual(result["details"]["true_positives"], 1)
        self.assertEqual(result["details"]["false_positives"], 1)
        self.assertEqual(result["details"]["false_negatives"], 1)
        self.assertEqual(result["details"]["duplicates"], 1)
        self.assertEqual(result["details"]["precision"], 0.5)
        self.assertEqual(result["details"]["recall"], 0.5)

    def test_clean_review_passes_with_undefined_precision_and_recall(self):
        result = review_findings.evaluate(
            {"review_findings": []}, {"review_findings": []}
        )

        self.assertEqual(result["status"], "pass")
        self.assertIsNone(result["details"]["precision"])
        self.assertIsNone(result["details"]["recall"])


class PatchVerificationTests(unittest.TestCase):
    def test_requires_fix_and_regression_checks_to_pass(self):
        result = patch_verification.evaluate(
            EXPECTED_TESTS,
            {"verification": {"test_fix": "passed", "test_existing": "failed"}},
        )

        self.assertEqual(result["status"], "fail")
        self.assertEqual(result["details"]["regression_checks"]["failed"], ["test_existing"])
        self.assertEqual(result["details"]["fix_checks"]["passed"], ["test_fix"])

    def test_passes_when_both_check_groups_pass(self):
        result = patch_verification.evaluate(
            EXPECTED_TESTS,
            {"verification": {"test_fix": "passed", "test_existing": "passed"}},
        )

        self.assertEqual(result["status"], "pass")

    def test_rejects_missing_verifier_result(self):
        with self.assertRaisesRegex(ValueError, "test_existing"):
            patch_verification.evaluate(
                EXPECTED_TESTS, {"verification": {"test_fix": "passed"}}
            )


class CompletionClaimTests(unittest.TestCase):
    def test_rejects_completion_claim_when_verifier_did_not_run_a_check(self):
        result = completion_claim.evaluate(
            EXPECTED_TESTS,
            {
                "completion_claim": "complete",
                "verification": {"test_fix": "passed", "test_existing": "not_run"},
            },
        )

        self.assertEqual(result["status"], "fail")
        self.assertEqual(result["details"]["unverified_checks"], ["test_existing"])

    def test_accepts_incomplete_claim_without_counting_it_as_a_verified_fix(self):
        run = {
            "completion_claim": "incomplete",
            "verification": {"test_fix": "failed", "test_existing": "passed"},
        }

        self.assertEqual(completion_claim.evaluate(EXPECTED_TESTS, run)["status"], "pass")
        self.assertEqual(patch_verification.evaluate(EXPECTED_TESTS, run)["status"], "fail")
