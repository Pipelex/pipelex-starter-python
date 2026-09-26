# Changelog

## [Unreleased]

### Changed

- **The demos name their pipe by its qualified reference**: every demo command, in every mode, sends `pipe_code` as `domain.pipe_code` (`extract_entities.extract_entities`) rather than the bare code, the exact key the runtime resolves. A bare code is searched for across every domain of the bundle and fails as ambiguous once two domains declare it, so code copied from a demo keeps working as its bundle grows; rename a bundle's `domain` and its call sites together.

### Fixed

- **A failed run says why**: a durable run that ended without a result, whether met by `widget attended …`, `widget detached wait` or `widget detached result`, now prints the reason the runner stored for it (its title and message), the next step it advises and whether running it again can succeed, instead of repeating its status; `widget detached status` prints the same lines under the status. A run that ended with no stored report, such as a cancelled one, says that no reason was recorded, keeps the platform's own sentence and says what is left to do.
- **Server text in an error is printed as it came**: a bracketed span in an error message or a stored report, such as a provider's `[/x]`, is no longer read as Rich markup, so it neither disappears nor crashes the print.

## [v0.1.0] - 2026-09-22

### Highlights

**A Python starter for the hosted Pipelex API.** The starter runs MTHDS methods with `pipelex-sdk` and never installs the `pipelex` runtime: the `.mthds` bundle is read from disk and sent to the API, which runs the method and returns the output. Copy it with "Use this template", then run `/bootstrap` to make it yours.

### Added

- **Execution modes as command groups**: `widget blocking …` runs a method in one call and dies at the hosted cap, `widget attended …` starts a durable run and waits for it, and `widget detached …` starts one and collects it later with `status`, `result` or `wait`. Each mode is a self-contained file meant to be diffed against the others, and nothing about the run lifecycle is shared.
- **The demos, in every mode**: `extract-entities` takes text, `summarize-pdf` uploads a file to hosted storage and sends its URI, and `generate-image` is the slow case that overruns the blocking cap on purpose. Every demo runs with zero arguments by falling back to a built-in sample.
- **Generated typed clients**: `make codegen` projects each bundle's concepts into `widget/generated/<method>/models.py` through the hosted codegen route, and `make codegen-check` verifies the committed trees against their locks offline. The same check runs in the test suite, so a tree that drifted from its lock fails in CI.
- **`make add-method`, for a method that lives elsewhere**: a catalog id or a published address becomes a `method.json` manifest, a generated tree and one Typer command in the mode you name, with parameters derived from the method's own input form and nothing method-shaped written by hand.
- **Cost reports and produced files**: every result-producing command prints a per-call cost report to stderr and brings the files a run produced down to `downloads/`, with links minted fresh rather than read from the expiring result.
- **Structured errors with hints**: an SDK or HTTP failure is mapped to a message and a hint naming the mode group to use, read from the API's RFC 7807 problem body rather than from a stringified exception.
- **`/bootstrap`**: the Claude Code skill that turns a fresh copy of this template into a named project, renaming the `widget` placeholder everywhere it appears and refusing to hand back a half-renamed tree.
- **`AGENTS.md`**: the damage-causing rules for any coding agent, beside `CLAUDE.md`.
