# Changelog

## [v0.9.0] - 2026-06-06

- Bump `pipelex` to `v0.32.0`: See `Pipelex` changelog [here](https://docs.pipelex.com/latest/changelog/)
- Update `tests/integration/test_fundamentals.py` to use the new `BundleValidator().acquire_and_validate()` API (replaces the removed `dry_run_pipes` / `get_library_manager` dry-run path)

## [v0.8.0] - 2026-05-06

- Bump `pipelex` to `v0.26.4`: See `Pipelex` changelog [here](https://docs.pipelex.com/latest/changelog/)
- Add `pipelex-tools` dev dependency
- Update `tests/integration/conftest.py` to use the new `needs_inference` kwarg on `Pipelex.make()` (replaces deprecated `disable_inference`)
