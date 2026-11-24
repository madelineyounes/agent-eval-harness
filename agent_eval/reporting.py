from collections import Counter
from statistics import mean

from agent_eval.intervals import suite_interval
from agent_eval.operations import summarize_operations


GROUPS = ("main", "edge")
STATUSES = ("pass", "fail", "error")


def rates(results):
    counts = Counter(result["status"] for result in results)
    completed = counts["pass"] + counts["fail"]
    scores = [result["score"] for result in results if result["status"] != "error" and result.get("score") is not None]
    return {
        "counts": {status: counts[status] for status in STATUSES},
        "pass_rate": counts["pass"] / completed if completed else None,
        "completion_rate": completed / len(results) if results else None,
        "mean_score": mean(scores) if scores else None,
    }


def summarize(cases, metrics, sampling=None):
    groups = {"overall": cases, **{group: [case for case in cases if case.get("group") == group] for group in GROUPS}}
    return {
        "operations": summarize_operations(cases),
        "cases": {
            group: rates([{"status": max((value["status"] for value in case["metrics"].values()), key=STATUSES.index)}
                          for case in members])
            for group, members in groups.items()
        },
        "metrics": {
            metric: {
                group: {
                    **rates([case["metrics"][metric] for case in members]),
                    **({"confidence_interval": suite_interval(members, metric, sampling)} if group == "overall" else {}),
                }
                for group, members in groups.items()
            }
            for metric in metrics
        },
    }
