# Agent eval harness

Replay captured PR reviews and coding-agent runs with selectable Python metrics. The first examples use synthetic JSON fixtures. Python 3.12 or later is enough to run them from a checkout.

```sh
python -m unittest discover -s tests -v
python -m agent_eval --list-metrics
python -m agent_eval --suite datasets/smoke/review.json --report artifacts/review.json
python -m agent_eval --suite datasets/smoke/coding.json --report artifacts/coding.json
```

The clean PR and the PR with a known finding both pass. The coding case passes because the captured verifier results confirm the fix and preserve existing behavior.

```sh
python -m agent_eval --suite datasets/demo/coding-failure.json --report artifacts/coding-failure.json
```

The demonstration exits with `1`. The captured agent claimed completion after a fix check passed and an existing behavior check failed. The report shows failures for both the patch and the completion claim.

## Labeled PR review example

The [catalog review example](examples/review-v1) pairs clean and defective PR diffs with free-text reviews and finding labels. Its control report shows how replay counts a missed defect, an unsupported finding, and a duplicate.

## Independently verified coding example

The [pagination task](examples/pagination-v1) asks the agent to remove the empty page returned when four items are split into pages of two and to keep the final partial page when three items are split into pages of two. The task version pins the baseline, the Codex patch, and a deliberately regressive comparison patch.

```sh
python examples/pagination-v1/verify.py
python -m agent_eval --suite examples/pagination-v1/capture.json --report artifacts/pagination.json
```

The first command uses Git to apply each checked-in patch to a fresh copy of the baseline. The verifier stays outside that copy and records the changed paths and its SHA-256 hash before and after the run. The second command replays the capture and exits with `1` because the comparison patch drops the partial page. The Codex patch passes all four checks.

## Metrics

| Metric | What it checks |
| --- | --- |
| `review-findings` | Counts matched, unexpected, missed, and duplicate findings. Reports precision and recall when their denominators are nonzero. |
| `patch-verification` | Checks captured verifier results for both required fixes and existing behavior. |
| `completion-claim` | Checks whether a claim of completion has passing verifier evidence. |
| `change-scope` | Checks recorded changed paths against the case's allowlist. |
| `verifier-integrity` | Compares SHA-256 hashes for the case's protected verifier files. |
| `execution-budget` | Compares observed token, call, retry, and time counts with case-specific limits. |
| `loop-detection` | Checks consecutive identical tool calls and results against the allowed retry count. |

Review findings use curated keys with a file path, symbol, and issue ID. Review free-text findings and map them to keys before replay. A suite declares default metrics. Repeat `--metric` to replace the defaults with your selection. Exit codes are `0` for pass, `1` for failed metrics, and `2` for invalid inputs or execution errors.

The [synthetic operations suite](datasets/demo/operations.json) records `run.telemetry` and ordered `run.tool_calls`. For a budget, choose `input_tokens`, `output_tokens`, `model_calls`, `tool_calls`, `elapsed_ms`, or `retries` in `expected.budgets`. An observed value equal to its limit passes. Record unavailable telemetry as `null` or omit the field. A budget over an unavailable field returns exit `2`. For loop detection, set `expected.allowed_identical_retries`. Each consecutive group starts with one call followed by retries. A changed tool, arguments, or result starts a new group.

```sh
python -m agent_eval --suite datasets/demo/operations.json --report artifacts/operations.json
```

The replay exits `1`. The report identifies the exceeded tool-call budget and the lookup that retried twice with the same timeout.

Reports retain each captured run and summarize results overall and by the optional case `group` values `main` and `edge`. The pass rate counts completed cases, while the completion rate includes execution errors in its denominator. Each completed case contributes one score to the metric mean when it has a numeric result.

Confidence intervals use 2,000 bootstrap resamples and seed `0`. A fixed-run interval needs at least 10 completed, independent judge repeats under the same settings. It measures variation in the judge's scores for that run. A suite interval needs at least 20 independently sampled cases with complete scores, at least five per included group, and distinct `scenario_family` values. The suite must declare `"sampling": "independent"` based on its sampling design. The bootstrap preserves the main and edge counts. Reports give a reason when the data cannot support an interval. Smoke suites are descriptive.

## Score a fixed run with a live judge

The optional `trajectory-quality` metric uses the OpenAI Responses API to score the evidence behind a captured answer. The `trajectory-evidence-v1` rubric scores absent or contradictory evidence as `0`, partial support as `0.5`, and support for the main claim as `1`. Each repeat cites numbered tool calls. The example uses `gpt-5-mini-2025-08-07` and a mean threshold of `0.5`. [OpenAI GPT-5 mini documentation](https://developers.openai.com/api/docs/models/gpt-5-mini)

Set `OPENAI_API_KEY` for live requests. Run the first command to save the fixed capture. The second command sends its final answer and tool calls to the judge for ten scoring requests. Use captures approved for that provider. The suite and saved report must have the same `dataset_version` and matching case IDs.

```sh
python -m agent_eval --suite examples/judge-v1/suite.json --report artifacts/judge-capture.json
python -m agent_eval --suite examples/judge-v1/suite.json --mode live --run-file artifacts/judge-capture.json --metric trajectory-quality --judge-model gpt-5-mini-2025-08-07 --judge-threshold 0.5 --repeats 10 --report artifacts/judge.json
```

The [synthetic judge report](examples/judge-v1/report.json) shows per-repeat scores and the two interval fields. The manually triggered **Live judge example** workflow uses the same commands and reads its key from GitHub Actions secrets.

## Golden datasets

Replay the [starter golden dataset](datasets/goldens) or point `--dataset` at a private checkout. The [golden dataset guide](docs/golden-datasets.md) covers source balance, candidate generation, and reviewable promotion proposals.

The current CLI scores captured verifier outcomes. The [spec](docs/spec.md) describes agent execution, trace metrics, reporting, and golden promotion.

## Contributing

Work on a branch and use a PR for each change. For behavior changes, include the failing test output and the passing test output in the PR description. Keep explanations in user-facing docs and use descriptive names in code, tests, and workflows.
