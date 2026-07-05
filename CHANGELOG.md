# Changelog

## [Unreleased]

## [v0.11.0] - 2026-07-05

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
