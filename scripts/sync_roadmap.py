import argparse
import json
import re
import subprocess
from pathlib import Path


ROADMAP_ID = re.compile(r"Roadmap ID `([a-z0-9-]+)`")


def github_api(method, path, payload=None, paginate=False):
    command = [
        "gh", "api", "--method", method,
        "--header", "X-GitHub-Api-Version: 2026-03-10",
    ]
    if paginate:
        command.extend(("--paginate", "--slurp"))
    if payload is not None:
        command.extend(("--input", "-"))
    completed = subprocess.run(
        [*command, path],
        input=json.dumps(payload) if payload is not None else None,
        stdout=subprocess.PIPE,
        encoding="utf-8",
        check=True,
    )
    return json.loads(completed.stdout)


def validate_roadmap(roadmap):
    ids = set()
    for parent in roadmap:
        for entry in (parent, *parent["tasks"]):
            key = entry["id"]
            if key in ids:
                raise ValueError(f"Duplicate roadmap ID {key}")
            if not ROADMAP_ID.fullmatch(f"Roadmap ID `{key}`"):
                raise ValueError(f"Invalid roadmap ID {key}")
            ids.add(key)


def sync_roadmap(roadmap, repository, api):
    validate_roadmap(roadmap)
    endpoint = f"repos/{repository}/issues"
    pages = api("GET", f"{endpoint}?state=all&per_page=100", paginate=True)
    existing = {}
    for page in pages:
        for issue in page:
            if "pull_request" in issue:
                continue
            for line in (issue.get("body") or "").splitlines():
                match = ROADMAP_ID.fullmatch(line.strip())
                if match:
                    key = match[1]
                    if key in existing:
                        raise ValueError(f"Duplicate GitHub issue for roadmap ID {key}")
                    existing[key] = issue["id"]

    created = 0

    def ensure_issue(entry, parent_id=None):
        nonlocal created
        key = entry["id"]
        if key in existing:
            return existing[key]
        payload = {
            "title": entry["title"],
            "body": f"{entry['body']}\n\nRoadmap ID `{key}`",
        }
        if parent_id is not None:
            payload["parent_issue_id"] = parent_id
        issue = api("POST", endpoint, payload=payload)
        print(f"Created #{issue['number']} {entry['title']}")
        created += 1
        return issue["id"]

    for parent in roadmap:
        parent_id = ensure_issue(parent)
        for task in parent["tasks"]:
            ensure_issue(task, parent_id)
    return created


def main():
    parser = argparse.ArgumentParser(description="Create missing GitHub roadmap issues.")
    parser.add_argument("--repository", required=True, help="GitHub repository as owner/name.")
    parser.add_argument("--manifest", type=Path, default=Path(".github/roadmap.json"))
    args = parser.parse_args()
    roadmap = json.loads(args.manifest.read_text(encoding="utf-8"))
    created = sync_roadmap(roadmap, args.repository, github_api)
    print(f"Created {created} roadmap issues.")


if __name__ == "__main__":
    main()
