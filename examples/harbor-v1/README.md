# Import a Harbor trial

This example uses native Harbor `0.23.0` and ATIF `v1.8`. The task creates `hello.txt` while preserving `existing.txt`. Its task files pin revision `1.0.0`. Harbor records the task checksum on each trial. The checked-in trial is a compact synthetic fixture for offline testing. The **Capture Harbor example** workflow runs the task in Docker and saves the runner's original artifacts.

## Capture a trial

On Linux with Docker available, install the pinned runner and run the scripted agent. The agent makes no model requests. It records its two shell calls and their observed results in ATIF.

```sh
python -m pip install harbor==0.23.0
PYTHONPATH=examples/harbor-v1 harbor trials start --path examples/harbor-v1/hello-file --agent scripted_hello:ScriptedHelloAgent --trial-name scripted --trials-dir artifacts/harbor-trials
```

The no-op baseline earns `0` for creating `hello.txt` and `1` for preserving the existing file. The scripted trial earns `1` for both. The verifier writes these independent outcomes as named rewards.

## Replay a saved trial

```sh
python -m agent_eval import-harbor --trial examples/harbor-v1/saved-trial --dataset examples/harbor-v1/dataset --case-id hello-file --output artifacts/harbor-suite.json
python -m agent_eval --suite artifacts/harbor-suite.json --report artifacts/harbor-report.json
python -m agent_eval promote --dataset examples/harbor-v1/dataset --report artifacts/harbor-report.json --run-id 9cd27316-8456-5b1c-9a24-614a65642fd5 --reason "Verified named Harbor rewards" --output artifacts/harbor-proposal
```

The import reads `result.json` and `agent/trajectory.json`. It keeps trial metadata, the original reward values, and the original trajectory. It maps named rewards `1` and `0` to `passed` and `failed` for the existing `patch-verification` metric. It matches each observed tool result by call ID and keeps tool calls in their original order for `loop-detection`. Unavailable optional telemetry appears as `null`. The importer supports standalone single-trial ATIF v1.8 artifacts. To replay a new capture, use its trial directory, a fresh output path, and the run ID printed in the report.

[Harbor v0.23.0 source and release](https://github.com/harbor-framework/harbor/releases/tag/v0.23.0)
