# Replay labeled PR reviews

Both synthetic PR diffs apply to the same [catalog baseline](catalog.py). The [clean diff](clean.patch) names the result of a membership check before returning it. The [defective diff](defective.patch) changes how the catalog handles empty strings. The [review prompt and responses](reviews.md) are curated examples, including a deliberately faulty control.

| Function | Minimal input | Baseline and clean behavior | Defective behavior |
| --- | --- | --- | --- |
| `store` | Call `store(catalog, "sku", "")` with `catalog = {}`. | The catalog contains `{"sku": ""}`. | The catalog stays empty. |
| `has_key` | Call `has_key({"sku": ""}, "sku")`. | Returns `True`. | Returns `False`. |

## Map review comments to finding keys

Read the diff and reproduce each alleged regression. Record each actionable claim as a key with the repository-relative path, function name, and behavior ID. Match wording variants to the same key. Keep one entry per comment so replay can count duplicates. Give an unsupported actionable claim its own key so replay can count the false positive. Omit praise and general advice that identify no defect.

| Response | Comment | Key |
| --- | --- | --- |
| Clean diff | No actionable finding | Empty list |
| Defective diff | 1 | `["catalog.py", "store", "drops-empty-value"]` |
| Defective diff | 2 | `["catalog.py", "has_key", "ignores-present-empty-value"]` |
| Synthetic control | 1 and 2 | `["catalog.py", "store", "drops-empty-value"]` twice |
| Synthetic control | 3 | `["catalog.py", "store", "lowercases-keys"]` |

The expected labels come from the two reproduced defects. The lowercase claim is unsupported because `store` still uses the supplied key when it writes a nonempty value.

## Run the examples

From the repository root, run both replays.

```sh
python -m agent_eval --suite examples/review-v1/passing.json --report artifacts/review-v1-pass.json
python -m agent_eval --suite examples/review-v1/control.json --report artifacts/review-v1-control.json
```

The passing suite exits `0`. The control exits `1`. Its `review-findings` details record one true positive, one false positive, one false negative, and one duplicate. Precision and recall are both `0.5`. The `missed` list names the membership defect and the `unexpected` list names the lowercase claim.
