---
name: release
description: Prepare a new release for the pipelex-starter-python project. Bumps version in pyproject.toml, syncs uv.lock, updates CHANGELOG.md, manages the release/vX.Y.Z branch, runs lint/type checks and tests, and commits. Use when the user says "release", "prepare a release", "bump version", "new version", "cut a release", or "ship it". The user can optionally provide changelog content inline (e.g. "/release Added foo, fixed bar"), which becomes the entry for this version.
---

# Release Workflow

Guides the user through preparing a new pipelex-starter-python release in 8 interactive steps. Every step requires explicit user confirmation before proceeding.

This is a **starter template, not a published package** — there is no PyPI publish. The release is cut by merging the `release/vX.Y.Z` PR into `main`: `github-release.yml` then creates a GitHub Release `vX.Y.Z` from the changelog notes. So the branch name, the `pyproject.toml` version, and the `CHANGELOG.md` heading must line up exactly, or CI blocks the PR.

## Step 1 — Gather State

Read the following and present a summary:

1. Current version from `pyproject.toml` (`version = "X.Y.Z"`, near the top of the `[project]` table)
2. Latest entry in `CHANGELOG.md`
3. Current git branch (`git branch --show-current`)
4. Working tree status (`git status --short`)

If the working tree is dirty, **warn the user** and ask whether to continue, commit those changes as part of the release, or abort. Also run `git log origin/main..HEAD --oneline` to list commits that will ship with this release so the user knows what's included.

## Step 2 — Determine Target Version

Calculate the three semver bump options from the current version:

- **Patch**: `X.Y.Z+1`
- **Minor**: `X.Y+1.0`
- **Major**: `X+1.0.0`

Present these options to the user using `AskUserQuestion`, showing the concrete resulting version for each. If the current branch already looks like `release/vA.B.C` and the version in `pyproject.toml` was already bumped, offer a **"Keep current (A.B.C)"** option.

Store the chosen version as `TARGET_VERSION` (no `v` prefix, e.g. `0.9.0`).

## Step 3 — Branch Management

The release branch **must** be named `release/v{TARGET_VERSION}`. `guard-branches.yml` rejects any other source branch merging into `main`, and `version-check.yml` requires the branch version to match `pyproject.toml`, so this name is not optional.

- If already on the correct branch: inform the user and continue.
- If on `dev`, `main`, or another branch: confirm with the user, then create and switch to `release/v{TARGET_VERSION}` from the current HEAD.
- If on a *different* release branch: warn the user and ask how to proceed.

All version, changelog, and lock changes must be made **on this branch**.

## Step 4 — Update Version in pyproject.toml

Edit the `version = "..."` line in `pyproject.toml` to `version = "{TARGET_VERSION}"`. Only change the version field — don't touch anything else.

- If the version already matches: inform the user and skip.
- Otherwise: use the Edit tool to make the change, then show the diff.

The version in `pyproject.toml` must **not** have a `v` prefix (e.g. `0.9.0`, not `v0.9.0`).

## Step 5 — Sync uv.lock

After updating `pyproject.toml`, regenerate the lock file so it reflects `TARGET_VERSION`:

```bash
make li
```

`make li` runs `uv lock` then `uv sync` (lock + install). CI's `package-check.yml` runs `uv lock --locked` and fails the PR if `uv.lock` is out of date, so this step is what keeps that check green. If you only need to refresh the lock without reinstalling, `uv lock` alone is sufficient.

- **If the lock file was already in sync**: inform the user and continue.
- **On failure**: show the error and ask the user how to proceed.

## Step 6 — Update CHANGELOG.md

The changelog entry **must** match the CI grep pattern (`changelog-check.yml`): `## [vX.Y.Z] -`

Check if `CHANGELOG.md` already contains a `## [v{TARGET_VERSION}] -` entry.

- **If it exists**: show the existing entry and ask the user whether to keep it or edit it.

- **If it's missing**: draft a new entry and insert it directly after the `# Changelog` heading (newest entry on top), formatted as:

  ```markdown
  ## [v{TARGET_VERSION}] - {TODAY'S DATE in YYYY-MM-DD}

  - Item one
  - Item two
  ```

  Source the content, in priority order:
  1. **Inline content** the user passed when invoking the skill (e.g. `/release Bumped pipelex to 0.32.0`) — use it as the entry body.
  2. Otherwise, run `git log main..HEAD --oneline` (or `git log --oneline -20` if on `main`) to review recent commits and draft an entry from them.

  Match the existing changelog style — plain bullets, as in the current entries. You may group under `### Added` / `### Changed` / `### Fixed` / `### Removed` subsections if the content clearly warrants it, but only include subsections that have content. The user may accept, edit, or rewrite the proposed entry.

This project does **not** use an `## [Unreleased]` placeholder — never add one. The changelog should only contain concrete version entries.

## Step 7 — Run Checks

Run the same gates CI enforces on the PR. Both are silent on success and only show output on failure:

```bash
make agent-check    # ruff format + lint, pyright, mypy (mirrors lint-check.yml)
make agent-test     # tests, excludes inference/LLM markers (mirrors tests-check.yml)
```

`make agent-check` auto-formats with ruff, so it may modify files — include any resulting changes in the release commit.

- **On success**: report and continue.
- **On failure**: show the errors and ask the user how to proceed (fix the issues, skip the check, or abort). Prefer fixing — a failing gate here means the PR's `lint-check` / `tests-check` will fail too.

## Step 8 — Review & Commit

Present a full summary:

- Target version: `v{TARGET_VERSION}`
- Branch: `release/v{TARGET_VERSION}`
- Files changed: `pyproject.toml`, `uv.lock`, `CHANGELOG.md` (plus any formatting changes from `make agent-check`, or other files the user chose to include in Step 1)
- Changelog entry preview

Ask the user to confirm. On confirmation:

1. Stage **only** the release files — `pyproject.toml`, `uv.lock`, `CHANGELOG.md`, plus any formatting changes from the checks and any files the user explicitly chose to include. Never use `git add .` or `git add -A`.
2. Commit with message: `Release v{TARGET_VERSION}: <one-line changelog summary>`
3. Show the commit result.

Then offer (but do **not** automatically execute):

- **Push** the branch to origin: `git push -u origin release/v{TARGET_VERSION}`
- **Create a PR** to `main`: `gh pr create --base main --title "Release/v{TARGET_VERSION}" --body "<changelog entries for this version>"`

Wait for explicit user approval before pushing or creating the PR. When you do create the PR, target `main`, title it `Release/v{TARGET_VERSION}`, and put the changelog entries for this version in the body. Report the PR URL back to the user.

## Rules

- Never use `git add .` or `git add -A` — stage only the release files (and any changes the user explicitly opted into).
- Never push or create PRs without explicit user approval.
- The `v` prefix appears in branch names, changelog headers, and the GitHub Release tag, but **not** in `pyproject.toml`.
- Always use today's date for new changelog entries (format: `YYYY-MM-DD`; run `date +%F` if unsure).
- Merging the `release/vX.Y.Z` PR into `main` is what ships — `github-release.yml` creates the GitHub Release on push to `main`. There is no PyPI publish; this is a starter template.
- If any step fails or the user wants to abort, stop immediately — do not continue the workflow.
