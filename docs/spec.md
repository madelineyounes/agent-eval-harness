# Agent evaluation harness spec

Draft. Working repository name `agent-eval-harness`.

Use the [build plan](build-plan.md) for implementation order, starter files, and acceptance tests for each roadmap issue.

## Purpose

Build a public Python evaluation harness that runs selected metrics against an agent's responses and tool traces. Editable YAML definitions identify each metric as deterministic or LLM judge. The repository includes the Python evaluators so a reviewer can inspect the scoring logic, run an individual metric, or run a suite in CI.

The first examples cover PR review and coding agents. A reviewer should surface known actionable issues and stay quiet on clean changes. A coding agent should fix the requested behavior, preserve existing behavior, and substantiate any claim of completion.

A reviewer can run the smoke suites from a fresh checkout and inspect a synthetic coding run that claims completion while a regression check fails. Replay uses captured results and needs no credentials or network access after setup.

## Cases and traces

Keep fixtures in version control. Each case defines a stable ID, user prompt, expected answer facts, required tool calls and arguments, and any forbidden tool calls. The agent adapter returns a run ID, final answer, ordered tool calls and results, and any execution error. Tool results record a success, a missing record, or a timeout. The adapter records calls at the tool boundary so an agent's text cannot stand in for a trace.

Capture operational telemetry alongside the trace. Record input and output tokens, elapsed time, tool and model call counts, retries, and error and stop reasons when the adapter can observe them. Record estimated cost with the pricing basis when available. Mark unavailable telemetry explicitly so a missing token count cannot pass a token budget check. Track agent usage and judge usage separately.

| Case | Expected trace and response |
| --- | --- |
| Actionable review | Match the known regression in the change. |
| Clean PR | Return no actionable findings. |
| Verified fix | Pass the check for the requested fix and the existing behavior check. |
| Unsupported completion | Claim completion while a required regression check fails. Both coding metrics fail. |

The first three cases form separate review and coding smoke suites. The unsupported completion case runs as a standalone demonstration. The first implementation scores structured captures. A later adapter can collect review evidence and independent verifier outputs from an actual coding task.

## Dataset design

Target roughly 80% main cases and 20% edge cases by case count in the benchmark dataset. Main cases cover common tasks and the variation users encounter within them. Edge cases cover failure modes with distinct consequences, such as missing data, timeouts, ambiguous requests, unnecessary retries, and premature stopping. The small smoke and demonstration suites select cases for coverage.

Give each benchmark case a `main` or `edge` label, a scenario family, and an expected outcome. Define required actions and acceptable alternatives before tuning the agent or judge. Keep related variants together when splitting development and held-out cases. Report the actual mix and show results for both groups so a strong overall result cannot hide weak edge-case performance. Treat 80/20 as a design target. Use production data to estimate production frequencies when that estimate matters.

## Generate dataset and metric drafts

Add commands to generate synthetic golden candidates and draft metric files. Generate cases from approved documents or reviewed seed cases. Give generated cases a proposed expected outcome, scenario family, and provenance, including seed IDs and generator configuration. Require a person to verify the expected outcome, check duplicates, and review the case before including it in a dataset. [DeepEval synthetic data guidance](https://deepeval.com/docs/synthetic-data-generation-introduction)

**Benchmark data warning.** Use at least two real goldens for every synthetic golden. Emit a warning when a benchmark contains fewer than two real cases per synthetic case. Include both counts in the report. Count distinct case IDs, with provenance rooted in an observed user task or workflow for real cases. A model-generated variant remains synthetic after review or promotion. The 80/20 main-to-edge target is a separate measure. Label the public smoke and demonstration suites as synthetic fixtures.

Generate metric code and tests as drafts for observable rules. Generate rubric criteria and scoring examples as drafts for qualitative judgments. Review the drafts and make the tests fail before implementing or adopting the metric. Fine-tune the metric's rules, rubric, and threshold against human-labeled pass and fail traces on the development split. Evaluate the tuned version on held-out scenario families and record agreement, false passes, and false failures. Keep the metric out of suite defaults until someone reviews that evidence in a PR.

## Golden dataset storage and promotion

Store the initial golden dataset as versioned JSON in Git under `datasets/goldens/`. Keep one case per file so reviewers can inspect a promotion in a small diff. A dataset manifest identifies the schema version, case membership, and splits. Git history provides revision and rollback. The public repository holds cases and reference traces approved for publication. A `--dataset` path can load the same format from a local checkout of a private repository when real examples cannot be shared. Keep raw reports outside the golden dataset.

Promotion starts from a saved report and a selected run ID. Require successful execution and passing required metrics before proposing a run for promotion. A reviewer independently checks the expected outcome and acceptable behavior, confirms provenance, and approves any trace excerpts for storage. For an existing case, attach the run as an optional reference trace and preserve the case's existing assertions. For a new case, draft assertions from independently verified evidence. Both paths keep the source classification and default to the development split for new cases.

The promotion command writes a candidate change for review. Record the run ID, source dataset revision, agent and metric versions, and promotion reason. Repeating the same promotion must produce no duplicate. Merge promotions through the same PR workflow as code. Keep the held-out case set fixed for a benchmark revision and review proposed changes to it as a separate dataset revision.

## Harbor tasks and execution options

Harbor tasks package an environment and a verifier. The native Harbor runner produces trial results and ATIF trajectories. Inspect AI can also run Harbor tasks through the optional `inspect-harbor` package and produces Inspect evaluation logs. Choose the runner when there is a benchmark to integrate. [Harbor job artifacts](https://github.com/harbor-framework/docs/blob/main/quickstart.mdx) [Inspect Harbor](https://meridianlabs-ai.github.io/inspect_harbor/) [Inspect evaluation logs](https://inspect.aisi.org.uk/eval-logs.html)

Import the first runner's saved artifacts into the harness's run format. Preserve the task version, runner and version, trial or sample reference, verifier outcome, and available trajectory and telemetry. This lets the harness apply the same metrics, reporting, and promotion workflow. If using Inspect, check the chosen task's environment and verifier support before comparing results with native Harbor. [Inspect Harbor task format](https://meridianlabs-ai.github.io/inspect_harbor/tasks.html)

The Git-backed golden dataset remains the source for reviewed cases, expected behavior, and promoted references. The credential-free PR suite starts with local synthetic fixtures. Add a second importer when a benchmark or existing run logs call for it.

## Metric files and selection

Each metric has a YAML definition under `metrics/`. Deterministic evaluators live under `agent_eval/metrics/`. A metric receives a case and the observed agent run. It returns a pass or fail result with a reason, plus a numeric score and threshold when applicable. The harness handles case selection, execution, reporting, and exit codes.

| Initial metric | File | What it checks |
| --- | --- | --- |
| `review-findings` | `agent_eval/metrics/review_findings.py` | Reports precision, recall, and counts of matched, missed, unexpected, and duplicate findings. |
| `patch-verification` | `agent_eval/metrics/patch_verification.py` | Requires fix checks that fail on the baseline and regression checks that pass on the baseline to pass after applying the patch. |
| `completion-claim` | `agent_eval/metrics/completion_claim.py` | Fails a claim of completion when required verifier checks failed or did not run. |

The first review metric compares human-reviewed finding keys made up of file path, symbol, and issue ID. Free-text review matching requires annotated examples and adjudication. Include both defect-bearing and clean PRs. For coding tasks, use a verifier controlled by the benchmark, keep its checks outside the editable patch, and validate the baseline so acceptable alternative fixes can pass. [SWE-bench Verified test design](https://openai.com/index/introducing-swe-bench-verified/)

The next deterministic metrics are change scope and verifier integrity, followed by execution budget and loop detection. Check protected paths and task-specific scope. Use recorded telemetry for token, call, retry, and time limits. For loops, look for repeated actions and unchanged outcomes beyond the allowed retry count. Add a trace-based judge once the dataset has labeled examples of review actionability and justified tool choices.

A registry maps stable metric IDs to their modules and supported run modes. A suite declares its default metric IDs. Use `--list-metrics` to see the available metrics and their supported modes. Repeat `--metric` to select one or more metrics for an ad hoc run. An explicit selection replaces the suite defaults for that run. The required CI job always uses the checked-in smoke suite defaults.

A run that accurately admits an incomplete fix can pass `completion-claim` while failing `patch-verification`. Report both results so an accurate status update gets credit without marking the task complete.

## Evaluation policy

Make deterministic metrics the majority of the suite and use them for all required PR checks. Read tool arguments, counts, tokens, and timing directly from the trace. Apply documented rules to check loops and budgets. A live judge can assess whether a costly call or retry was justified by the task, using the measured telemetry as evidence.

Write judge rubrics around behavior visible in the trace. Score whether the agent chose an appropriate tool, used the returned evidence, adapted after failure, and stopped once the task was complete. Include an anchored scoring scale and ask the judge to cite the trace steps that support its score. Answer correctness, clarity, and retrieval quality can have their own metrics. Calibrate behavioral rubrics on hand-labeled traces, including examples with identical final answers and different execution paths. [DeepEval trajectory-based evaluation](https://deepeval.com/docs/evaluation-trajectory-based-llm-evals)

- **Replay.** Apply the selected deterministic metrics to the recorded responses and traces.
- **Live.** Capture one agent run per case against the selected task environment, or load a saved run. Apply the selected metrics to the fixed response and trace. For judge metrics, record the model and rubric version. A judge error is an execution error.
- **Gate.** Any failed selected metric fails the suite. An empty suite, unknown or incompatible metric ID, or missing or skipped case result for a selected metric is an execution error. An expected tool timeout is a case input and can still produce a passing evaluation.

Live judging uses the provider selected in YAML. OpenAI, Anthropic, and local Ollama score captured traces through the same rubric interface. Prefer a judge from a different model family than the agent and check its agreement with human labels. The PR workflow runs deterministic replay without judge credentials.

## Repeat a metric on a fixed run

`--repeats N` evaluates each selected stochastic metric `N` times on the same captured response, trace, and telemetry. The agent runs once per case, or the harness reads the saved run. Deterministic metrics run once. Each judge repeat makes a fresh scoring request with the same model, settings, and rubric.

Store each repeat's score, reason, and any error. For a complete set of repeats, compute the arithmetic mean and apply the metric threshold to that mean. If a requested repeat fails, preserve the available results and mark the metric evaluation as an execution error. Report the requested and completed repeat counts so partial runs stay visible.

## Command and report

The initial CLI runs from the checkout with `python -m agent_eval`. These commands run the review smoke suite and isolate the completion claim on the coding failure example.

```text
python -m agent_eval --suite datasets/smoke/review.json --report artifacts/review.json
python -m agent_eval --suite datasets/demo/coding-failure.json --metric completion-claim --report artifacts/demo.json
```

Reporting is part of the harness. Every run prints a terminal summary and can write a versioned JSON report for CI or later analysis. The report includes the dataset version, run IDs, mode, selected metric IDs, and overall status. Case details include the agent response, trace, telemetry, and results by metric. With `--run-file`, load captured runs from an existing report and match them by dataset version and case ID. The CLI writes a report on evaluation failure and includes execution errors when it can write to the requested path.

| Report view | Information |
| --- | --- |
| Case and metric | Status, reason, threshold, and score. For judge metrics, include the model and rubric version, raw repeat scores, their mean and standard deviation, and repeat counts. |
| Suite and metric | Counts of passed, failed, and errored cases, pass rate among completed cases, completion rate, and mean case score where applicable. Show overall, main, and edge results. Each completed case contributes one score to the mean. Include counts by real and synthetic source and any dataset balance warning. |
| Agent operations | Trace coverage, call counts, tokens, latency, retries, loops, timeouts, and cost where available. Show missing-data counts and list the cases behind failures. |

Label confidence intervals by what was sampled. For a fixed agent run, a 95% interval around the mean judge score describes variation across repeat judge requests under the recorded settings. For suite performance, estimate a 95% interval from independent cases, keeping the main and edge mix fixed when resampling. Use one aggregate result per case. Keep related variants together if the sampled unit is a scenario family.

Record the interval method, sample size, and any resampling seed. Publish summary statistics and an explicit reason when the sample is too small or the design does not support an interval. Treat hand-picked smoke fixtures as descriptive results. An interval over judge repeats quantifies judge variability on the captured run. It cannot establish agent reliability across new runs or tasks. [NIST confidence limits for the mean](https://itl.nist.gov/div898/software/dataplot/refman1/auxillar/conflimi.htm)

| Exit code | Meaning |
| --- | --- |
| `0` | Every required case ran and passed. |
| `1` | A required evaluation check failed. |
| `2` | A setup or execution error prevented a valid result. |

Execution errors take precedence if a run also contains failed checks.

## Contribution rules

Keep source code, tests, fixtures, configuration, and workflow files free of comments. Put explanations in the README or user-facing documentation. Use docstrings only when they are part of the public API reference or command help. Keep the implementation readable through names and structure.

Use test-driven development for new behavior and bug fixes. Write a focused test, run it and confirm it fails for the intended reason, then implement the smallest change that makes it pass. Rerun the relevant tests after any refactor. Record the failing and passing test commands and outcomes in the pull request. For a docs-only change, record how you verified the documentation.

Make each change on a branch and merge it through a pull request, including changes to documentation and CI. Apply an active GitHub ruleset to the default branch that requires a pull request and the CI status check. Keep the bypass list empty so the rule also applies to repository maintainers. [GitHub ruleset settings](https://docs.github.com/en/repositories/configuring-branches-and-merges-in-your-repository/managing-rulesets/available-rules-for-rulesets)

## Pull request checks

Trigger GitHub Actions on `pull_request` for every PR into the default branch, including updates to open PRs and docs-only PRs. The required `tests` job runs the Python test suite and, once available, the credential-free smoke suite using the local replay command. Upload the smoke report on success or failure when the file exists. Run live evaluation in a separate manually triggered workflow with provider credentials stored as GitHub Actions secrets.

## Implementation milestones

1. **Set up the PR workflow and select custom metrics.** Add the test workflow and captured review and coding examples in the first implementation PR. Once GitHub has registered the `tests` job, make it required before merging. Build the three initial metric modules test-first. Verify the smoke suites pass and that the false completion case exits with `1` and reports the failed regression check.
2. **Capture independently verified results.** Add one small coding task with known baseline outcomes and a clean PR and defective PR pair. Check out a pinned revision for each task. Verify the reference fix and capture verifier results from a path the agent cannot modify. Exercise scope and verifier integrity checks. Verify that a fresh checkout can replay the smoke suites without credentials and that CI uploads the reports.
3. **Report behavior and operational metrics.** Add trace telemetry, deterministic budget and loop metrics, and main and edge reporting. Test missing telemetry and verify that an allowed retry and a loop produce different outcomes.
4. **Repeat judge scoring and report uncertainty.** Add one trace-based rubric. Use a fake judge to verify that repeated evaluations receive the same captured run, that their average controls the result, and that a failed repeat is reported. Test per-case and suite aggregation separately, including when there is too little data for an interval. Document the rubric and include a synthetic report in the README.
5. **Generate and promote goldens.** Test draft generation with a stub generator. Verify that a dataset below 2:1 warns and one at 2:1 passes the ratio check. Verify that generation leaves the active dataset untouched, that repeating a promotion creates no duplicate, and that a reviewed promotion can be evaluated from a clean checkout.
6. **Draft and calibrate metrics.** Generate a deterministic metric draft and a judge rubric from a stated behavior. Verify that generated metrics stay out of suite defaults. Record calibration results and verify that the development and held-out splits contain distinct scenario families.
7. **Import one Harbor-format task run.** Choose native Harbor or Inspect AI with `inspect-harbor` for the first benchmark. Use a saved run fixture to verify that the importer preserves runner, task, verifier, and trajectory data and that the resulting run works with the harness's metrics and promotion command.

The first public release can ship after milestone 2 with basic reports. Before milestone 4, choose the agent provider, judge model, threshold, interval estimators, and minimum sample sizes. Document the sample assumptions alongside the interval methods.
