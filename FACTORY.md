# Maintainer automation

The Claude Mention Handler accepts explicit requests in issue and same-repository PR conversation comments.
To request an implementation, comment `@claude implement this issue and open a draft PR`.
Continue in the draft PR's conversation to reuse its branch.

The caller pins the [shared Pixi workflow](https://github.com/neuralsignal/agentic-engineering-kit/blob/c1d65d9ec77c90350465affd2b68acca6a677fe8/.github/workflows/maintainer-claude-pixi.yml).
It uses the existing repository `CLAUDE_CODE_OAUTH_TOKEN` and `FACTORY_PAT` secrets.

CI, Docs, Release Please and PyPI publishing retain their existing triggers and checks.

## Dependency updates

Dependabot opens weekly pull requests for GitHub Actions. Require green PR checks before merging.
Pixi remains authoritative for Python dependencies. Review and commit changes to `pixi.toml` and
`pixi.lock` together when those files change. Regenerate a conflicted lockfile through Pixi.

## Verify or roll back

The pilot produced one draft PR with green lint, tests and docs. Release Please also passed on main.
[Maintainer run](https://github.com/neuralsignal/obsidian-import/actions/runs/44329349075) · [Pilot draft PR](https://github.com/neuralsignal/obsidian-import/pull/402)

Revert the migration commit to restore the previous workflow definitions. In GitHub Actions,
restore only the historical workflow states needed for rollback. Leave the release credentials
and deployment settings in place.
