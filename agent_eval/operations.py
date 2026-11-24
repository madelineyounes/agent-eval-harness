from collections import Counter
from math import isfinite

from agent_eval.metrics.execution_budget import FIELDS


TELEMETRY_FIELDS = (*sorted(FIELDS), "cached_tokens", "cost_usd")


def recorded_number(value):
    return (type(value) is int and value >= 0) or (type(value) is float and isfinite(value) and value >= 0)


def totals(values, count):
    return {"total": sum(values) if values else None, "observed_cases": len(values), "missing_cases": count - len(values)}


def summarize_operations(cases):
    count = len(cases)
    samples = {key: [] for key in TELEMETRY_FIELDS}
    timeouts = []
    result_statuses = Counter()
    stop_reasons = Counter()
    failed = {}
    loop_cases = []
    trace_count = 0

    for case in cases:
        run = case.get("run", {})
        telemetry = run.get("telemetry")
        telemetry = telemetry if isinstance(telemetry, dict) else {}
        calls = run.get("tool_calls")
        has_trace = isinstance(calls, list)
        if has_trace:
            trace_count += 1
            statuses = []
            for call in calls:
                result = call.get("result") if isinstance(call, dict) else None
                status = result.get("status") if isinstance(result, dict) else None
                if isinstance(status, str) and status:
                    statuses.append(status)
            result_statuses.update(statuses)
            if len(statuses) == len(calls):
                timeouts.append(statuses.count("timeout"))

        for field in TELEMETRY_FIELDS:
            value = telemetry.get(field)
            if field == "tool_calls" and not recorded_number(value) and has_trace:
                value = len(calls)
            if recorded_number(value):
                samples[field].append(value)

        stop_reason = run.get("stop_reason")
        if isinstance(stop_reason, str) and stop_reason:
            stop_reasons[stop_reason] += 1
        failures = [name for name, result in case["metrics"].items() if result["status"] != "pass"]
        if failures and "id" in case:
            failed[case["id"]] = failures
        if any(result.get("details", {}).get("loops") for result in case["metrics"].values()):
            loop_cases.append(case["id"])

    return {
        "trace_coverage": {"recorded_cases": trace_count, "missing_cases": count - trace_count,
                           "rate": trace_count / count if count else None},
        "telemetry": {key: totals(values, count) for key, values in samples.items()},
        "tool_timeouts": totals(timeouts, count),
        "observed_tool_result_statuses": dict(result_statuses),
        "stop_reasons": dict(stop_reasons),
        "loop_cases": loop_cases,
        "failed_cases": failed,
    }
