# Changelog

## [Unreleased]

- **The typed output models are now generated from the bundles, not hand-written.** `pipelex codegen` projects each method's concepts into `piper/generated/<method>/models.py` (a stamped module plus a `codegen.lock` recording the artifact set); the `piper/examples/*.py` modules now import the generated models and keep only the bundle path, pipe code, and the `parse()` narrower. `generate-image` parses into the generated built-in `Image` model (natives are materialized into the generated client), replacing the hand-written `GeneratedImage`.
- **New make targets:** `make codegen` regenerates the typed clients and the runnable `inputs.template.json` scaffolds beside each bundle; `make codegen-check` verifies offline (pure hashing, no network or API key) that the generated clients are current. The `pipelex` CLI is not a starter dependency — point the `PIPELEX` make variable at a pipelex install that ships `codegen`. CI wiring of `codegen-check` lands once a released pipelex ships the command.
- **New offline smoke tests** (`tests/unit/test_generated_clients.py`): the generated modules import, carry the stamp + lock, round-trip their serialization, and each committed input template names exactly the inputs the CLI dispatches.
- `piper/generated` is excluded from ruff (reformatting generated files would trip the drift check) and remains fully type-checked; documented the whole flow in `docs/codegen.md`.
- Each `codegen.lock` is shipped as package data, so `pipelex codegen check` also works against an installed (wheel) copy, not just a git checkout.

## [v0.13.0] - 2026-07-07

- **Breaking:** renamed the starter's placeholder project from `my-project` / `my_project` / `My Project` to `piper` / `Piper`. The console command is now `uv run piper ...`, the template package is `piper/`, `pyproject.toml` points at `piper.cli:app`, and the e2e extract-entities test file no longer carries the project placeholder in its name.
- **Reworked `/bootstrap` for the single-token placeholder.** It now derives distribution, package, and title forms from `piper`, applies context-aware replacements for command vs import/path positions, edits `pyproject.toml` by key, and aborts before writing if any placeholder tokens survive.
- **Overhauled the README DevX.** The quick start now explains `uv run` before the first command, shows real expected output, groups the demos around copy-pasteable commands, explains durable vs blocking execution, and adds Mermaid diagrams for hosted-run flow and execution modes.
- **Added demo methods so the starter matches the JS starter.** `summarize-pdf` summarizes a document (PDF) into `{ title, doc_type, key_points }` and demonstrates a *file* input: `piper/file_input.build_document_input()` encodes a local file as a base64 `data:` URL wrapped in a `Document` envelope. `generate-image` generates an image from a text prompt and is the slow case that overruns the hosted ~30s blocking cap, making the durable-vs-blocking split concrete. Each is a self-contained "copy me" module under `piper/examples/` with a matching `main.mthds` bundle and its own unit + e2e tests. Ships `samples/sample-invoice.pdf` to try `summarize-pdf` on.

## [v0.12.0] - 2026-07-06

- **Breaking:** dropped Python 3.10 support. `pipelex-sdk` 0.4.0 no longer supports 3.10, so the starter now requires Python 3.11+ (`requires-python = ">=3.11,<3.15"`). Removed the `Python :: 3.10` classifier and dropped 3.10 from the CI lint/test matrices.
- Bumped `pipelex-sdk` to 0.4.0 (pulls in `mthds` 0.8.1). Re-locked `uv.lock` and refreshed the dev-tooling pins (ruff, mypy, pyright, pytest).

## [v0.11.0] - 2026-07-05

- **Fixed:** the demo bundle's list fields (`people`/`orgs`/`dates`) now declare `item_type = "text"` so the output is typed as `list[str]`, matching the `ExtractedEntities` model. Without it the runtime built the fields as `List[Any]`.
- **Read a run's output with `results.main_stuff`.** Bumped to `pipelex-sdk` 0.3.0, which resolves the main output for you on both execution modes: `execute` returns a `PipelexExecuteResult` and the durable path a `RunResults`, and both expose a resolved `.main_stuff`. The starter's whole output-extraction module (`my_project/run_output.py` — `find_main_content` shape-guessing + the `to_run_results` adapter) is gone; the CLI and the narrower read `results.main_stuff` directly, and the blocking `execute` result is adapted onto `RunResults` inline in the runner. A completed run that delivers no main stuff raises the SDK's `MissingMainStuffError` instead of yielding `None`.
- **Breaking:** renamed the env var `PIPELEX_API_URL` to `PIPELEX_BASE_URL` for consistency with the SDK's `base_url` naming. There is no read alias — update your `.env` / environment.
- **Fixed:** rewrote the README and `CLAUDE.md` around the actual `my-project` CLI (the `extract-entities` command, the durable/blocking execution modes, and the `runs status|result|wait` lifecycle). They still described the removed `hello_world` module, `start_and_wait` usage, and the `find_main_content` normalizer, so the quick start's first command errored out for a fresh user.
- **Repository:** removed internal-only planning docs (`TODOS.md`, `wip/`) that must not ship in a "Use this template" repo.

## [v0.10.0] - 2026-07-01

- **Breaking:** run methods through the hosted Pipelex API instead of the local `pipelex` runtime. The `pipelex` package (and its `[tool.uv.sources]` git pin) is dropped; the starter now depends on `pipelex-sdk` (`PipelexAPIClient`) and `python-dotenv`.
- Rewrite `my_project/hello_world.py` to read the `.mthds` bundle from disk and run it via `client.start_and_wait(pipe_code=..., mthds_contents=[...])`, reading the output out of `main_stuff` / `pipe_output`.
- Configuration is now `PIPELEX_API_URL` / `PIPELEX_API_KEY` (see `.env.example`); `.env` is loaded via `python-dotenv`.
- Repoint `make validate` to `plxt lint` (offline bundle validation, was `pipelex validate --all`).
- Rewrite the test suite to be API-based: offline boot/bundle checks plus API `validate` (`pipelex_api`) and a full run (`inference`). CI no longer runs `pipelex init`, and `make gha-tests` / `make codex-tests` exclude the `pipelex_api` marker.
- Prune AWS/doc type-stub dev dependencies that were only needed by the `pipelex` runtime.
- Add a `/bootstrap` skill (`.claude/skills/bootstrap/`) that turns a fresh clone of this template into a real project. It collects the project name, description, author, repository URL, and license, then renames the package directory and e2e test file, substitutes every placeholder name spelling (dash / underscore / Title Case / CamelCase), applies the chosen license (MIT, proprietary, or another SPDX id) across `LICENSE`, `pyproject.toml`, and the README, regenerates `uv.lock`, and runs the lint/type checks and tests

## [v0.9.0] - 2026-06-06

- Bump `pipelex` to `v0.32.0`: See `Pipelex` changelog [here](https://docs.pipelex.com/latest/changelog/)
- Update `tests/integration/test_fundamentals.py` to use the new `BundleValidator().acquire_and_validate()` API (replaces the removed `dry_run_pipes` / `get_library_manager` dry-run path)

## [v0.8.0] - 2026-05-06

- Bump `pipelex` to `v0.26.4`: See `Pipelex` changelog [here](https://docs.pipelex.com/latest/changelog/)
- Add `pipelex-tools` dev dependency
- Update `tests/integration/conftest.py` to use the new `needs_inference` kwarg on `Pipelex.make()` (replaces deprecated `disable_inference`)
