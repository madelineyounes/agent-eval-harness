def findings(record, label):
    values = record.get("review_findings")
    if not isinstance(values, list):
        raise ValueError(f"{label} review_findings must be a list")
    for value in values:
        if (
            not isinstance(value, list)
            or len(value) != 3
            or not all(isinstance(part, str) and part.strip() for part in value)
        ):
            raise ValueError(f"{label} findings must contain a path, symbol, and issue ID")
    return [tuple(value) for value in values]


def evaluate(expected, run):
    golden = findings(expected, "Expected")
    expected_keys = set(golden)
    if len(expected_keys) != len(golden):
        raise ValueError("Expected review findings contain duplicate keys")

    observed = findings(run, "Observed")
    observed_keys = set(observed)
    matched = expected_keys & observed_keys
    unexpected = observed_keys - expected_keys
    missed = expected_keys - observed_keys
    duplicates = len(observed) - len(observed_keys)
    exact = not (unexpected or missed or duplicates)
    return {
        "status": "pass" if exact else "fail",
        "reason": "Findings match the reviewed labels" if exact else "Review findings differ from the reviewed labels",
        "details": {
            "true_positives": len(matched),
            "false_positives": len(unexpected),
            "false_negatives": len(missed),
            "duplicates": duplicates,
            "precision": len(matched) / len(observed_keys) if observed_keys else None,
            "recall": len(matched) / len(expected_keys) if expected_keys else None,
            "unexpected": sorted(unexpected),
            "missed": sorted(missed),
        },
    }
