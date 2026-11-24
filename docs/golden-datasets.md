# Manage golden datasets

Keep a `manifest.json` and one `cases/<id>.json` per case in Git. Use `--dataset` for the same format in a private checkout. The manifest lists case IDs for each split, the required metric IDs, and the dataset revision. Each case carries its prompt, expected behavior, main or edge group, scenario family, and provenance. Keep all variants of a scenario family in one split. Aim for roughly 80% main cases and 20% edge cases by case count.

Record `real` provenance for a case rooted in an observed user task or workflow. Record `synthetic` provenance for generated or curated examples, including reviewed generated variants. The report warns when the manifest contains fewer than two real cases for every synthetic case. Counts use distinct case IDs across the manifest. The public starter dataset contains one synthetic example.

## Replay and draft a variant

```sh
python -m agent_eval --dataset datasets/goldens --split development --report artifacts/goldens.json
python -m agent_eval draft-goldens --dataset datasets/goldens --seed clean-catalog-review --output artifacts/golden-drafts
```

The default generator asks for a concise response to a reviewed development seed. Each draft records the seed ID, source revision, generator, and proposed assertions. Verify those assertions against the task and check for duplicate behavior before approving a draft. Generated variants stay synthetic after review.

## Propose a promotion

```sh
python -m agent_eval promote --dataset datasets/goldens --report artifacts/goldens.json --run-id synthetic-clean-catalog-review-v1 --reason "Verified the clean diff" --output artifacts/golden-promotions
```

Use the saved report from a run with passing required metrics and a recorded agent version. The proposal retains existing assertions and records the run ID, source revision, agent version, metric versions, and review reason. To attach a trace excerpt, pass a reviewer-approved JSON object with `--excerpt-file`. The command writes files to the staging directory and prints their location. Repeating the same promotion keeps one reference per case and run.

For a new case, provide `--reviewed-case` with independently verified assertions, approved provenance, and `"review_status": "approved"`. The proposal places the case in development and includes a proposed manifest. Review the candidate in a PR, update the dataset revision when publishing the change, and keep held-out membership fixed for that revision. Store raw reports outside the dataset.
