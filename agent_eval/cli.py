import argparse
import json
import sys
from pathlib import Path

from agent_eval.calibration import calibrate, draft_metric
from agent_eval.captures import use_saved_runs
from agent_eval.goldens import SPLITS, draft, load_dataset, promote, read
from agent_eval.metrics import (
    change_scope,
    completion_claim,
    execution_budget,
    loop_detection,
    patch_verification,
    review_findings,
    trajectory_quality,
    verifier_integrity,
)
from agent_eval.reporting import GROUPS, summarize
from agent_eval.openai_judge import openai_judge


METRICS = {
    "review-findings": review_findings.evaluate,
    "patch-verification": patch_verification.evaluate,
    "completion-claim": completion_claim.evaluate,
    "change-scope": change_scope.evaluate,
    "verifier-integrity": verifier_integrity.evaluate,
    "execution-budget": execution_budget.evaluate,
    "loop-detection": loop_detection.evaluate,
}
EXIT_CODES = {"pass": 0, "fail": 1, "error": 2}
METRIC_IDS = (*METRICS, trajectory_quality.METRIC)


def evaluate_suite(suite, selected_metrics, report, *, judge=None, judge_model=None, judge_threshold=None, repeats=1):
    if not isinstance(suite, dict):
        raise ValueError("Suite must be a JSON object")
    cases = suite.get("cases")
    metrics = selected_metrics or suite.get("metrics")
    if not isinstance(cases, list) or not cases:
        raise ValueError("Suite must contain at least one case")
    if not isinstance(metrics, list) or not metrics:
        raise ValueError("Select at least one metric")
    for metric in metrics:
        if not isinstance(metric, str) or metric not in METRIC_IDS:
            raise ValueError(f"Unknown metric {metric!r}")

    report["selected_metrics"] = list(dict.fromkeys(metrics))
    if "dataset_version" in suite:
        report["dataset_version"] = suite["dataset_version"]
    if "source_balance" in suite:
        report["source_balance"] = suite["source_balance"]
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
        case_result = {"id": case_id, "metrics": results, "run": run}
        if "id" in run:
            case_result["run_id"] = run["id"]
        if case.get("group") in GROUPS:
            case_result["group"] = case["group"]
        if isinstance(case.get("scenario_family"), str) and case["scenario_family"].strip():
            case_result["scenario_family"] = case["scenario_family"]
        report["cases"].append(case_result)
        for metric in report["selected_metrics"]:
            try:
                if metric == trajectory_quality.METRIC:
                    result = trajectory_quality.evaluate(run, judge, judge_model, judge_threshold, repeats)
                else:
                    result = METRICS[metric](expected, run)
            except ValueError as error:
                result = {"status": "error", "reason": str(error)}
            results[metric] = {**result, "metric_version": result.get("rubric_version", "1")}
            if EXIT_CODES[result["status"]] > EXIT_CODES[report["status"]]:
                report["status"] = result["status"]
    report["summary"] = summarize(report["cases"], report["selected_metrics"], suite.get("sampling"))


def golden_command(command, argv):
    parser = argparse.ArgumentParser(prog=f"python -m agent_eval {command}")
    parser.add_argument("--dataset", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    if command == "draft-goldens":
        parser.add_argument("--seed", action="append", required=True)
    else:
        parser.add_argument("--report", type=Path, required=True)
        parser.add_argument("--run-id", required=True)
        parser.add_argument("--reason", required=True)
        parser.add_argument("--reviewed-case", type=Path)
        parser.add_argument("--excerpt-file", type=Path)
    args = parser.parse_args(argv)
    try:
        if command == "draft-goldens":
            paths = draft(args.dataset, args.seed, args.output)
        else:
            paths = [promote(
                args.dataset, read(args.report), args.run_id, args.output, args.reason,
                reviewed_case=read(args.reviewed_case) if args.reviewed_case else None,
                excerpt=read(args.excerpt_file) if args.excerpt_file else None,
            )]
    except (OSError, ValueError) as error:
        print(error, file=sys.stderr)
        return 2
    for path in paths:
        print(path)
    return 0


def calibration_command(command, argv):
    parser = argparse.ArgumentParser(prog=f"python -m agent_eval {command}")
    if command == "draft-metric":
        parser.add_argument("--id", required=True)
        parser.add_argument("--behavior", required=True)
        parser.add_argument("--tool", required=True)
        parser.add_argument("--output", type=Path, required=True)
    else:
        parser.add_argument("--labels", type=Path, required=True)
    args = parser.parse_args(argv)
    try:
        if command == "draft-metric":
            print(draft_metric(args.output, args.id, args.behavior, args.tool))
        else:
            print(json.dumps(calibrate(read(args.labels)), indent=2))
    except (OSError, ValueError) as error:
        print(error, file=sys.stderr)
        return 2
    return 0


def main(argv=None):
    argv = sys.argv[1:] if argv is None else argv
    if argv and argv[0] in ("draft-goldens", "promote"):
        return golden_command(argv[0], argv[1:])
    if argv and argv[0] in ("draft-metric", "calibrate-metric"):
        return calibration_command(argv[0], argv[1:])
    parser = argparse.ArgumentParser(description="Evaluate captured coding-agent and PR review runs.")
    parser.add_argument("--list-metrics", action="store_true", help="List metric IDs and exit.")
    inputs = parser.add_mutually_exclusive_group()
    inputs.add_argument("--suite", type=Path, help="Path to a JSON replay suite.")
    inputs.add_argument("--dataset", type=Path, help="Path to a versioned golden dataset directory.")
    parser.add_argument("--split", choices=SPLITS, help="Select one split of a golden dataset.")
    parser.add_argument("--metric", action="append", help="Select a metric, replacing suite defaults. Repeat for multiple metrics.")
    parser.add_argument("--repeats", type=int, default=1, help="Number of scores to request for each stochastic metric.")
    parser.add_argument("--mode", choices=("replay", "live"), default="replay", help="Enable a live judge in live mode.")
    parser.add_argument("--run-file", type=Path, help="Load fixed runs from a saved evaluation report.")
    parser.add_argument("--judge-model", help="OpenAI model ID for a live trajectory judge.")
    parser.add_argument("--judge-threshold", type=float, help="Minimum mean trajectory judge score to pass.")
    parser.add_argument("--report", type=Path, help="Write the evaluation report as JSON.")
    args = parser.parse_args(argv)
    if args.list_metrics:
        print("\n".join(METRIC_IDS))
        return 0
    if args.suite is None and args.dataset is None:
        parser.error("--suite or --dataset is required unless --list-metrics is used")
    if args.split and args.dataset is None:
        parser.error("--split requires --dataset")
    if args.repeats < 1:
        parser.error("--repeats must be a positive integer")

    report = {"schema_version": 1, "mode": args.mode, "status": "pass", "cases": []}
    try:
        suite = load_dataset(args.dataset, args.split) if args.dataset is not None else read(args.suite)
        if args.run_file is not None:
            suite = use_saved_runs(suite, json.loads(args.run_file.read_text(encoding="utf-8")))
        judge = None
        if isinstance(suite, dict):
            selected = args.metric or suite.get("metrics")
            if isinstance(selected, list) and trajectory_quality.METRIC in selected:
                if args.mode != "live" or not args.judge_model or args.judge_threshold is None:
                    raise ValueError("trajectory-quality requires live mode, --judge-model, and --judge-threshold")
                judge = openai_judge(args.judge_model)
        evaluate_suite(
            suite, args.metric, report, judge=judge, judge_model=args.judge_model,
            judge_threshold=args.judge_threshold, repeats=args.repeats,
        )
    except (OSError, ValueError) as error:
        report.update(status="error", reason=str(error))

    if args.report is not None:
        try:
            if args.dataset and args.report.resolve().is_relative_to(args.dataset.resolve()):
                print("Report path must be outside the active dataset", file=sys.stderr)
                return 2
            if args.report.exists() and args.suite and args.suite.exists() and args.report.samefile(args.suite):
                print("Report path refers to the input suite", file=sys.stderr)
                return 2
            if args.report.exists() and args.run_file and args.run_file.exists() and args.report.samefile(args.run_file):
                print("Report path refers to the saved runs input", file=sys.stderr)
                return 2
            args.report.parent.mkdir(parents=True, exist_ok=True)
            args.report.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
        except OSError as error:
            print(f"Could not write report: {error}", file=sys.stderr)
            return 2

    if "reason" in report:
        print(report["reason"], file=sys.stderr)
    if report.get("source_balance", {}).get("warning"):
        print(report["source_balance"]["warning"], file=sys.stderr)
    for case in report["cases"]:
        for metric, result in case["metrics"].items():
            print(f"{case['id']} | {metric} | {result['status']} | {result['reason']}")
    return EXIT_CODES[report["status"]]
