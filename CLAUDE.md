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
- `make cleanderived` - Remove caches/compiled files (useful when linters get confused)
- `make validate` / `make v` - Lint/validate the `.mthds` bundle with plxt (offline)
- `make codegen` - Regenerate the typed clients + input templates from the `.mthds` methods (needs the `pipelex` CLI — see below)
- `make codegen-check` - Verify generated clients are current (offline, pure hashing against each `codegen.lock`)
- `make tb` - Quick boot test (constructs the API client, no network)
- `make fui` - Fix unused imports only
- `make plxt-format` - Format `.mthds`/`.toml` files with plxt
- `make plxt-lint` - Lint `.mthds`/`.toml` files with plxt

## Architecture

This starter calls the **hosted Pipelex API** via the `pipelex-sdk` package (`PipelexAPIClient`) — it does **not** run Pipelex as a local library. The `.mthds` bundle is read from disk and sent to the API as content (`mthds_contents`); the API runs the method and returns the output.

- Credentials/endpoint come from `PIPELEX_BASE_URL` / `PIPELEX_API_KEY` (see `.env.example`). `python-dotenv` loads `.env` when running the CLI or tests.
- The `piper` CLI (`piper/cli.py`) is a Typer app; `piper/runner.py` dispatches each run by execution mode — `blocking` (`client.execute`), durable attended (`client.start` + `client.wait_for_result`), and durable detached (`client.start` only, resumed via `piper runs status|result|wait <id>`). It branches on mode explicitly rather than using the SDK's `start_and_wait` self-healing one-liner, because teaching the mode difference is the point.
- The SDK resolves the main output on both modes: `client.execute` returns a `PipelexExecuteResult` and the durable path a `RunResults`, both exposing a resolved `.main_stuff` (a completed run with no main stuff raises `MissingMainStuffError`). Each demo command in `piper/cli.py` narrows its own result inline — e.g. `ExtractedEntities.model_validate(results.main_stuff)` — into the generated model; there is no per-example wrapper layer. SDK errors are mapped to CLI-facing messages + hints in `piper/errors.py`.
- **The typed models are generated, never hand-written.** `pipelex codegen` projects each bundle's concepts into `piper/generated/<method>/models.py` (stamped, locked by a sibling `codegen.lock`); the CLI and the e2e tests import from there. Do NOT edit generated files — edit the bundle, then `make codegen` (regenerates models + `inputs.template.json` scaffolds) and `make codegen-check` (offline drift check). The `pipelex` CLI is not a dependency of this starter; point the `PIPELEX` make variable at a pipelex install that ships `codegen`. `piper/generated` is excluded from ruff (reformatting would trip the drift check) but fully type-checked. See `docs/codegen.md`.
- Three demo commands share that dispatch: `extract-entities` (text in), `summarize-pdf` (a *file* in — `piper/file_input.build_document_input()` encodes a local file as a base64 `data:` URL wrapped in a `{"concept": "Document", "content": …}` envelope), and `generate-image` (prompt in). `generate-image` is the deliberate slow case that overruns the ~30s blocking cap, so it's how the starter demonstrates the durable-vs-blocking difference concretely. `samples/sample-invoice.pdf` is shipped for `summarize-pdf`.

## Project Structure

- Package: `piper/` (Python 3.11+, target 3.11)
- Tests: `tests/` (unit = offline CLI/error-mapping/generated-client tests; integration = offline boot/bundle checks + API `validate`; e2e = full run via the API)
- Dependency manager: uv (>=0.7.2)
- Pipelex dependency: `pipelex-sdk` package from PyPI (the API client — see pyproject.toml). The `pipelex` runtime is **not** a dependency.
- `.mthds` files: Pipelex method definition files in `piper/methods/<name>/main.mthds`

## Test markers

- `pipelex_api` — reaches the hosted API (needs a key); excluded from `make agent-test` / `make gha-tests`.
- `inference` — runs real LLM inference via the API; also excluded by default.
- Offline tests (no marker) run everywhere, including CI.
