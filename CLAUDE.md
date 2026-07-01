# Pipelex Starter Project

## Commands

### Linting & Type Checking

After making code changes, always run:
```bash
make agent-check
```
This runs: fix-unused-imports, ruff format, ruff lint, plxt format/lint (`.mthds`/`.toml`), pyright, mypy.

### Running Tests

```bash
make agent-test
```
Silent on success, full output on failure. Excludes inference/LLM markers by default.

Run specific tests (local only): `make tp TEST=test_function_name`

### Other Useful Targets

- `make install` - Create venv + install all deps (uses uv)
- `make li` - Lock + install
- `make run` - Run the `hello_world` example against the Pipelex API
- `make cleanderived` - Remove caches/compiled files (useful when linters get confused)
- `make validate` / `make v` - Lint/validate the `.mthds` bundle with plxt (offline)
- `make tb` - Quick boot test (constructs the API client, no network)
- `make fui` - Fix unused imports only
- `make plxt-format` - Format `.mthds`/`.toml` files with plxt
- `make plxt-lint` - Lint `.mthds`/`.toml` files with plxt

## Architecture

This starter calls the **hosted Pipelex API** via the `pipelex-sdk` package (`PipelexAPIClient`) — it does **not** run Pipelex as a local library. The `.mthds` bundle is read from disk and sent to the API as content (`mthds_contents`); the API runs the method and returns the output.

- Credentials/endpoint come from `PIPELEX_API_URL` / `PIPELEX_API_KEY` (see `.env.example`). `python-dotenv` loads `.env` when running the CLI or tests.
- `my_project/hello_world.py` uses `client.start_and_wait(...)` — the durable start-and-poll path (survives the hosted gateway's ~30s cap, self-heals to blocking `execute` on a bare runner).
- Output is loosely-typed JSON: hosted runs carry `main_stuff`; the bare-runner fallback carries `pipe_output`. `find_main_content()` normalizes both.

## Project Structure

- Package: `my_project/` (Python 3.10+, target 3.11)
- Tests: `tests/` (integration = offline boot/bundle checks + API `validate`; e2e = full run via the API)
- Dependency manager: uv (>=0.7.2)
- Pipelex dependency: `pipelex-sdk` package from PyPI (the API client — see pyproject.toml). The `pipelex` runtime is **not** a dependency.
- `.mthds` files: Pipelex method definition files in `my_project/`

## Test markers

- `pipelex_api` — reaches the hosted API (needs a key); excluded from `make agent-test` / `make gha-tests`.
- `inference` — runs real LLM inference via the API; also excluded by default.
- Offline tests (no marker) run everywhere, including CI.
