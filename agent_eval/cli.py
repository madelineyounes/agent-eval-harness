import argparse
import json
import sys
from pathlib import Path

from agent_eval.calibration import calibrate, draft_metric
from agent_eval.captures import use_saved_runs
from agent_eval.docs_adapter import capture_docs
from agent_eval.goldens import SPLITS, draft, load_dataset, promote, read, write_proposal
from agent_eval.harbor_import import import_trial
from agent_eval.judge_providers import PROVIDERS, make_judge
from agent_eval.metric_config import DEFAULT_DIRECTORY, EVALUATORS, JudgeMetric, load_metrics
from agent_eval.metrics import trajectory_quality
from agent_eval.reporting import GROUPS, summarize


EXIT_CODES = {"pass": 0, "fail": 1, "error": 2}


def evaluate_suite(suite, selected_metrics, report, *, definitions=None, mode="replay",
                   judge=None, judge_provider=None, judge_model=None, judge_threshold=None, repeats=1):
    if not isinstance(suite, dict):
        raise ValueError("Suite must be a JSON object")
    cases = suite.get("cases")
    metrics = selected_metrics or suite.get("metrics")
    if not isinstance(cases, list) or not cases:
        raise ValueError("Suite must contain at least one case")
    if not isinstance(metrics, list) or not metrics:
        raise ValueError("Select at least one metric")
    if definitions is None:
        definitions = load_metrics()
    for metric in metrics:
        if not isinstance(metric, str) or metric not in definitions:
            raise ValueError(f"Unknown metric {metric!r}")
        if mode not in definitions[metric].modes:
            raise ValueError(f"Metric {metric!r} requires --mode live")

    report["selected_metrics"] = list(dict.fromkeys(metrics))
    judges = {}
    for metric in report["selected_metrics"]:
        definition = definitions[metric]
        if isinstance(definition, JudgeMetric):
            provider = judge_provider if judge_provider is not None else definition.provider
            if provider != definition.provider and not judge_model:
                raise ValueError(f"Set --judge-model when changing the provider for {metric}")
            model = judge_model if judge_model is not None else definition.model
            threshold = judge_threshold if judge_threshold is not None else definition.threshold
            if not isinstance(model, str) or not model.strip() or not 0 <= threshold <= 1:
                raise ValueError("Judge requires a model and threshold between 0 and 1")
            scorer = judge if judge is not None else make_judge(provider, model, definition.rubric)
            judges[metric] = (scorer, model, threshold, provider)
    if "dataset_version" in suite:
        report["dataset_version"] = suite["dataset_version"]
    if suite.get("source") in ("real", "synthetic"):
        report["dataset_source"] = suite["source"]
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
            definition = definitions[metric]
            try:
                if run.get("execution_error"):
                    raise ValueError("Captured run contains an execution error")
                if isinstance(definition, JudgeMetric):
                    scorer, model, threshold, provider = judges[metric]
                    result = trajectory_quality.evaluate(run, scorer, model, threshold, repeats, definition.rubric_version)
                    result["provider"] = provider
                else:
                    result = EVALUATORS[definition.evaluator]({**definition.expected, **expected}, run)
            except ValueError as error:
                result = {"status": "error", "reason": str(error)}
            results[metric] = {**result, "metric_type": definition.type, "metric_version": definition.version}
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


def harbor_command(argv):
    parser = argparse.ArgumentParser(prog="python -m agent_eval import-harbor")
    parser.add_argument("--trial", type=Path, required=True)
    parser.add_argument("--dataset", type=Path, required=True)
    parser.add_argument("--case-id", required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args(argv)
    try:
        dataset = load_dataset(args.dataset)
        case = next((case for case in dataset["cases"] if case["id"] == args.case_id), None)
        if case is None:
            raise ValueError(f"Unknown dataset case {args.case_id}")
        if any(args.output.resolve().is_relative_to(source.resolve()) for source in (args.trial, args.dataset)):
            raise ValueError("Import output must be outside the trial and dataset")
        run = import_trial(read(args.trial / "result.json"), read(args.trial / "agent/trajectory.json"))
        if run["task"] != case.get("harbor_task"):
            raise ValueError(f"Harbor task does not match reviewed case {args.case_id}")
        suite = {**dataset, "cases": [{**case, "run": run}]}
        write_proposal(args.output.parent.resolve(), args.output, suite)
    except (OSError, ValueError) as error:
        print(error, file=sys.stderr)
        return 2
    print(args.output)
    return 0


def main(argv=None):
    argv = sys.argv[1:] if argv is None else argv
    if argv and argv[0] in ("draft-goldens", "promote"):
        return golden_command(argv[0], argv[1:])
    if argv and argv[0] in ("draft-metric", "calibrate-metric"):
        return calibration_command(argv[0], argv[1:])
    if argv and argv[0] == "import-harbor":
        return harbor_command(argv[1:])
    parser = argparse.ArgumentParser(description="Evaluate captured coding-agent and PR review runs.")
    parser.add_argument("--list-metrics", action="store_true", help="List metric IDs, types, and supported modes.")
    parser.add_argument("--metrics-dir", type=Path, default=DEFAULT_DIRECTORY, help="Directory of YAML metric definitions.")
    inputs = parser.add_mutually_exclusive_group()
    inputs.add_argument("--suite", type=Path, help="Path to a JSON replay suite.")
    inputs.add_argument("--dataset", type=Path, help="Path to a versioned golden dataset directory.")
    parser.add_argument("--split", choices=SPLITS, help="Select one split of a golden dataset.")
    parser.add_argument("--metric", action="append", help="Select a metric, replacing suite defaults. Repeat for multiple metrics.")
    parser.add_argument("--repeats", type=int, default=1, help="Number of scores to request for each stochastic metric.")
    parser.add_argument("--mode", choices=("replay", "live"), default="replay", help="Enable a live judge in live mode.")
    parser.add_argument("--run-file", type=Path, help="Load fixed runs from a saved evaluation report.")
    parser.add_argument("--adapter", choices=("mock-docs",), help="Capture one new run per case with a live adapter.")
    parser.add_argument("--judge-provider", choices=PROVIDERS, help="Override the provider in the YAML judge definition.")
    parser.add_argument("--judge-model", help="Override the model in the YAML judge definition.")
    parser.add_argument("--judge-threshold", type=float, help="Minimum mean trajectory judge score to pass.")
    parser.add_argument("--report", type=Path, help="Write the evaluation report as JSON.")
    args = parser.parse_args(argv)
    if args.list_metrics:
        try:
            for definition in load_metrics(args.metrics_dir).values():
                print(f"{definition.id}\t{definition.type}\t{', '.join(definition.modes)}")
        except (OSError, ValueError) as error:
            print(error, file=sys.stderr)
            return 2
        return 0
    if args.suite is None and args.dataset is None:
        parser.error("--suite or --dataset is required unless --list-metrics is used")
    if args.split and args.dataset is None:
        parser.error("--split requires --dataset")
    if args.repeats < 1:
        parser.error("--repeats must be a positive integer")
    if args.adapter and (args.mode != "live" or args.run_file is not None):
        parser.error("--adapter requires --mode live and cannot be used with --run-file")
    if args.report and args.report.resolve().is_relative_to(args.metrics_dir.resolve()) and args.report.suffix in (".yaml", ".yml"):
        parser.error("Report path must be outside the YAML metric definitions")

    report = {"schema_version": 1, "mode": args.mode, "status": "pass", "cases": []}
    try:
        suite = load_dataset(args.dataset, args.split) if args.dataset is not None else read(args.suite)
        if args.run_file is not None:
            suite = use_saved_runs(suite, json.loads(args.run_file.read_text(encoding="utf-8")))
        if args.adapter == "mock-docs":
            suite = capture_docs(suite)
        evaluate_suite(
            suite, args.metric, report, definitions=load_metrics(args.metrics_dir), mode=args.mode,
            judge_provider=args.judge_provider, judge_model=args.judge_model,
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
