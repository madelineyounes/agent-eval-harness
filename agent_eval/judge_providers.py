import json
import os
from urllib.error import HTTPError
from urllib.parse import urlsplit
from urllib.request import Request, urlopen


PROVIDERS = ("openai", "anthropic", "ollama")
GRADE_SCHEMA = {
    "type": "object", "additionalProperties": False, "required": ["score", "reason"],
    "properties": {"score": {"type": "number"}, "reason": {"type": "string"}},
}


def grade_input(run):
    return json.dumps({
        "task": run.get("prompt"),
        "final_response": run["final_response"],
        "tool_calls": [{"step": step, "call": call} for step, call in enumerate(run["tool_calls"], 1)],
    })


def post(provider, url, headers, payload, timeout=60):
    request = Request(url, data=json.dumps(payload).encode(), headers={"Content-Type": "application/json", **headers})
    try:
        with urlopen(request, timeout=timeout) as response:
            return json.load(response)
    except HTTPError as error:
        raise ValueError(f"{provider} judge API returned HTTP {error.code}") from error


def parse_grade(texts, usage):
    if len(texts) != 1:
        raise ValueError("Judge returned no single structured grade")
    grade = json.loads(texts[0])
    if not isinstance(grade, dict):
        raise ValueError("Judge grade must be an object")
    return {**grade, "usage": usage}


def openai_score(model, rubric, evidence, key):
    result = post("OpenAI", "https://api.openai.com/v1/responses", {"Authorization": f"Bearer {key}"}, {
        "model": model, "instructions": rubric, "input": evidence, "store": False, "max_output_tokens": 2000,
        "text": {"format": {"type": "json_schema", "name": "trajectory_grade", "strict": True, "schema": GRADE_SCHEMA}},
    })
    if result.get("status") != "completed":
        raise ValueError("OpenAI judge response did not complete")
    texts = [
        content["text"] for item in result.get("output", []) if item.get("type") == "message"
        for content in item.get("content", []) if content.get("type") == "output_text"
    ]
    return parse_grade(texts, result.get("usage"))


def anthropic_score(model, rubric, evidence, key):
    result = post("Anthropic", "https://api.anthropic.com/v1/messages", {
        "x-api-key": key, "anthropic-version": "2023-06-01",
    }, {
        "model": model, "system": rubric, "messages": [{"role": "user", "content": evidence}], "max_tokens": 2000,
        "output_config": {"format": {"type": "json_schema", "schema": GRADE_SCHEMA}},
    })
    if result.get("stop_reason") != "end_turn":
        raise ValueError("Anthropic judge response did not complete")
    return parse_grade([item["text"] for item in result.get("content", []) if item.get("type") == "text"], result.get("usage"))


def ollama_score(model, rubric, evidence, url):
    result = post("Ollama", url, {}, {
        "model": model, "stream": False, "think": False, "format": GRADE_SCHEMA,
        "messages": [{"role": "system", "content": rubric}, {"role": "user", "content": evidence}],
    }, timeout=120)
    if result.get("done") is not True or result.get("done_reason") not in (None, "stop"):
        raise ValueError("Ollama judge response did not complete")
    usage = {field: result[name] for field, name in (("input_tokens", "prompt_eval_count"), ("output_tokens", "eval_count"))
             if result.get(name) is not None}
    return parse_grade([result.get("message", {}).get("content", "")], usage or None)


def make_judge(provider, model, rubric):
    if provider == "ollama":
        base = os.environ.get("OLLAMA_BASE_URL", "http://127.0.0.1:11434").rstrip("/")
        parts = urlsplit(base)
        if (parts.scheme not in ("http", "https") or not parts.hostname or parts.username is not None
                or parts.path or parts.query or parts.fragment):
            raise ValueError("OLLAMA_BASE_URL must be an HTTP origin")
        return lambda run: ollama_score(model, rubric, grade_input(run), f"{base}/api/chat")
    if provider == "openai":
        variable, scorer = "OPENAI_API_KEY", openai_score
    elif provider == "anthropic":
        variable, scorer = "ANTHROPIC_API_KEY", anthropic_score
    else:
        raise ValueError(f"Unknown judge provider {provider!r}")
    key = os.environ.get(variable)
    if not key:
        raise ValueError(f"{variable} is required for {provider} judging")
    return lambda run: scorer(model, rubric, grade_input(run), key)
