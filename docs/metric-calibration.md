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
