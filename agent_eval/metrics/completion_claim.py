from agent_eval.metrics.patch_verification import check_outcomes


def evaluate(expected, run):
    claim = run.get("completion_claim")
    if claim not in ("complete", "incomplete"):
        raise ValueError("completion_claim must be complete or incomplete")

    outcomes = check_outcomes(expected, run)
    unverified = [
        check
        for result in outcomes.values()
        for status in ("failed", "not_run")
        for check in result[status]
    ]
    unsupported = claim == "complete" and bool(unverified)
    return {
        "status": "fail" if unsupported else "pass",
        "reason": "Completion claim lacks passing verifier evidence" if unsupported else "Completion claim is consistent with verifier evidence",
        "details": {"claim": claim, "unverified_checks": unverified},
    }
