import json
from itertools import groupby


def call_signature(entry):
    index, call = entry
    if (
        not isinstance(call, dict)
        or not isinstance(call.get("tool"), str)
        or not call["tool"].strip()
        or not isinstance(call.get("arguments"), dict)
        or "result" not in call
    ):
        raise ValueError(f"Tool call {index} requires a tool, arguments object, and observed result")
    return json.dumps([call["tool"], call["arguments"], call["result"]], sort_keys=True, allow_nan=False)


def evaluate(expected, run):
    allowed = expected.get("allowed_identical_retries")
    calls = run.get("tool_calls")
    if type(allowed) is not int or allowed < 0:
        raise ValueError("allowed_identical_retries must be a nonnegative integer")
    if not isinstance(calls, list):
        raise ValueError("Recorded tool_calls must be a list")

    loops = []
    for _, group in groupby(enumerate(calls, start=1), key=call_signature):
        first, call = next(group)
        retries = sum(1 for _ in group)
        if retries > allowed:
            loops.append({"first_call": first, "tool": call["tool"], "arguments": call["arguments"], "retries": retries})
    return {
        "status": "fail" if loops else "pass",
        "reason": "Repeated tool calls exceeded the retry limit" if loops else "Tool calls stayed within the retry limit",
        "details": {"loops": loops},
    }
