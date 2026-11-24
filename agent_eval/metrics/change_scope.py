def paths(record, field):
    values = record.get(field)
    if not isinstance(values, list):
        raise ValueError(f"{field} must be a list of repository-relative paths")
    for value in values:
        if (
            not isinstance(value, str)
            or any(char in value for char in ("\\", ":", "\0"))
            or any(part in ("", ".", "..") for part in value.split("/"))
        ):
            raise ValueError(f"Invalid path in {field}: {value!r}")
    return set(values)


def evaluate(expected, run):
    allowed = paths(expected, "allowed_paths")
    changed = paths(run, "changed_paths")
    unexpected = sorted(changed - allowed)
    return {
        "status": "fail" if unexpected else "pass",
        "reason": "Patch changed paths outside the allowlist" if unexpected else "All changed paths are allowed",
        "details": {"unexpected_paths": unexpected},
    }
