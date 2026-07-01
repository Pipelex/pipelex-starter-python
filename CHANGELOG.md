# Changelog

## [Unreleased]

- **Breaking:** run methods through the hosted Pipelex API instead of the local `pipelex` runtime. The `pipelex` package (and its `[tool.uv.sources]` git pin) is dropped; the starter now depends on `pipelex-sdk` (`PipelexAPIClient`) and `python-dotenv`.
- Rewrite `my_project/hello_world.py` to read the `.mthds` bundle from disk and run it via `client.start_and_wait(pipe_code=..., mthds_contents=[...])`, reading the output out of `main_stuff` / `pipe_output`.
- Configuration is now `PIPELEX_API_URL` / `PIPELEX_API_KEY` (see `.env.example`); `.env` is loaded via `python-dotenv`.
- Add `make run` to run the example; repoint `make validate` to `plxt lint` (offline bundle validation, was `pipelex validate --all`).
- Rewrite the test suite to be API-based: offline boot/bundle checks plus API `validate` (`pipelex_api`) and a full run (`inference`). CI no longer runs `pipelex init`, and `make gha-tests` / `make codex-tests` exclude the `pipelex_api` marker.
- Fix a latent pytest config bug: `[tool.pytest]` → `[tool.pytest.ini_options]` (markers/asyncio config were previously supplied by the now-removed pipelex pytest plugin).
- Prune AWS/doc type-stub dev dependencies that were only needed by the `pipelex` runtime.

## [v0.9.0] - 2026-06-06

- Bump `pipelex` to `v0.32.0`: See `Pipelex` changelog [here](https://docs.pipelex.com/latest/changelog/)
- Update `tests/integration/test_fundamentals.py` to use the new `BundleValidator().acquire_and_validate()` API (replaces the removed `dry_run_pipes` / `get_library_manager` dry-run path)

## [v0.8.0] - 2026-05-06

- Bump `pipelex` to `v0.26.4`: See `Pipelex` changelog [here](https://docs.pipelex.com/latest/changelog/)
- Add `pipelex-tools` dev dependency
- Update `tests/integration/conftest.py` to use the new `needs_inference` kwarg on `Pipelex.make()` (replaces deprecated `disable_inference`)
