import unittest

from scripts.sync_roadmap import sync_roadmap


REPOSITORY = "example/evals"
ROADMAP = [
    {
        "id": "test-roadmap",
        "title": "Test roadmap",
        "body": "Track work.",
        "tasks": [{"id": "test-task", "title": "Add a metric", "body": "Check results."}],
    }
]


class FakeGitHub:
    def __init__(self, pages=None):
        self.pages = pages if pages is not None else [[]]
        self.created = []

    def __call__(self, method, path, payload=None, paginate=False):
        if method == "GET":
            if path != f"repos/{REPOSITORY}/issues?state=all&per_page=100" or not paginate:
                raise AssertionError("Include all issues across pages")
            return self.pages
        if method != "POST" or path != f"repos/{REPOSITORY}/issues":
            raise AssertionError(f"Unexpected request {method} {path}")
        issue_id = 100 + len(self.created)
        self.created.append(payload)
        issue = {**payload, "id": issue_id, "number": issue_id - 90}
        self.pages[-1].append(issue)
        return issue


class SyncRoadmapTests(unittest.TestCase):
    def test_creates_parent_and_subissue_and_can_run_twice(self):
        github = FakeGitHub()

        self.assertEqual(sync_roadmap(ROADMAP, REPOSITORY, github), 2)
        self.assertEqual(sync_roadmap(ROADMAP, REPOSITORY, github), 0)
        self.assertEqual(len(github.created), 2)
        self.assertNotIn("parent_issue_id", github.created[0])
        self.assertEqual(github.created[1]["parent_issue_id"], 100)
        self.assertIn("Roadmap ID `test-task`", github.created[1]["body"])

    def test_a_closed_issue_on_a_later_page_is_left_alone(self):
        github = FakeGitHub([
            [{"id": 30, "body": "Roadmap ID `test-roadmap`"}],
            [{"id": 31, "state": "closed", "body": "Updated details.\nRoadmap ID `test-task`"}],
        ])

        self.assertEqual(sync_roadmap(ROADMAP, REPOSITORY, github), 0)
        self.assertEqual(github.created, [])

    def test_a_partial_sync_can_resume_using_existing_parent(self):
        github = FakeGitHub([[{"id": 30, "body": "Roadmap ID `test-roadmap`"}]])

        self.assertEqual(sync_roadmap(ROADMAP, REPOSITORY, github), 1)
        self.assertEqual(github.created[0]["parent_issue_id"], 30)

    def test_a_pull_request_with_a_tracking_id_is_not_an_issue(self):
        github = FakeGitHub([[
            {"id": 30, "body": "Roadmap ID `test-roadmap`"},
            {"id": 31, "pull_request": {}, "body": "Roadmap ID `test-task`"},
        ]])

        self.assertEqual(sync_roadmap(ROADMAP, REPOSITORY, github), 1)
        self.assertEqual(github.created[0]["parent_issue_id"], 30)

    def test_duplicate_manifest_ids_fail_before_creating_issues(self):
        github = FakeGitHub()

        with self.assertRaisesRegex(ValueError, "Duplicate roadmap ID"):
            sync_roadmap(ROADMAP + ROADMAP, REPOSITORY, github)

        self.assertEqual(github.created, [])
