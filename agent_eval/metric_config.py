import re
from dataclasses import dataclass
from pathlib import Path

import yaml

from agent_eval.judge_providers import PROVIDERS
from agent_eval.metrics import (
    change_scope, completion_claim, execution_budget, loop_detection, patch_verification, review_findings, verifier_integrity,
)


DEFAULT_DIRECTORY = Path(__file__).resolve().parent.parent / "metrics"
EVALUATORS = {
    "review-findings": review_findings.evaluate,
    "patch-verification": patch_verification.evaluate,
    "completion-claim": completion_claim.evaluate,
    "change-scope": change_scope.evaluate,
    "verifier-integrity": verifier_integrity.evaluate,
    "execution-budget": execution_budget.evaluate,
    "loop-detection": loop_detection.evaluate,
}


@dataclass(frozen=True)
class DeterministicMetric:
    id: str
    version: str
    evaluator: str
    expected: dict
    type = "deterministic"
    modes = ("replay", "live")


@dataclass(frozen=True)
class JudgeMetric:
    id: str
    version: str
    provider: str
    model: str
    threshold: float
    rubric_version: str
    rubric: str
    type = "llm-judge"
    modes = ("live",)


class MetricLoader(yaml.SafeLoader):
    def construct_mapping(self, node, deep=False):
        mapping = super().construct_mapping(node, deep=deep)
        if len(mapping) != len(node.value):
            raise ValueError("Duplicate YAML mapping key")
        return mapping


def required_text(data, key):
    value = data.get(key)
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{key} must be nonempty text")
    return value


def parse_metric(data):
    if not isinstance(data, dict):
        raise ValueError("Metric definition must be a YAML mapping")
    metric_id = required_text(data, "id")
    if not re.fullmatch(r"[a-z0-9][a-z0-9-]*", metric_id):
        raise ValueError(f"Invalid metric ID {metric_id!r}")
    version = required_text(data, "version")
    common = {"id", "type", "version"}
    kind = data.get("type")
    if kind == "deterministic":
        if data.keys() - common - {"evaluator", "expected"}:
            raise ValueError("Unknown deterministic metric field")
        evaluator = required_text(data, "evaluator")
        if evaluator not in EVALUATORS:
            raise ValueError(f"Unknown deterministic evaluator {evaluator!r}")
        expected = data.get("expected", {})
        if not isinstance(expected, dict) or not all(isinstance(key, str) for key in expected):
            raise ValueError("expected must be a mapping with text keys")
        return DeterministicMetric(metric_id, version, evaluator, expected)
    if kind == "llm-judge":
        if data.keys() - common - {"provider", "model", "threshold", "rubric_version", "rubric"}:
            raise ValueError("Unknown LLM judge metric field")
        provider = required_text(data, "provider")
        if provider not in PROVIDERS:
            raise ValueError(f"Unknown LLM judge provider {provider!r}")
        threshold = data.get("threshold")
        if type(threshold) not in (int, float) or not 0 <= threshold <= 1:
            raise ValueError("threshold must be between 0 and 1")
        return JudgeMetric(metric_id, version, provider, required_text(data, "model"), threshold,
                           required_text(data, "rubric_version"), required_text(data, "rubric"))
    raise ValueError("type must be deterministic or llm-judge")


def load_metrics(directory=DEFAULT_DIRECTORY):
    definitions = {}
    for path in sorted(directory.iterdir()):
        if path.suffix not in (".yaml", ".yml"):
            continue
        try:
            metric = parse_metric(yaml.load(path.read_text(encoding="utf-8"), Loader=MetricLoader))
            if metric.id in definitions:
                raise ValueError(f"Duplicate metric ID {metric.id!r}")
        except (ValueError, yaml.YAMLError) as error:
            raise ValueError(f"{path}: {error}") from error
        definitions[metric.id] = metric
    if not definitions:
        raise ValueError(f"No YAML metric definitions in {directory}")
    return definitions
