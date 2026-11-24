import argparse
import json
import re
from pathlib import Path


REVISION = "0a42606b178a8c69d40c5765dc05c342f921e578"


def words(text):
    return set(re.findall(r"[^\W_]{3,}", text.casefold()))


def score(call, result):
    arguments = call["function"]["arguments"]
    if isinstance(arguments, str):
        try:
            arguments = json.loads(arguments)
        except ValueError:
            return 0.0
    if not isinstance(arguments, dict):
        return 0.0
    queries = arguments.get("query_list", arguments.get("query"))
    if isinstance(queries, str):
        queries = [queries]
    if not isinstance(queries, list) or not all(isinstance(query, str) for query in queries):
        return 0.0
    terms = words(" ".join(queries))
    return len(terms & words(result)) / len(terms) if terms else 0.0


def observations(path, split, family):
    with path.open(encoding="utf-8") as handle:
        for line in handle:
            row = json.loads(line)
            messages = row["messages"]
            for raw_index, label in row["step_labels"].items():
                if label not in (-1, 1):
                    continue
                index = int(raw_index)
                calls = messages[index].get("tool_calls") or []
                if len(calls) != 1 or calls[0]["function"]["name"] != "search":
                    continue
                call = calls[0]
                results = []
                for message in messages[index + 1:]:
                    if message["role"] != "tool":
                        break
                    if message.get("tool_call_id") == call["id"] and isinstance(message.get("content"), str):
                        results.append(message["content"])
                yield {
                    "id": f"{family}:{row['total_index']}:{index}", "split": split, "scenario_family": family,
                    "label": "pass" if label == 1 else "fail", "score": score(call, " ".join(results)),
                }


def main():
    parser = argparse.ArgumentParser(description="Extract scored human-labeled search steps from AgentProcessBench.")
    parser.add_argument("source", type=Path, help="Directory containing hotpotqa.jsonl and gaia_dev.jsonl")
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    labels = {
        "metric_id": "search-result-query-overlap", "metric_version": "1", "rubric_version": "search-step-progress-v1",
        "label_source": "human", "label_provenance": f"AgentProcessBench expert step labels at {REVISION}; excludes neutral steps",
        "cases": [
            *observations(args.source / "hotpotqa.jsonl", "development", "hotpotqa"),
            *observations(args.source / "gaia_dev.jsonl", "held-out", "gaia_dev"),
        ],
    }
    with args.output.open("x", encoding="utf-8", newline="\n") as handle:
        json.dump(labels, handle, indent=2)
        handle.write("\n")


if __name__ == "__main__":
    main()
