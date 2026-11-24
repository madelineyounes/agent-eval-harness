# Build the agent evaluation harness

Use the [spec](spec.md) for product behavior and the [harness roadmap](https://github.com/madelineyounes/agent-eval-harness/issues/3) for live issue status. Start on current `main`. Read [AGENTS.md](../AGENTS.md) before opening a PR.

PR #24 closed #5. The [pagination example](../examples/pagination-v1) shows a pinned baseline, an independently verified patch, and a regression control. The harness already has a replay CLI and three metric modules.

## Pick the next PR

1. Start with [#6](https://github.com/madelineyounes/agent-eval-harness/issues/6). Its instructions below are enough to implement the first PR.
2. Work through #7, #8, #9, #10, and #11 in that order. Split a task into multiple PRs at the boundaries listed below.
3. Handle #4 when you have GitHub ruleset access. Publish #12 after #5, #6, and the change scope and verifier integrity checks from #7 are merged. Check the release procedure below before tagging.

Take one section at a time. Write the focused test first for behavior changes and record why it fails. Run `python -m unittest discover -s tests -v` and both [README smoke commands](../README.md) before opening the PR. Run Ponytail Review and resolve actionable findings. Use **What changed**, **Why**, and **How it was tested** in the PR. Add `Closes #N` after every acceptance check for that issue is satisfied. Verify the GitHub Actions `tests` job before merging.

Use Python 3.12 and the standard library for replay. Keep live providers and task runners optional. Preserve the existing CLI exit codes: `0` for pass, `1` for failed evaluation, and `2` for invalid input or execution error. Keep replay independent of model credentials.

## #6 Benchmark PR reviews with labeled findings

1. Create `examples/review-v1/` with two unified diffs against the same checked-in `catalog.py` baseline. Give the baseline two functions. `store(catalog, key, value)` stores the supplied value, including an empty string. `has_key(catalog, key)` checks key membership, including keys that map to empty strings.
2. Make the clean diff a local variable rename or equivalent refactor. In the defective diff, make `store` skip empty values and make `has_key` return the truthiness of the stored value. Document a minimal input that reproduces each defect. Record the exact review prompt and save its free-text responses beside the diffs. Identify any manually written control as synthetic.
3. Hand-label the clean diff with `[]` and the defective diff with two keys. Use `["catalog.py", "store", "drops-empty-value"]` and `["catalog.py", "has_key", "ignores-present-empty-value"]`. In a README beside the fixtures, show how a reviewer maps each actionable comment to a key by path, symbol, and behavior. Assign a distinct key to an unsupported actionable claim. Keep both entries when two comments describe the same defect. Ignore praise and general advice that identifies no defect.
4. Write `passing.json` with the clean review and a review that identifies both defects. Write `control.json` with a defective-PR review that mentions the `store` defect twice, misses the `has_key` defect, and claims the function lowercases keys. Give that last claim its own key. Use `expected.review_findings` and `run.review_findings` from [the smoke fixture](../datasets/smoke/review.json).
5. Add a CLI integration test under `tests/`. Use the existing [review metric](../agent_eval/metrics/review_findings.py) and run the same commands in the example README.

```sh
python -m agent_eval --suite examples/review-v1/passing.json --report artifacts/review-v1-pass.json
python -m agent_eval --suite examples/review-v1/control.json --report artifacts/review-v1-control.json
```

The passing suite exits `0`. The control exits `1` with one true positive, one false positive, one false negative, one duplicate, precision `0.5`, and recall `0.5`. Assert the exact missed and unexpected keys in the JSON report. Link the example from the root README. This issue uses manual annotation and the existing replay engine.

## #7 Check scope, verifier integrity, budgets, and loops

1. In the first PR, start from the [pagination verifier](../examples/pagination-v1/verify.py). Have the trusted capture code record repository-relative changed paths and verifier SHA-256 hashes before and after the patch. Record evidence outside the candidate patch. Keep evidence capture separate from scoring.
2. Add `change-scope` and `verifier-integrity` modules under `agent_eval/metrics/`. Register both in `agent_eval/cli.py`. Give each case explicit allowed paths and protected verifier paths. Fail for a changed path outside the allowed set or changed verifier bytes. Treat absent required evidence or a malformed path as an execution error. Test an allowed change, an out-of-scope change, an altered verifier, and missing evidence.
3. In the next PR, add optional, recorded telemetry for input tokens, output tokens, model calls, tool calls, elapsed milliseconds, and retries. A case sets the limits it needs. Add `execution-budget` against those limits and `loop-detection` against ordered tool evidence. Compare consecutive calls with identical tool and arguments and an unchanged observed result. Count the first call separately from retries. Reset the count when the action or result changes.
4. Check a value equal to the budget, one unit over budget, and missing required telemetry. For loops, test a retry within the limit, enough identical calls to exceed the limit, and a retry that makes progress. Keep existing suites replayable with their current metric selections.

Run each new metric by name on a checked-in captured fixture. Verify the report names the breached path or budget, or identifies the repeated action. Missing evidence produces exit `2`. A known breach produces exit `1`.

## #8 Repeat judge scoring and report uncertainty

1. In the first PR, add scoring and aggregation with a fake judge under `tests/`. Pass the same captured run to the judge for every repeat. Use one trace rubric that scores whether the agent uses a tool result to support its final claim. Give it anchored scores, a model identifier, and a rubric version. Keep the model and threshold explicit in live configuration.
2. Add `--repeats N` for stochastic metrics. Require a positive integer. Score deterministic metrics once. Store every repeat result, the requested and completed counts, mean, sample standard deviation when defined, and threshold. Use mean greater than or equal to threshold for pass. Record a failed repeat and return exit `2`, retaining the completed scores.
3. Add suite aggregates over one result per case. Report counts by status, pass rate among completed cases, completion rate, and mean score for overall, main, and edge cases. Handle a zero denominator as `null`. Keep the existing report fields. Add dataset version and run IDs when available.
4. Test a fixed trace with fake scores `0.25` and `0.75` at threshold `0.5`. It passes, and the agent run count stays at one. Test a judge exception after one success and a missing group. In an aggregation unit test, use two completed cases with different repeat counts. Their case means carry equal weight in the suite mean.
5. In a separate PR, add 95% percentile bootstrap intervals. Use 2,000 resamples, seed `0`, and the 2.5th and 97.5th percentiles as starting defaults. For a fixed run, resample independent judge scores and require at least 10 completed repeats. For a suite, resample independent case scores within main and edge groups, preserving their sizes. Require at least 20 cases overall and at least 5 cases in each included group. For the first implementation, omit the suite interval when cases share a scenario family. Include method, sampled unit, size, and seed in the report. For hand-picked smoke cases or an ineligible sample, report a reason and descriptive results. Document these cutoffs as reporting defaults and record the assumptions before using them on a benchmark.
6. Connect one optional live judge after the fake-judge path passes. Record the chosen provider, model, threshold, and rubric in user-facing docs. Add a saved example report and keep required CI on deterministic replay.

The fake-judge tests run without credentials. A repeated score and a suite score have distinct report fields. A fixed seed reproduces interval bounds. A suite with too few independent cases still reports counts and scores.

## #9 Generate and promote versioned golden cases

1. Add a manifest under `datasets/goldens/` and use one JSON file per case. Give the manifest a schema version and dataset revision. Record case ID, scenario family, split, main or edge, real or synthetic provenance, and expected outcomes. Keep the same format usable in a private checkout.
2. Test the manifest loader with duplicate IDs, missing files, and one scenario family in both development and held-out splits. Run the source balance check on distinct case IDs. One real and one synthetic case warns. Two real and one synthetic case meet the target. Report counts for real and synthetic source and for main and edge cases. Document the 80/20 main-to-edge design target.
3. Add a draft generator with a stub in tests. It accepts reviewed seeds or approved source text and writes candidate files to a staging directory. Record seed IDs and generator configuration. Verify that generating a draft leaves the versioned manifest and cases untouched. A reviewed synthetic candidate keeps its synthetic provenance.
4. Add a promotion command that takes a saved report and run ID. Require passing evidence for all required metrics. Create a proposal for PR review with the run ID, dataset revision, agent and metric versions, and promotion reason. For an existing case, preserve assertions and attach a reference trace. For a new case, default to development and require independently reviewed assertions. Use case ID and run ID as the identity of the promoted reference.

Test promotion twice and verify that a second run produces no duplicate. Reject failed and incomplete runs. From a fresh checkout, replay one reviewed example and show that its expected checks still apply.

## #10 Draft and calibrate metrics

1. Accept a short description of an observable behavior. Generate a draft deterministic metric with its tests and a trace-based grading rubric with anchored examples. Write drafts outside the registered metrics and test the output with a stub generator.
2. Collect human labels for accepted and rejected behavior. Tune the rule, rubric, or threshold using development cases. Freeze those settings before evaluating held-out scenario families. Validate that a scenario family appears in one split only.
3. Record the metric version, rubric, threshold, case counts, agreement, false passes, and false failures. Include example disagreements that a reviewer can inspect. Enable a metric by default through a separate reviewed change after the calibration evidence is available.

Verify that generation leaves current default suites unchanged. Add a small test set where both types of error occur and assert both counts. Include the calibration procedure and results in the PR.

## #11 Import one Harbor-format run

1. Select one runnable task and pin its revision. Choose native Harbor or Inspect AI with `inspect-harbor` according to which runner can execute that task and export usable evidence. Record the runner and its version.
2. Save a small shareable artifact fixture. Write the importer against that version's artifact format. Preserve task version, trial or sample ID, verifier outcomes, ordered trajectory, and observed telemetry. Represent missing optional telemetry explicitly. Treat missing required evidence as an import error.
3. Test the importer with the saved artifact, missing required data, and a run with missing optional telemetry. Document the exact capture, import, and replay commands. Reuse the current metric registry and the promotion path from #9.

Run the import and replay with no runner credentials using the saved artifact. Compare the resulting verifier outcomes and call order to the source. Verify that one passing imported run can produce a promotion proposal.

## #4 Require CI on main

1. Check the current GitHub ruleset before making changes. If your connector lacks ruleset access, leave the issue open and record the missing permission.
2. If you have access, apply an active ruleset to `main` that requires a PR and the GitHub Actions `tests` check. Keep the bypass list empty.
3. Verify the rule in repository settings and link a PR with a passing check. Confirm GitHub lists the check as required for merging. Close the issue after both the settings and the check are verified.

## #12 Publish the first runnable release

1. From a clean checkout of the release commit, run the test suite and both README smoke commands. Run the deliberate coding failure from the README and confirm exit `1` and the failed regression check in the JSON report.
2. Prepare release notes that link one passing report and the deliberate failure report. Document the Python version and exact replay commands. Review those instructions in a PR before tagging.
3. Tag the merged release commit and publish the release with the reports. Link the release from the README via a PR and close #12 once the release link and artifacts work.
