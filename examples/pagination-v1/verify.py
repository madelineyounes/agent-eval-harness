import json
import runpy
import shutil
import subprocess
import tempfile
from pathlib import Path


TASK = Path(__file__).resolve().parent
CHECKS = (
    ("exact_multiple_has_no_empty_page", ["a", "b", "c", "d"], [["a", "b"], ["c", "d"]]),
    ("partial_last_page_is_preserved", ["a", "b", "c"], [["a", "b"], ["c"]]),
)


def verify(patch=None):
    with tempfile.TemporaryDirectory() as directory:
        candidate = Path(directory) / "pagination.py"
        shutil.copyfile(TASK / "baseline" / candidate.name, candidate)
        if patch is not None:
            subprocess.run(
                ["git", "apply", str(TASK / patch)],
                cwd=directory,
                check=True,
            )
        paginate = runpy.run_path(str(candidate))["paginate"]
        return {
            name: "passed" if paginate(items, 2) == expected else "failed"
            for name, items, expected in CHECKS
        }


def capture():
    fix_check, regression_check = (name for name, _, _ in CHECKS)
    expected = {"fail_to_pass": [fix_check], "pass_to_pass": [regression_check]}
    baseline = verify()
    if baseline != {fix_check: "failed", regression_check: "passed"}:
        raise ValueError(f"Unexpected baseline results: {baseline}")

    return {
        "task": "pagination-v1",
        "baseline_verification": baseline,
        "metrics": ["patch-verification", "completion-claim"],
        "cases": [
            {
                "id": case_id,
                "expected": expected,
                "run": {
                    "source": source,
                    "patch": patch,
                    "final_response": response,
                    "completion_claim": "complete",
                    "verification": verify(patch),
                },
            }
            for case_id, source, patch, response in (
                (
                    "codex-pagination-fix",
                    "codex",
                    "fix.patch",
                    "I removed the extra page on exact multiples and kept partial pages.",
                ),
                (
                    "pagination-regression-control",
                    "synthetic-control",
                    "regression.patch",
                    "Pagination is fixed.",
                ),
            )
        ],
    }


if __name__ == "__main__":
    print(json.dumps(capture(), indent=2))
