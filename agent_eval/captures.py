def use_saved_runs(suite, report):
    if not isinstance(suite, dict) or not isinstance(suite.get("cases"), list):
        raise ValueError("Suite must contain cases to match saved runs")
    version = suite.get("dataset_version")
    if not isinstance(report, dict) or report.get("schema_version") != 1:
        raise ValueError("Saved runs must come from a schema version 1 report")
    if not isinstance(version, str) or not version.strip() or report.get("dataset_version") != version:
        raise ValueError("Suite and saved report require the same dataset_version")
    if not isinstance(report.get("cases"), list):
        raise ValueError("Saved report must contain cases")

    runs = {}
    for case in report["cases"]:
        if not isinstance(case, dict) or not isinstance(case.get("id"), str) or not isinstance(case.get("run"), dict):
            raise ValueError("Saved report case must have an ID and a captured run")
        if case["id"] in runs:
            raise ValueError(f"Duplicate saved case {case['id']}")
        runs[case["id"]] = case["run"]
    cases = []
    for case in suite["cases"]:
        if not isinstance(case, dict) or not isinstance(case.get("id"), str) or case["id"] not in runs:
            raise ValueError(f"No saved run for suite case {case!r}")
        cases.append({**case, "run": runs[case["id"]]})
    return {**suite, "cases": cases}
