# Changelog

## [Unreleased]

### Added

- **`make add-method`, for a method that lives elsewhere**: `make add-method METHOD=<mt_… | github.com/owner/repo[/package][@tag]>` wires a method that lives on the platform or in a published package into this CLI in one gesture — the `method.json` manifest, the generated tree, and one Typer command in the execution mode `MODE=` names (default `attended`). The command's parameters come from the method's own input-form descriptor and its narrowing from the output contract, so nothing method-shaped is written by hand; an input kind with no honest command-line spelling (`object`, `list`, `image`, `unknown`) is refused naming the input rather than guessed at, as is a pipe that cannot be chosen without a guess. Nothing is written until everything has been fetched and derived, `--dry-run` stops at that boundary and prints the plan, and the gesture never overwrites — `make codegen` is the refresh. Before anything is fetched it asks `GET /v1/version` whether this deployment resolves the kind of selector you passed, so an address against a deployment that serves only catalog ids refuses naming the base URL and the missing capability instead of surfacing an opaque `403`. `docs/add-method.md` is the reference, and `tests/unit/test_add_method.py` compiles the emitted command for every mode against the real mode files. Its JS twin is `pipelex-starter-js`'s `make add-method`; the differences are deliberate and documented.
- **A second method source kind, `method.json`**: a directory under `piper/methods/` now holds either `.mthds` files (the bundle, as before) or a one-line manifest naming exactly one of `method_id` / `method_ref`. `make codegen` discovers both and sends the right selector, so a method that lives elsewhere is regenerated through the same call and the same writer as a bundle rather than through a second path; a directory holding both kinds is refused, because the two would disagree about where the generated tree came from.
- **`AGENTS.md`**: the damage-causing rules for any coding agent, beside `CLAUDE.md` — the generated tree, the regenerate-and-commit rule, the gates, the no-`pipelex`-dependency decision, the no-shared-runner rule and the scaffolder's anchors. It also records this repo's decision **not** to carry an `adopt-in-an-existing-project.md`: in Python there is no kit to transplant (`pipelex-sdk` already ships the writer and the offline check), the transplant is five bullets, and the moving part belongs to the `/pipelex-integrate` skill rather than to a page here that would go stale behind it.
- **The bootstrap renames `AGENTS.md` too**: it is in `gather_target_files`'s explicit set beside `CLAUDE.md`, because a file missing from that set is not merely left alone — the no-token-survives assertion reads the same list, so bootstrap would report success over a project whose `AGENTS.md` still named the template's package.
- **`piper/outputs.py`**: `list_items`, the one place a plural output is read. A plural output arrives as a bare array or as an `items` envelope depending on the execution path rather than on the method, so a command that declared either shape would work in one mode and fail in another; `list_items` accepts both and hands the elements back for the generated model to validate.
- **The generated clients are drift-checked in CI**: `tests/unit/test_generated_clients.py` now runs `pipelex_sdk.codegen_check.run_codegen_check` over each `piper/generated/<method>/` tree, comparing every artifact's whole body against the SHA-256 its `codegen.lock` records. A tree regenerated and only half committed, a file hand-edited below its stamp, a locked artifact deleted or a stale one left behind now fails the test suite — offline, with no `pipelex` install, no API key and no network, which is what puts the check in `tests-check.yml` where `make codegen-check` could not go. The methods covered are discovered from `piper/methods/` rather than listed by hand.

### Changed

- **A failed request names its route and says what to do**: `explain` in `scripts/codegen.py` now reads a raw `httpx.HTTPStatusError` as well as the SDK's `ApiResponseError`, and takes the route it is reporting on. The protocol routes surface the raw class, so a `validate` failure used to print an httpx one-liner with a link to MDN and nothing else.
- **The three lifecycle helpers take a method selector**: `execute_pipe`, `start_and_wait` and `start_pipe` now take `mthds_contents`, `method_id` or `method_ref` — the SDK's own three-way XOR — instead of `mthds_contents` alone, and all three are keyword-only. The demos still send the bundle they ship; a scaffolded command sends the selector its manifest holds. Each mode file also gains the `# add-method:imports` and `# add-method:commands` anchors the scaffolder inserts at.
- **The wheel's contents are derived rather than listed**: `pyproject.toml` moves to `[tool.setuptools.packages.find]` and a package-data glob for `codegen.lock`, and `make codegen-check` loops over `piper/generated/*/codegen.lock` instead of naming each method. Adding a method used to mean remembering three sites; the only one that still names a method by hand is the `CLI_INPUTS` map in `tests/unit/test_generated_clients.py`, which cannot go stale unnoticed.
- **`tests/unit/test_mode_symmetry.py` asserts containment, not equality**: every demo must still be in every mode, and the run-lifecycle commands must still be detached's alone — but a mode may now hold more, because `make add-method` writes its command into exactly one of them. Demanding the three sets be equal would have turned using the scaffolder into a test failure.
- **`make codegen` regenerates through the hosted API (Breaking)**: it now runs `scripts/codegen.py`, which discovers every method under `piper/methods/`, posts each one to `POST /v1/codegen` with `pipelex-sdk` and writes the response verbatim with the SDK's `write_codegen_tree` — so regenerating the typed clients needs `PIPELEX_API_KEY` and nothing else, where it used to need a `pipelex` runtime install the starter does not depend on and a `PIPELEX=` make variable pointing at it. That variable now serves `make codegen-check` alone, the offline drift check; the `pipelex-sdk` floor moves to `>=0.10.0`, the release that ships `write_codegen_tree` and the `crate_models` request envelope alongside the codegen route.
- **Regenerated typed clients**: the committed trees under `piper/generated/` were regenerated through the hosted engine. No class, field, type, default or description changed — the only differences are the stamp headers, a new `lock_version` key in each `codegen.lock`, and longer `Field(...)` calls now wrapped. That key raises the floor for `make codegen-check` to a `pipelex` of 0.47.0 or newer, because the `CodegenLock` model before that release forbids unknown keys.
- **`scripts/` is type-checked**: `scripts` now appears in `[tool.pyright] include` and `[tool.mypy] packages`, so `make agent-check` covers `scripts/codegen.py` at the same strictness as the rest of the repo. It was outside both scopes before, which is the only reason the checks could pass green while the script imported an SDK module the lockfile did not carry. `pipelex-starter-js` already type-checks its own scripts, so this also removes an asymmetry between the two starters.
- **Tooling:** Pinned `ruff` to an exact `0.16.4`, up from `0.14.13`. This matches what the Ruff VS Code extension now bundles, which matters because Ruff 0.16 lints `pyproject.toml` itself: the extension syncs the config file to the language server, and a pre-0.16 binary parses it as Python source and paints phantom `invalid-syntax` diagnostics on lines like `requires-python`. Keeping the pin exact stops the editor and the CLI from drifting apart again. This is a dev dependency, so nothing shipped changes; the upgrade produced no new lint findings. Because this is the starter template every new project is cloned from, the stale pin was propagating into fresh checkouts.
- **Editor config:** Removed the `ruff.configuration` entry from `.vscode/settings.json`. That setting takes a path to a config file rather than a CLI flag, so its `--config=pyproject.toml` value never resolved — it only appeared to work because Ruff falls back to discovering the same `pyproject.toml` on its own.

### Removed

- **The committed `inputs.template.json` scaffolds (Breaking)**: the generated input template beside each `piper/methods/<method>/main.mthds` is gone, and so is its `package-data` entry — no code read it, the route that projected it is retired, and a committed scaffold nothing reads goes stale unnoticed. The offline floor now asserts that each bundle declares exactly the inputs its mode CLIs pass, read from the `main.mthds` itself rather than from a generated file; `docs/codegen.md` shows how to project a template from a method's input-form descriptor when you want one.

## [v0.15.0] - 2026-07-22

### Added

- **Cost reports on every run.** Each result-producing command now prints a per-call cost report (pipe, model, tokens in→out, USD cost, and a total) to stderr, after the JSON result on stdout. A new shared `piper/usage.py` reads the run's per-call usage off the SDK result into a `RunUsage` (`usage_from_results` for the durable modes' typed `RunResults.tokens_usages`; `usage_from_execute` for blocking, which lifts the same records off its execute result) and renders it with `print_cost_report`. It respects the SDK's usage semantics: an unpriced call (`cost is None` — mock / own-GPU / dry-run) is excluded from the total rather than counted as zero, and token categories are never summed. Detached prints the report from `wait` / `result` (collection time), not from the start-only demo commands.

### Changed

- **Cleaner file upload for `summarize-pdf` (breaking):** the document is now uploaded to hosted storage up front with `client.upload_file` (new `inputs.upload_document_input`), and the run request carries only the returned `pipelex-storage://` URI — replacing the previous inline base64 `data:` URL. `inputs.build_document_input` becomes the pure envelope builder `build_document_input(path, uri)`; the upload is a separate step, so a file or capability error surfaces before any run is created. `piper/errors.py` gains hints for the file-upload error family (unsupported capability, rejected asset, authentication, invalid local source).
- **Lifecycle helpers return `(main_stuff, RunUsage)` (breaking):** `execute_pipe`, `start_and_wait`, and detached's `attend_run` now return the resolved main output *and* the run's usage, instead of `main_stuff` alone, so the commands can print the cost report. The demo commands unpack the pair; the SDK output accessor itself is unchanged.
- Bumped the `pipelex-sdk` floor from `>=0.4.0` to `>=0.5.0` (for `upload_file` and typed run usage).

## [v0.14.1] - 2026-07-15

- **Multi-file bundle support in the mode lifecycle helpers:** `execute_pipe`, `start_and_wait`, and `start_pipe` now take `mthds_contents: list[str]` (the bundle's `.mthds` files as strings — one entry for a single-file bundle, several for a multi-file one) instead of a single `bundle: str`, passed straight through to the SDK. Multi-file bundles cannot be concatenated into one string (duplicate top-level TOML keys), so the list is the interface. The three demos stay single-file (`mthds_contents=[bundle]`); a method dir with several `.mthds` files is read with `[p.read_text() for p in sorted((METHODS_DIR / "<name>").glob("*.mthds"))]`. The package-data glob broadens to `methods/*/*.mthds` so multi-file bundles ship.
- Bumped the `pipelex-tools` dev dependency from `>=0.3.2` to `>=0.7.2`.

## [v0.14.0] - 2026-07-15

### Added

- **Zero-argument demo fallbacks:** every demo now runs with zero arguments, falling back to a built-in sample (e.g. `samples/sample-invoice.pdf` for `summarize-pdf`) and printing a notice to stderr, so stdout stays pipeable and a fresh clone shows a working result on the first command. `read_text_input()` gains a `sample` parameter and returns a `TextInput(text, is_sample)`.
- **Generated typed clients:** output models are now generated from `.mthds` bundles into `piper/generated/` via `pipelex codegen`, replacing hand-written models (`generate-image` now parses into the generated `Image` model, replacing the hand-written `GeneratedImage`). Added `make codegen` to regenerate clients and templates, and `make codegen-check` to verify offline (via hashing against each `codegen.lock`) that generated clients are up to date. Each `codegen.lock` ships as package data, so the check also works against an installed (wheel) copy, not just a git checkout.
- **New documentation:** added `docs/cli-architecture.md`, describing the copy-paste CLI layout, and `docs/codegen.md`, explaining the generated-models workflow.
- **Offline smoke tests:** added `tests/unit/test_generated_clients.py` to verify generated modules import correctly, carry the stamp + lock, round-trip their serialization, and match the committed input templates to the CLI's inputs; and `tests/unit/test_mode_symmetry.py` to guard against drift between CLI modes.
- **Bootstrap validation:** `/bootstrap` now rejects package names that collide with the template's `piper` placeholder (e.g. `piper_tools`, which would corrupt into `piper_tools_tools` under the pyproject transform).

### Changed

- **Execution mode is now the command group, not an option (Breaking):** `--mode`, `--detach`, and the `PIPELEX_EXECUTION_MODE` env var are gone — invoke the mode explicitly: `piper blocking <demo>`, `piper attended <demo>`, or `piper detached <demo>`. The top-level `runs` command moves under detached mode (`piper detached status|result|wait <id>`). There is no default mode anymore; the mode is explicit in every invocation, which is itself the lesson. The middle mode is named `attended`, not `durable`, because detached runs are durable too — the axis the names describe is who waits.
- **Typed `Image` dimensions (Breaking):** the generated `Image` model now uses optional integer `width` and `height` fields instead of an untyped `size` dict, with native field descriptions sourced from the standard's pinned definitions. Regenerated all committed clients (stamps, locks, and fingerprints updated).
- **CLI architecture:** each execution mode is now a self-contained, copy-paste unit (`piper/<mode>/cli.py`) with its own commands, SDK lifecycle helper (`execute_pipe` / `start_and_wait` / `start_pipe`), and progress rendering; lifecycle code is no longer shared. Only mode-orthogonal code remains shared: `piper/inputs.py` (text/file inputs and document envelopes — `piper/file_input.py` is merged into it) and `piper/errors.py`, whose hints now name the mode groups (a blocking run that hits the ~30s cap points at `piper attended`; an interrupted attended run points at `piper detached wait <id>`).
- **Structured HTTP errors:** protocol-route HTTP errors now parse and surface the API's RFC 7807 `problem+json` body (`title`, `detail`, machine `error_type`) instead of httpx's stringification, with hints pointing to the correct CLI mode based on error type (e.g. `StartRequiresAsyncOrchestration` points at `piper blocking`).
- **E2E tests:** end-to-end tests now call the mode lifecycle helpers directly, with one execution mode per demo (`extract-entities` → blocking, `summarize-pdf` → attended, `generate-image` → detached) for full matrix coverage.
- `piper/generated` is excluded from ruff (reformatting generated files would trip the drift check) but remains fully type-checked.

### Fixed

- **Bootstrap `pyproject.toml` transform:** `/bootstrap` now rewrites `pyproject.toml` using generic, context-aware rules (quoted-exact and dotted/path positions) instead of per-key edits, preventing staleness as the package list changes, and correctly handles the multi-line `packages` array with the `piper.generated.*` subpackages, quoted package-data keys, and the `piper/generated` ruff exclude.

### Removed

- **Dispatch layer:** removed `piper/runner.py`, the central `_dispatch()` chain, and the `ExecutionMode` enum, in favor of the self-contained mode CLIs; `piper/cli.py` shrinks to a `load_dotenv` callback plus three `add_typer` calls.
- **`piper/examples/` layer:** removed the per-demo wrapper modules; demo logic and inline model narrowing (`Model.model_validate(main_stuff)`) now live directly in the mode CLI files. The `parse()` unit tests went with it (they only exercised pydantic's `model_validate`).
- **`piper/file_input.py`:** merged into the new shared `piper/inputs.py` module.

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
