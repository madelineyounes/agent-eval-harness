import argparse
import json
import sys
from pathlib import Path

from agent_eval.metrics import change_scope, completion_claim, patch_verification, review_findings, verifier_integrity


METRICS = {
    "review-findings": review_findings.evaluate,
    "patch-verification": patch_verification.evaluate,
    "completion-claim": completion_claim.evaluate,
    "change-scope": change_scope.evaluate,
    "verifier-integrity": verifier_integrity.evaluate,
}
EXIT_CODES = {"pass": 0, "fail": 1, "error": 2}


def evaluate_suite(suite, selected_metrics, report):
    if not isinstance(suite, dict):
        raise ValueError("Suite must be a JSON object")
    cases = suite.get("cases")
    metrics = selected_metrics or suite.get("metrics")
    if not isinstance(cases, list) or not cases:
        raise ValueError("Suite must contain at least one case")
    if not isinstance(metrics, list) or not metrics:
        raise ValueError("Select at least one metric")
    for metric in metrics:
        if not isinstance(metric, str) or metric not in METRICS:
            raise ValueError(f"Unknown metric {metric!r}")

    report["selected_metrics"] = list(dict.fromkeys(metrics))
    seen_cases = set()
    for case in cases:
        if not isinstance(case, dict):
            raise ValueError("Each case must be a JSON object")
        case_id = case.get("id")
        if not isinstance(case_id, str) or not case_id.strip() or case_id in seen_cases:
            raise ValueError("Each case needs a unique, nonempty ID")
        seen_cases.add(case_id)
        expected = case.get("expected")
        run = case.get("run")
        if not isinstance(expected, dict) or not isinstance(run, dict):
            raise ValueError(f"{case_id} requires expected and run objects")

        results = {}
        report["cases"].append({"id": case_id, "metrics": results})
        for metric in report["selected_metrics"]:
            try:
                result = METRICS[metric](expected, run)
            except ValueError as error:
                result = {"status": "error", "reason": str(error)}
            results[metric] = result
            if EXIT_CODES[result["status"]] > EXIT_CODES[report["status"]]:
                report["status"] = result["status"]


def main(argv=None):
    parser = argparse.ArgumentParser(description="Evaluate captured coding-agent and PR review runs.")
    parser.add_argument("--list-metrics", action="store_true", help="List metric IDs and exit.")
    parser.add_argument("--suite", type=Path, help="Path to a JSON replay suite.")
    parser.add_argument("--metric", action="append", help="Select a metric, replacing suite defaults. Repeat for multiple metrics.")
    parser.add_argument("--report", type=Path, help="Write the evaluation report as JSON.")
    args = parser.parse_args(argv)
    if args.list_metrics:
        print("\n".join(METRICS))
        return 0
    if args.suite is None:
        parser.error("--suite is required unless --list-metrics is used")

    report = {"schema_version": 1, "mode": "replay", "status": "pass", "cases": []}
    try:
        suite = json.loads(args.suite.read_text(encoding="utf-8"))
        evaluate_suite(suite, args.metric, report)
    except (OSError, ValueError) as error:
        report.update(status="error", reason=str(error))

    if args.report is not None:
        try:
            if args.report.exists() and args.suite.exists() and args.report.samefile(args.suite):
                print("Report path refers to the input suite", file=sys.stderr)
                return 2
            args.report.parent.mkdir(parents=True, exist_ok=True)
            args.report.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
        except OSError as error:
            print(f"Could not write report: {error}", file=sys.stderr)
            return 2

    if "reason" in report:
        print(report["reason"], file=sys.stderr)
    for case in report["cases"]:
        for metric, result in case["metrics"].items():
            print(f"{case['id']} | {metric} | {result['status']} | {result['reason']}")
    return EXIT_CODES[report["status"]]
