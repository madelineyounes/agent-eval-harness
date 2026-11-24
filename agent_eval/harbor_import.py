from collections import defaultdict
from datetime import datetime
from math import isfinite

from agent_eval.goldens import nonempty


HARBOR_VERSION = "0.23.0"


def record(value, label):
    if not isinstance(value, dict):
        raise ValueError(f"Missing or invalid {label}")
    return value


def ordered_calls(steps):
    observed = []
    for index, step in enumerate(steps, 1):
        step = record(step, f"ATIF step {index}")
        if step.get("step_id") != index or step.get("source") not in ("agent", "system", "user"):
            raise ValueError(f"Invalid ATIF step order or source at {index}")
        raw_calls = step.get("tool_calls")
        calls = [] if raw_calls is None else raw_calls
        observation = record(step.get("observation") or {}, "ATIF observation")
        results = observation.get("results", [])
        if not isinstance(calls, list) or not isinstance(results, list):
            raise ValueError(f"Invalid ATIF tool calls or results at step {index}")
        by_call = defaultdict(list)
        for result in results:
            result = record(result, "ATIF observation result")
            call_id = result.get("source_call_id")
            if call_id is not None:
                if not nonempty(call_id):
                    raise ValueError(f"Invalid result call ID at step {index}")
                by_call[call_id].append({key: value for key, value in result.items() if key != "source_call_id"})
        seen = set()
        for call in calls:
            call = record(call, "ATIF tool call")
            call_id, tool, arguments = call.get("tool_call_id"), call.get("function_name"), call.get("arguments")
            if not nonempty(call_id) or call_id in seen or not nonempty(tool) or not isinstance(arguments, dict):
                raise ValueError(f"Invalid ATIF tool call at step {index}")
            seen.add(call_id)
            item = {"tool": tool, "arguments": arguments, "step_id": index, "call_id": call_id}
            if call_id in by_call:
                item["result"] = by_call[call_id]
            observed.append(item)
        if by_call.keys() - seen:
            raise ValueError(f"ATIF observation references an unknown call at step {index}")
    return observed


def elapsed_ms(timing):
    if not isinstance(timing, dict) or not all(nonempty(timing.get(key)) for key in ("started_at", "finished_at")):
        return None
    try:
        start, end = (datetime.fromisoformat(timing[key]) for key in ("started_at", "finished_at"))
        duration = round((end - start).total_seconds() * 1000)
    except (TypeError, ValueError):
        return None
    return duration if duration >= 0 else None


def import_trial(result, trajectory):
    result = record(result, "Harbor trial result")
    trajectory = record(trajectory, "ATIF trajectory")
    required = ("id", "trial_name", "task_name", "task_checksum")
    if not all(nonempty(result.get(field)) for field in required):
        raise ValueError("Harbor result requires trial ID and name, task name, and task checksum")
    agent = record(result.get("agent_info"), "Harbor agent information")
    if not all(nonempty(agent.get(field)) for field in ("name", "version")):
        raise ValueError("Harbor agent name and version are required")
    verifier = record(result.get("verifier_result"), "Harbor verifier rewards")
    rewards = record(verifier.get("rewards"), "Harbor verifier rewards")
    if not rewards or not all(type(value) in (int, float) and isfinite(value) for value in rewards.values()):
        raise ValueError("Harbor verifier rewards must contain finite numeric values")

    steps = trajectory.get("steps")
    if trajectory.get("schema_version") != "ATIF-v1.8" or not isinstance(steps, list) or not steps:
        raise ValueError("Import requires a nonempty ATIF-v1.8 trajectory")
    if trajectory.get("continued_trajectory_ref") or trajectory.get("subagent_trajectories"):
        raise ValueError("Import requires a standalone ATIF trajectory")
    calls = ordered_calls(steps)
    context = record(result.get("agent_result") or {}, "Harbor agent result")
    metrics = record(trajectory.get("final_metrics") or {}, "ATIF final metrics")
    telemetry = {}
    for field, harbor_key, atif_key in (
        ("input_tokens", "n_input_tokens", "total_prompt_tokens"),
        ("output_tokens", "n_output_tokens", "total_completion_tokens"),
        ("cached_tokens", "n_cache_tokens", "total_cached_tokens"),
        ("cost_usd", "cost_usd", "total_cost_usd"),
    ):
        value = context.get(harbor_key)
        telemetry[field] = metrics.get(atif_key) if value is None else value
    model_calls = [step.get("llm_call_count") for step in steps if step["source"] == "agent"]
    telemetry.update(
        tool_calls=len(calls), elapsed_ms=elapsed_ms(result.get("agent_execution")), retries=None,
        model_calls=sum(model_calls) if model_calls and all(type(count) is int and count >= 0 for count in model_calls) else None,
    )
    final = next((step.get("message") for step in reversed(steps)
                  if step["source"] == "agent" and not step.get("tool_calls") and isinstance(step.get("message"), str)), None)
    return {
        "id": result["id"], "runner": "harbor", "runner_version": HARBOR_VERSION,
        "trial_name": result["trial_name"], "trial_uri": result.get("trial_uri"),
        "task": result["task_name"], "task_version": result["task_checksum"], "task_id": result.get("task_id"),
        "agent": agent["name"], "agent_version": agent["version"], "execution_error": result.get("exception_info"),
        "verifier_rewards": rewards,
        "verification": {check: "passed" if reward == 1 else "failed"
                         for check, reward in rewards.items() if reward in (0, 1)},
        "trajectory": trajectory, "tool_calls": calls, "final_response": final, "telemetry": telemetry,
    }
