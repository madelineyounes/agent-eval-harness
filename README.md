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

The first command uses Git to apply each checked-in patch to a fresh copy of the baseline. The verifier stays outside that copy. It prints the recorded results for the baseline and both patches. The second command replays the saved capture and exits with `1` because the comparison patch drops the partial page. The Codex patch passes both metrics.

## Metrics

| Metric | What it checks |
| --- | --- |
| `review-findings` | Counts matched, unexpected, missed, and duplicate findings. Reports precision and recall when their denominators are nonzero. |
| `patch-verification` | Checks captured verifier results for both required fixes and existing behavior. |
| `completion-claim` | Checks whether a claim of completion has passing verifier evidence. |

Review findings use curated keys with a file path, symbol, and issue ID. Review free-text findings and map them to keys before replay. A suite declares default metrics. Repeat `--metric` to replace the defaults with your selection. Exit codes are `0` for pass, `1` for failed metrics, and `2` for invalid inputs or execution errors.

The current CLI scores captured verifier outcomes. The [spec](docs/spec.md) describes agent execution, trace metrics, reporting, and golden promotion.

## Contributing

Work on a branch and use a PR for each change. For behavior changes, include the failing test output and the passing test output in the PR description. Keep explanations in user-facing docs and use descriptive names in code, tests, and workflows.
