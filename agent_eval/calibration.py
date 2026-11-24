import re
from pathlib import Path

from agent_eval.goldens import SPLITS, nonempty


def metric_template(metric_id, behavior, tool):
    return {
        "metric.py": "def evaluate(expected, run):\n    raise NotImplementedError('Implement the reviewed rule')\n",
        "test_metric.py": (
            "import unittest\n\nfrom metric import evaluate\n\n\n"
            "class DraftMetricTests(unittest.TestCase):\n"
            "    def test_observed_action_passes(self):\n"
            f"        call = {{'tool': {tool!r}, 'arguments': {{}}, 'result': {{'status': 'success'}}}}\n"
            f"        self.assertEqual(evaluate({{'tool': {tool!r}}}, {{'tool_calls': [call]}})['status'], 'pass')\n\n"
            "    def test_missing_action_fails(self):\n"
            f"        self.assertEqual(evaluate({{'tool': {tool!r}}}, {{'tool_calls': []}})['status'], 'fail')\n"
        ),
        "rubric.md": (
            f"# {metric_id} rubric draft\n\n## Observable behavior\n\n{behavior}\n\n"
            f"Use the captured `{tool}` calls, their results, and the final response. Cite tool call numbers.\n\n"
            "| Score | Evidence |\n| --- | --- |\n"
            f"| 0 | The trace contains no `{tool}` call that supports the claim. |\n"
            f"| 0.5 | A `{tool}` call supports part of the claim. |\n"
            f"| 1 | A completed `{tool}` call supports the main claim. |\n"
        ),
    }


def draft_metric(output, metric_id, behavior, tool, generator=metric_template):
    if (not isinstance(metric_id, str) or re.fullmatch(r"[a-z0-9][a-z0-9-]*", metric_id) is None
            or not nonempty(behavior) or not nonempty(tool)):
        raise ValueError("Provide a metric ID, observable behavior, and tool name")
    files = generator(metric_id, behavior.strip(), tool.strip())
    if not isinstance(files, dict) or files.keys() != {"metric.py", "test_metric.py", "rubric.md"} or not all(map(nonempty, files.values())):
        raise ValueError("Generator must return a metric draft, tests, and rubric")
    root = Path(output).resolve()
    destination = root / metric_id
    if not destination.resolve().is_relative_to(root):
        raise ValueError("Draft path escapes the staging directory")
    destination.mkdir(parents=True)
    for name, contents in files.items():
        (destination / name).write_text(contents, encoding="utf-8", newline="\n")
    return destination


def agreement(cases, threshold):
    false_passes = []
    false_failures = []
    disagreements = []
    for case in cases:
        observed = "pass" if case["score"] >= threshold else "fail"
        if observed != case["label"]:
            (false_passes if observed == "pass" else false_failures).append(case["id"])
            disagreements.append({"id": case["id"], "score": case["score"], "label": case["label"], "result": observed})
    return {
        "case_count": len(cases),
        "agreement": (len(cases) - len(disagreements)) / len(cases),
        "false_passes": false_passes,
        "false_failures": false_failures,
        "disagreements": disagreements,
    }


def calibrate(dataset):
    fields = ("metric_id", "metric_version", "rubric_version", "label_provenance")
    if (not isinstance(dataset, dict) or not all(nonempty(dataset.get(field)) for field in fields)
            or not isinstance(dataset.get("cases"), list)
            or dataset.get("label_source") not in ("human", "synthetic")):
        raise ValueError("Calibration requires metric and rubric versions, label provenance, and labeled cases")
    splits = {split: [] for split in SPLITS}
    ids = set()
    families = {}
    for case in dataset["cases"]:
        if (not isinstance(case, dict) or not nonempty(case.get("id")) or not nonempty(case.get("scenario_family"))
                or case.get("split") not in SPLITS or case.get("label") not in ("pass", "fail")
                or type(case.get("score")) not in (int, float) or not 0 <= case["score"] <= 1):
            raise ValueError("Each calibration case needs an ID, split, scenario family, pass/fail label, and score from 0 to 1")
        if case["id"] in ids:
            raise ValueError(f"Duplicate calibration case {case['id']}")
        ids.add(case["id"])
        if families.setdefault(case["scenario_family"], case["split"]) != case["split"]:
            raise ValueError(f"A scenario family belongs to both calibration splits: {case['scenario_family']}")
        splits[case["split"]].append(case)

    development = splits["development"]
    if {case["label"] for case in development} != {"pass", "fail"} or not splits["held-out"]:
        raise ValueError("Calibration needs both labels in development and at least one held-out case")
    candidates = {0, 1, *(case["score"] for case in development)}
    development_results = {threshold: agreement(development, threshold) for threshold in candidates}
    threshold = max(candidates, key=lambda value: (
        development_results[value]["agreement"], -len(development_results[value]["false_passes"]), value,
    ))
    return {
        **{field: dataset[field] for field in (*fields, "label_source")},
        "threshold": threshold,
        "development": development_results[threshold],
        "held-out": agreement(splits["held-out"], threshold),
    }
