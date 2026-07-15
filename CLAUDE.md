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
- **The execution mode is the command group, not an option.** There are exactly three, each a self-contained Typer sub-package: `piper blocking …` (`client.execute` — one call, dies at the hosted ~30s cap), `piper attended …` (`client.start` + `client.wait_for_result` — durable, you wait), `piper detached …` (`client.start` only — durable, you collect it later with `piper detached status|result|wait <id>`). Attended and detached start the *same* durable run; the axis they name is who waits. There is no default mode and no `--mode` option: `piper/cli.py` is a thin assembler (`load_dotenv` callback + three `add_typer` calls in reading order) and nothing else.
- **Each mode file is a copy-paste unit; lifecycle code is never shared.** `piper/<mode>/cli.py` holds that mode's whole story: its `typer.Typer`, its consoles (results → stdout, progress → stderr), its one public lifecycle helper (`execute_pipe` / `start_and_wait` / `start_pipe`, plus `attend_run` + the fetchers in detached), its demo commands, and a private `_run()` that wraps `asyncio.run` and catches SDK errors once. The **only** shared modules are the two that are orthogonal to execution: `piper/inputs.py` (text-or-file input with a built-in **sample fallback** so every demo runs with zero arguments — `read_text_input` returns `TextInput(text, is_sample)` and the demo prints a stderr notice when the sample was used; plus file → `{"concept": "Document", "content": …}` envelope with the file base64-encoded into a `data:` URL, and the `SAMPLE_*` constants) and `piper/errors.py` (SDK error → message + hint, hints naming the mode groups; it reads the RFC 7807 **problem+json** body off raw protocol-route `httpx.HTTPStatusError`s and branches on the structured `error_type`, e.g. `StartRequiresAsyncOrchestration` → "use `piper blocking`"). Do not introduce a shared runner — the dispatch indirection is exactly what this layout removed. See `docs/cli-architecture.md`.
- **Full demo matrix, guarded.** All three demos exist in all three modes: `extract-entities` (text in), `summarize-pdf` (a *file* in), `generate-image` (prompt in). `generate-image` is the deliberate slow case that overruns the ~30s blocking cap — `piper blocking generate-image` is *expected to fail*, and that is the teaching moment for the durable modes. The near-duplication across mode files is the pedagogy (diff two mode files and only the lifecycle helper differs); `tests/unit/test_mode_symmetry.py` keeps it from drifting. `samples/sample-invoice.pdf` is shipped for `summarize-pdf`.
- The SDK resolves the main output on every result-producing path (`client.execute` returns a `PipelexExecuteResult`, the durable path a `RunResults`, both exposing a resolved `.main_stuff`, typed `Any`; a completed run with no main stuff raises `MissingMainStuffError`). So the result-producing lifecycle helpers (`execute_pipe`, `start_and_wait`, detached's `attend_run`) return `main_stuff`, and the blocking/attended demo commands narrow it inline — e.g. `ExtractedEntities.model_validate(main_stuff)` — into the generated model. Detached is the exception by design: `start_pipe` returns only the run id (the demos print it bare), and the run-id commands (`wait`/`result`) print the output generically — no model narrowing, since at collection time the command doesn't know which method the run executed. There is no per-example wrapper layer.
- The modes spell out lifecycles the SDK could hide: `client.start_and_wait()` is a self-healing one-liner that picks the path for you (the production shortcut). The starter writes them out because teaching the difference is the point.
- **The typed models are generated, never hand-written.** `pipelex codegen` projects each bundle's concepts into `piper/generated/<method>/models.py` (stamped, locked by a sibling `codegen.lock`); the mode CLIs and the e2e tests import from there. Do NOT edit generated files — edit the bundle, then `make codegen` (regenerates models + `inputs.template.json` scaffolds) and `make codegen-check` (offline drift check). The `pipelex` CLI is not a dependency of this starter; point the `PIPELEX` make variable at a pipelex install that ships `codegen`. `piper/generated` is excluded from ruff (reformatting would trip the drift check) but fully type-checked. See `docs/codegen.md`.

## Project Structure

- Package: `piper/` (Python 3.11+, target 3.11) — root `cli.py` + one sub-package per execution mode (`blocking/`, `attended/`, `detached/`) + the two shared modules (`inputs.py`, `errors.py`). New mode sub-packages must be added to `[tool.setuptools] packages` in `pyproject.toml`.
- Tests: `tests/` (unit = offline per-mode CLI tests patching each mode's public lifecycle helper, plus mode-symmetry / error-mapping / generated-client tests; integration = offline boot/bundle checks + API `validate`; e2e = full run via the API, one execution mode per demo so all three get end-to-end coverage)
- Dependency manager: uv (>=0.7.2)
- Pipelex dependency: `pipelex-sdk` package from PyPI (the API client — see pyproject.toml). The `pipelex` runtime is **not** a dependency.
- `.mthds` files: Pipelex method definition files in `piper/methods/<name>/main.mthds`

## Test markers

- `pipelex_api` — reaches the hosted API (needs a key); excluded from `make agent-test` / `make gha-tests`.
- `inference` — runs real LLM inference via the API; also excluded by default.
- Offline tests (no marker) run everywhere, including CI.
