# Maintainer automation pilot

The Claude Mention Handler accepts explicit requests in issue and PR conversation comments. For implementation, comment `@claude implement this issue and open a draft PR`. Use one issue thread per task. The action owns the resulting PR.

The pilot uses the existing `CLAUDE_CODE_OAUTH_TOKEN` and `FACTORY_PAT` secrets. Confirm the GitHub credential is scoped to this repository and produces PRs whose CI runs. The reusable workflow can use the Claude GitHub App after its access has been verified. During rollout, keep release automation's existing credentials configured.

The latest sampled issue-implementation run already had a PR for the implementation branch. A separate shell step tried to open it again and marked the issue blocked. A sampled branch-sync run also failed in Pixi setup because it enabled caching while skipping environment installation. The pilot replaces the duplicate PR lifecycle with one explicit entry point. [Issue implementation run](https://github.com/neuralsignal/obsidian-import/actions/runs/44225197277) · [Branch sync run](https://github.com/neuralsignal/obsidian-import/actions/runs/44106285697)

## Verify before retiring the old workflows

1. Verify PR lint, tests, and coverage. Check the docs build and release settings. Record the current workflow states and release reference for rollback.
2. Ask Claude a question on a disposable issue. Then request a small draft PR and confirm the PR's CI starts. Continue in the draft PR's conversation to reuse its branch.
3. Run the smoke request through the pinned Agentic Engineering Kit caller and confirm the run uses that revision.
4. Disable the retired workflows after the pilot passes. Keep `ci.yml`, `docs-deploy.yml`, `release.yml`, `publish.yml`, and `claude-mention.yml` active.

Retire `code-quality.yml`, `dep-audit.yml`, `docs-freshness.yml`, `docs-update.yml`, `factory-orchestrator.yml`, `issue-implement.yml`, `issue-triage.yml`, `pr-autofix.yml`, `pr-branch-sync.yml`, `pr-code-review.yml`, `pr-docs-check.yml`, `security-scan.yml`, `test-coverage.yml`, and `workflow-upgrade.yml`. Review the enabled check names before removal. The original files remain available during the pilot.

Dependabot refreshes GitHub Actions weekly. Pixi remains authoritative for Python dependencies. Review and commit `pixi.toml` and `pixi.lock` together when they change.

For rollback, restore the preceding Claude workflow revision and re-enable the previously active legacy workflows that are needed. Confirm that the CI and release workflow states still match the pre-pilot record.
