# Track roadmap work in GitHub Issues

The `Sync roadmap issues` workflow creates two parent issues and their sub-issues when the roadmap first lands on `main`. Edit `.github/roadmap.json` through a PR to add planned work. The workflow also accepts a manual run from `main`.

Keep each issue's Roadmap ID in its description. The workflow uses that ID to find existing open and closed issues. You can edit issue titles, descriptions, and status on GitHub.

Put `Closes #42` in a PR description when the PR satisfies the issue. For work in another portfolio repo, use `Closes madelineyounes/agent-eval-harness#42`. When the PR merges into its repo's default branch, GitHub closes the issue and updates its parent roadmap's progress. Use a plain issue link for a PR that completes part of the work. [GitHub PR closing keywords](https://docs.github.com/en/issues/tracking-your-work-with-issues/using-issues/linking-a-pull-request-to-an-issue) [GitHub sub-issues](https://docs.github.com/en/issues/tracking-your-work-with-issues/using-issues/adding-sub-issues)

For profile pins, résumé edits, and other work that happens outside a PR, close the issue on GitHub once the result is verified.
