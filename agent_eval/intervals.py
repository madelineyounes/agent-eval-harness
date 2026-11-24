import random
from collections import defaultdict
from statistics import quantiles


RESAMPLES = 2000
SEED = 0


def interval(unit, sample_size, strata=(), reason=None):
    bounds = None
    if reason is None:
        rng = random.Random(SEED)
        estimates = [
            sum(sum(rng.choices(values, k=len(values))) for values in strata) / sample_size
            for _ in range(RESAMPLES)
        ]
        percentiles = quantiles(estimates, n=40, method="inclusive")
        bounds = [percentiles[0], percentiles[-1]]
    return {
        "method": "stratified_percentile_bootstrap" if unit == "case" else "percentile_bootstrap",
        "sampled_unit": unit,
        "sample_size": sample_size,
        "seed": SEED,
        "resamples": RESAMPLES,
        "confidence": 0.95,
        "bounds": bounds,
        "reason": reason,
    }


def judge_interval(scores, *, complete=True):
    reason = None
    if not complete:
        reason = "One or more requested repeats failed"
    elif len(scores) < 10:
        reason = "At least 10 completed judge repeats are required"
    return interval("judge_repeat", len(scores), [scores], reason)


def suite_interval(cases, metric, sampling):
    strata = defaultdict(list)
    families = set()
    results = [case["metrics"][metric] for case in cases]
    sample_size = sum(result["status"] != "error" and result.get("score") is not None for result in results)
    reason = None
    if sampling != "independent":
        reason = "The suite does not declare independent case sampling"
    elif sample_size != len(cases):
        reason = "Every case must have a completed numeric score"
    elif sample_size < 20:
        reason = "At least 20 independently sampled cases are required"
    else:
        for case in cases:
            family = case.get("scenario_family")
            group = case.get("group")
            if not family or family in families:
                reason = "Each case must have a distinct scenario family"
                break
            if group not in ("main", "edge"):
                reason = "Each case needs a main or edge group"
                break
            families.add(family)
            strata[group].append(case["metrics"][metric]["score"])
        if reason is None and any(len(scores) < 5 for scores in strata.values()):
            reason = "At least 5 independently sampled cases per included group are required"
    return interval("case", sample_size, sorted(strata.values()), reason)
