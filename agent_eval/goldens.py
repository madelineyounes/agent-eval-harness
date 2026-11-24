import json
import re
from collections import Counter
from hashlib import sha256
from pathlib import Path
from tempfile import NamedTemporaryFile


SPLITS = ("development", "held-out")


def read(path):
    return json.loads(path.read_text(encoding="utf-8"))


def nonempty(value):
    return isinstance(value, str) and bool(value.strip())


def case_path(root, case_id):
    if not isinstance(case_id, str) or re.fullmatch(r"[a-z0-9][a-z0-9_-]*", case_id) is None:
        raise ValueError(f"Invalid case ID {case_id!r}")
    path = root / "cases" / f"{case_id}.json"
    if not path.resolve().is_relative_to(root.resolve()):
        raise ValueError(f"Case path escapes dataset: {case_id}")
    return path


def validate_case(case, case_id, split):
    if not isinstance(case, dict) or case.get("id") != case_id or case.get("split") != split:
        raise ValueError(f"Case file must match manifest ID and split: {case_id}")
    if case.get("group") not in ("main", "edge") or not all(nonempty(case.get(key)) for key in ("prompt", "scenario_family")):
        raise ValueError(f"Case {case_id} needs a group, scenario family, and prompt")
    provenance = case.get("provenance")
    if (not isinstance(provenance, dict) or provenance.get("source") not in ("real", "synthetic")
            or not nonempty(provenance.get("origin"))):
        raise ValueError(f"Case {case_id} needs source and origin provenance")
    if provenance["source"] == "real" and "generator" in provenance:
        raise ValueError(f"Generated case {case_id} must keep synthetic provenance")
    if not isinstance(case.get("expected"), dict) or case.get("review_status", "approved") != "approved":
        raise ValueError(f"Case {case_id} needs reviewed expectations")


def load_dataset(root, split=None):
    root = Path(root)
    manifest = read(root / "manifest.json")
    if (not isinstance(manifest, dict) or manifest.get("schema_version") != 1
            or not nonempty(manifest.get("dataset_version"))):
        raise ValueError("Dataset requires schema_version 1 and a dataset_version")
    splits = manifest.get("splits")
    metrics = manifest.get("metrics")
    if (not isinstance(splits, dict) or splits.keys() != set(SPLITS)
            or not all(isinstance(splits[name], list) for name in SPLITS)):
        raise ValueError("Dataset must declare development and held-out case lists")
    if not isinstance(metrics, list) or not metrics or not all(nonempty(metric) for metric in metrics):
        raise ValueError("Dataset requires a list of metric IDs")
    if split is not None and split not in SPLITS:
        raise ValueError(f"Unknown dataset split {split}")

    cases = {}
    families = {}
    for name in SPLITS:
        for case_id in splits[name]:
            path = case_path(root, case_id)
            if case_id in cases:
                raise ValueError(f"Duplicate case ID {case_id}")
            case = read(path)
            validate_case(case, case_id, name)
            family = case["scenario_family"]
            if families.setdefault(family, name) != name:
                raise ValueError(f"A scenario family belongs to both splits: {family}")
            cases[case_id] = case

    counts = Counter(case["provenance"]["source"] for case in cases.values())
    warning = "Dataset has fewer than two real goldens per synthetic golden" if counts["real"] < 2 * counts["synthetic"] else None
    return {
        "dataset_version": manifest["dataset_version"],
        "metrics": metrics,
        "cases": [case for case in cases.values() if split is None or case["split"] == split],
        "source_balance": {"real": counts["real"], "synthetic": counts["synthetic"], "warning": warning},
    }


def staging_root(root, output):
    output = Path(output).resolve()
    root = Path(root).resolve()
    if output.is_relative_to(root) or root.is_relative_to(output):
        raise ValueError("Choose a staging directory separate from the active dataset")
    return output


def write_proposal(output, path, value):
    if not path.resolve().is_relative_to(output):
        raise ValueError(f"Proposal path escapes the staging directory: {path}")
    path.parent.mkdir(parents=True, exist_ok=True)
    with NamedTemporaryFile(mode="w", encoding="utf-8", newline="\n", dir=path.parent, delete=False) as handle:
        temporary = Path(handle.name)
    try:
        temporary.write_text(json.dumps(value, indent=2) + "\n", encoding="utf-8", newline="\n")
        try:
            path.hardlink_to(temporary)
        except FileExistsError:
            if read(path) != value:
                raise ValueError(f"A different draft already exists at {path}") from None
    finally:
        temporary.unlink()


def seed_variant(seed):
    return {"prompt": f"Give a concise response. {seed['prompt']}", "expected": seed["expected"]}


def draft(root, seed_ids, output, generator=seed_variant, *, configuration=None):
    dataset = load_dataset(root)
    output = staging_root(root, output)
    seeds = {case["id"]: case for case in dataset["cases"] if case["split"] == "development"}
    proposals = []
    for seed_id in dict.fromkeys(seed_ids):
        if seed_id not in seeds:
            raise ValueError(f"Unknown development seed {seed_id}")
        seed = seeds[seed_id]
        generated = generator(seed)
        if not isinstance(generated, dict) or not nonempty(generated.get("prompt")) or not isinstance(generated.get("expected"), dict):
            raise ValueError(f"Generator did not propose a prompt and expectations for {seed_id}")
        generated_id = f"{seed_id}-concise-draft"
        if generated_id in seeds:
            raise ValueError(f"Generated case ID already exists: {generated_id}")
        path = output / f"{generated_id}.json"
        write_proposal(output, path, {
            "id": generated_id, "prompt": generated["prompt"], "expected": generated["expected"],
            "group": seed["group"], "scenario_family": seed["scenario_family"], "split": "development",
            "review_status": "draft",
            "provenance": {"source": "synthetic", "origin": dataset["dataset_version"], "seed_ids": [seed_id],
                           "generator": configuration or {"name": getattr(generator, "__name__", type(generator).__name__), "version": "1"}},
        })
        proposals.append(path)
    return proposals


def draft_document(root, source, document_id, output):
    root, source = Path(root), Path(source)
    case_path(root, document_id)
    dataset = load_dataset(root)
    output = staging_root(root, output)
    if not set(dataset["metrics"]) <= {"tool-call-contract", "response-expectations"}:
        raise ValueError("Document drafts require a dataset with documentation lookup metrics")
    case_id = f"doc-{document_id}-draft"
    if any(case["id"] == case_id for case in dataset["cases"]):
        raise ValueError(f"Generated case ID already exists: {case_id}")
    content = source.read_bytes()
    excerpt = next((line.strip() for line in content.decode("utf-8-sig").splitlines() if line.strip()), "")
    if not excerpt:
        raise ValueError("The approved document needs a nonempty first line")
    proposal = output / f"{case_id}.json"
    write_proposal(output, proposal, {
        "id": case_id, "prompt": f"What does the {document_id} document say?",
        "split": "development", "group": "main", "scenario_family": f"documentation-{document_id}",
        "review_status": "draft", "capture": {"document_id": document_id},
        "expected": {"answer_contains": [excerpt], "required_calls": [{"tool": "lookup_doc", "arguments": {"id": document_id}}]},
        "provenance": {"source": "synthetic", "origin": source.name, "source_sha256": sha256(content).hexdigest(),
                       "generator": {"name": "document-first-line", "version": "1"}},
    })
    return proposal


def promote(root, report, run_id, output, reason, *, reviewed_case=None, excerpt=None):
    root = Path(root)
    dataset = load_dataset(root)
    output = staging_root(root, output)
    if (not isinstance(report, dict) or report.get("schema_version") != 1
            or not nonempty(report.get("dataset_version")) or not isinstance(report.get("cases"), list)
            or not nonempty(run_id) or not nonempty(reason)):
        raise ValueError("Promotion requires a versioned report, run ID, and review reason")
    matches = [case for case in report["cases"] if isinstance(case, dict) and case.get("run_id") == run_id]
    if len(matches) != 1:
        raise ValueError("Promotion requires exactly one report case for the run ID")
    observed = matches[0]
    case_id = observed.get("id")
    case_path(root, case_id)
    cases = {case["id"]: case for case in dataset["cases"]}
    case = cases.get(case_id)
    if case is None:
        if not isinstance(reviewed_case, dict) or reviewed_case.get("review_status") != "approved":
            raise ValueError("New cases require independently reviewed expectations and approved provenance")
        case = {**reviewed_case, "split": "development"}
        validate_case(case, case_id, "development")
        if any(item["scenario_family"] == case["scenario_family"] and item["split"] == "held-out" for item in cases.values()):
            raise ValueError("A new development case cannot reuse a held-out scenario family")
    elif report["dataset_version"] != dataset["dataset_version"]:
        raise ValueError("Existing-case promotions require the current dataset revision")

    run, results = observed.get("run"), observed.get("metrics")
    required = dataset["metrics"]
    if (not isinstance(run, dict) or run.get("id") != run_id or run.get("execution_error")
            or not nonempty(run.get("agent_version")) or not isinstance(results, dict)
            or not all(isinstance(results.get(metric), dict) and results[metric].get("status") == "pass"
                       and nonempty(results[metric].get("metric_version")) for metric in required)):
        raise ValueError("Promotion requires successful execution and passing versioned results for all required metrics")
    if excerpt is not None and not isinstance(excerpt, dict):
        raise ValueError("An approved excerpt must be a JSON object")

    references = case.get("references", [])
    if not isinstance(references, list) or not all(isinstance(reference, dict) for reference in references):
        raise ValueError("Case references must be a list of objects")
    if not any(reference.get("run_id") == run_id for reference in references):
        reference = {
            "run_id": run_id, "source_dataset_version": report["dataset_version"], "agent_version": run["agent_version"],
            "metric_versions": {metric: results[metric]["metric_version"] for metric in required}, "reason": reason,
        }
        if excerpt is not None:
            reference["excerpt"] = excerpt
        references = [*references, reference]

    proposal = output / case_id / sha256(run_id.encode()).hexdigest()[:16]
    path = case_path(proposal, case_id)
    write_proposal(output, path, {**case, "references": references})
    if case_id not in cases:
        manifest = read(root / "manifest.json")
        manifest["splits"]["development"].append(case_id)
        write_proposal(output, proposal / "manifest.json", manifest)
    return path
