def required_checks(expected, field):
    checks = expected.get(field)
    if (
        not isinstance(checks, list)
        or not checks
        or not all(isinstance(check, str) and check.strip() for check in checks)
        or len(set(checks)) != len(checks)
    ):
        raise ValueError(f"{field} must list distinct required checks")
    return checks


def check_outcomes(expected, run):
    fix_checks = required_checks(expected, "fail_to_pass")
    regression_checks = required_checks(expected, "pass_to_pass")
    if set(fix_checks) & set(regression_checks):
        raise ValueError("Fix and regression check IDs must be distinct")

    verification = run.get("verification")
    if not isinstance(verification, dict):
        raise ValueError("Verification must contain independently recorded check results")
    allowed = ("passed", "failed", "not_run")
    results = {}
    for group, checks in (("fix_checks", fix_checks), ("regression_checks", regression_checks)):
        outcomes = {status: [] for status in allowed}
        for check in checks:
            status = verification.get(check)
            if status not in allowed:
                raise ValueError(f"Missing or invalid verifier result for {check}")
            outcomes[status].append(check)
        results[group] = outcomes
    return results


def evaluate(expected, run):
    outcomes = check_outcomes(expected, run)
    passed = all(not result["failed"] and not result["not_run"] for result in outcomes.values())
    return {
        "status": "pass" if passed else "fail",
        "reason": "All required checks passed" if passed else "A required check failed or did not run",
        "details": outcomes,
    }
