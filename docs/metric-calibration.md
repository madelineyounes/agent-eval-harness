# Draft and calibrate a metric

Describe an observable behavior and name the tool involved. Generate a starter evaluator, failing tests, and an anchored trace rubric in a staging directory.

```sh
python -m agent_eval draft-metric --id catalog-lookup-quality --behavior "Check whether the answer uses catalog lookup evidence" --tool lookup --output artifacts/metric-drafts
python -m unittest discover -s artifacts/metric-drafts/catalog-lookup-quality -v
```

Review the draft tests and confirm that they fail at the evaluator stub. Fill in the observable rule and rerun them. The draft stays outside the metric registry. Review the rubric anchors against concrete traces before scoring cases.

## Freeze the threshold before held-out evaluation

Collect pass or fail labels from people who can verify the traces. Record their annotation process in `label_provenance`. Assign each case to a scenario family and keep related variants in one split. Use development labels to revise the proposed rule and rubric. Score the labeled cases with the frozen versions and record one score per case.

```sh
python -m agent_eval calibrate-metric --labels examples/calibration-v1/scores.json
```

The command selects a development threshold that maximizes agreement, then favors fewer false passes and a higher threshold in ties. It applies the selected threshold to the held-out scores and lists disagreements by case ID. The synthetic example selects `0.75`. Development agrees on both cases. Held-out agreement is one of three, with one false pass and one false failure.

Review human-labeled calibration results in a PR before enabling a candidate metric by default. The example uses synthetic labels to exercise reporting.

## Human-labeled search-step calibration

`search-result-query-overlap` version `1` scores the fraction of distinct query terms of at least three characters that appear in the recorded result. It matches calls and results by call ID. The `search-step-progress-v1` rubric uses AgentProcessBench's expert labels. A step that advanced progress passes. An incorrect step fails. The sample uses single `search` calls and excludes neutral labels. HotpotQA supplies development and GAIA supplies held-out cases, keeping each source family in one split. [AgentProcessBench annotation and data](https://arxiv.org/abs/2603.14465)

| Split | Labeled steps | Agreement | False passes | False failures |
| --- | ---: | ---: | ---: | ---: |
| HotpotQA development | 395 | 82.78% | 65 | 3 |
| GAIA held-out | 522 | 69.16% | 158 | 3 |

The development threshold is `0.25`. Held-out case `gaia_dev:250:10` scored `1.0` on overlap and the expert label was fail. Case `gaia_dev:252:2` scored `0.0` and the expert label was pass. Term overlap is a weak proxy for whether a step advances the task. Keep this metric in the calibration example.

To reproduce the counts, download `hotpotqa.jsonl` and `gaia_dev.jsonl` from the pinned dataset directory into `artifacts/agentprocessbench`. The extractor writes case IDs, split assignments, scores, and labels. [Pinned AgentProcessBench files](https://github.com/RUCBM/AgentProcessBench/tree/0a42606b178a8c69d40c5765dc05c342f921e578/data/AgentProcessBench)

```sh
python examples/calibration-v1/measure_search_steps.py artifacts/agentprocessbench --output artifacts/search-calibration-labels.json
python -m agent_eval calibrate-metric --labels artifacts/search-calibration-labels.json
```
