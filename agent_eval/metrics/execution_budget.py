FIELDS = frozenset({"input_tokens", "output_tokens", "model_calls", "tool_calls", "elapsed_ms", "retries"})


def evaluate(expected, run):
    limits = expected.get("budgets")
    telemetry = run.get("telemetry")
    if not isinstance(limits, dict) or not limits or limits.keys() - FIELDS:
        raise ValueError("budgets must specify at least one supported telemetry field")
    if not isinstance(telemetry, dict):
        raise ValueError("Recorded telemetry is required")

    breaches = {}
    for field, limit in limits.items():
        observed = telemetry.get(field)
        if type(limit) is not int or limit < 0:
            raise ValueError(f"Budget for {field} must be a nonnegative integer")
        if type(observed) is not int or observed < 0:
            raise ValueError(f"Missing or invalid telemetry for {field}")
        if observed > limit:
            breaches[field] = {"limit": limit, "observed": observed}
    return {
        "status": "fail" if breaches else "pass",
        "reason": "Execution exceeded budget" if breaches else "Execution stayed within budget",
        "details": {"breaches": breaches},
    }
