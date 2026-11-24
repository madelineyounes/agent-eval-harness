import json
from collections import Counter


def signature(call):
    if (not isinstance(call, dict) or not isinstance(call.get("tool"), str) or not call["tool"].strip()
            or not isinstance(call.get("arguments"), dict)):
        raise ValueError("Each tool call requires a tool name and arguments mapping")
    return call["tool"], json.dumps(call["arguments"], sort_keys=True, allow_nan=False)


def evaluate(expected, run):
    required = expected.get("required_calls", [])
    forbidden = expected.get("forbidden_tools", [])
    ordered = expected.get("ordered_calls", False)
    calls = run.get("tool_calls")
    if not isinstance(required, list) or not isinstance(calls, list):
        raise ValueError("Required and observed tool calls must be lists")
    if not isinstance(forbidden, list) or not all(isinstance(tool, str) and tool.strip() for tool in forbidden):
        raise ValueError("forbidden_tools must be a list of tool names")
    if type(ordered) is not bool or not (required or forbidden):
        raise ValueError("A tool call contract needs a required call or forbidden tool and a boolean ordered_calls setting")

    required_keys = [signature(call) for call in required]
    observed_keys = [signature(call) for call in calls]
    available = Counter(observed_keys)
    missing = []
    for call, key in zip(required, required_keys):
        if available[key]:
            available[key] -= 1
        else:
            missing.append(call)
    forbidden_calls = [index for index, (name, _) in enumerate(observed_keys, 1) if name in forbidden]
    remaining = iter(observed_keys)
    out_of_order = ordered and not missing and not all(any(key == actual for actual in remaining) for key in required_keys)
    failed = missing or forbidden_calls or out_of_order
    return {
        "status": "fail" if failed else "pass",
        "reason": "Tool trace violates the call contract" if failed else "Tool trace satisfies the call contract",
        "details": {"missing_calls": missing, "forbidden_call_steps": forbidden_calls, "out_of_order": out_of_order},
    }
