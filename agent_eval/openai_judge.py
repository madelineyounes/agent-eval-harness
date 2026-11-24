import json
import os
from urllib.error import HTTPError
from urllib.request import Request, urlopen

from agent_eval.metrics.trajectory_quality import RUBRIC


def openai_judge(model):
    key = os.environ.get("OPENAI_API_KEY")
    if not key:
        raise ValueError("OPENAI_API_KEY is required for live judging")

    def score(run):
        payload = {
            "model": model,
            "instructions": RUBRIC,
            "input": json.dumps({
                "final_response": run["final_response"],
                "tool_calls": [{"step": step, "call": call} for step, call in enumerate(run["tool_calls"], 1)],
            }),
            "store": False,
            "max_output_tokens": 2000,
            "text": {"format": {
                "type": "json_schema", "name": "trajectory_grade", "strict": True,
                "schema": {
                    "type": "object", "additionalProperties": False, "required": ["score", "reason"],
                    "properties": {"score": {"type": "number"}, "reason": {"type": "string"}},
                },
            }},
        }
        request = Request(
            "https://api.openai.com/v1/responses", data=json.dumps(payload).encode(),
            headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json"},
        )
        try:
            with urlopen(request, timeout=60) as response:
                result = json.load(response)
        except HTTPError as error:
            raise ValueError(f"Judge API returned HTTP {error.code}") from error
        if result.get("status") != "completed":
            raise ValueError("Judge response did not complete")
        texts = [
            content["text"] for item in result.get("output", []) if item.get("type") == "message"
            for content in item.get("content", []) if content.get("type") == "output_text"
        ]
        if len(texts) != 1:
            raise ValueError("Judge returned no single structured grade")
        grade = json.loads(texts[0])
        grade["usage"] = result.get("usage")
        return grade

    return score
