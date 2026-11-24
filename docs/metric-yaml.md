# Edit metric definitions

Put one `.yaml` or `.yml` file per metric in `metrics/`. Choose the files to load with `--metrics-dir PATH`. A custom directory supplies the entire registry for that run. A suite or `--metric` selects definitions by ID. The report records each metric's type and version.

```sh
python -m agent_eval --list-metrics
```

## Deterministic metrics

Use `type: deterministic` and select a built-in evaluator by name. The evaluator checks recorded evidence. Use `expected` for shared rules and limits. Case expectations override these defaults one top-level field at a time. For example, a case that defines `budgets` replaces the full default budgets mapping.

```yaml
id: short-tool-run
type: deterministic
version: "1"
evaluator: execution-budget
expected:
  budgets:
    tool_calls: 4
```

Copy an existing definition to use a different ID or defaults. Change the version when a rule or threshold changes so saved reports identify the metric that scored them.

## LLM judges

Use `type: llm-judge` with `provider`, `model`, `threshold`, `rubric_version`, and a multiline `rubric`. Judges run in `--mode live`. `--judge-provider`, `--judge-model`, and `--judge-threshold` override the YAML defaults for a run. Supply a model name when changing providers.

**Choose a judge from a different model family than the agent.** This reduces the chance that both models share the same blind spots. Record both model IDs and check the judge's scores against human-labeled traces before relying on them.

| Provider | Setup |
| --- | --- |
| `openai` | Set `OPENAI_API_KEY` and use a model that supports structured Responses API output. |
| `anthropic` | Set `ANTHROPIC_API_KEY` and use a Claude model that supports JSON structured outputs. |
| `ollama` | Start Ollama and pull a model that supports structured output. The default endpoint is `http://127.0.0.1:11434`. Set `OLLAMA_BASE_URL` to use another server. |

```sh
python -m agent_eval --suite examples/judge-v1/suite.json --mode live --metric trajectory-quality --judge-provider ollama --judge-model qwen3.5:9b --repeats 2 --report artifacts/ollama-judge.json
python -m agent_eval --suite examples/judge-v1/suite.json --mode live --metric trajectory-quality --judge-provider anthropic --judge-model claude-sonnet-4-6 --repeats 2 --report artifacts/claude-judge.json
```

The `trajectory-decisions` definition grades tool choice, recovery, and stopping. It is available for manual evaluation and rubric calibration. [OpenAI structured outputs](https://developers.openai.com/api/docs/guides/structured-outputs) · [Anthropic structured outputs](https://platform.claude.com/docs/en/build-with-claude/structured-outputs) · [Ollama structured outputs](https://docs.ollama.com/capabilities/structured-outputs)
