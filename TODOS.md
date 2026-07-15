# TODO: split the execution modes into three self-contained CLIs

Implementation plan for the design in **[`wip/mode-split-clis.md`](wip/mode-split-clis.md)** — read that first; it is the canonical design (target surface, package anatomy, sample code, rejected alternatives). This file tracks execution and carries just enough context to cold-start a fresh session.

## Cold-start context

**Goal.** Kill the `--mode` option and its dispatch chain (`cli.py` → `_dispatch` → `match ExecutionMode` → `runner.py` → SDK). Each execution mode becomes a self-contained Typer sub-package whose `cli.py` is a copy-paste unit: `piper blocking …`, `piper attended …`, `piper detached …`.

**Decisions already taken (do not re-litigate):**
- One `piper` binary, three command groups mounted in reading order: `blocking`, `attended`, `detached`.
- Naming is `blocking` / `attended` / `detached` (not `durable` — detached runs are durable too; attended/detached names the who-waits axis).
- Full demo matrix: every demo command (`extract-entities`, `summarize-pdf`, `generate-image`) exists in every mode group.
- Run-lifecycle commands live inside detached: `piper detached wait|status|result <run-id>`. No top-level `runs` group.
- Sharing rule: share only what's orthogonal to modes — `piper/errors.py` (presentation) and a new `piper/inputs.py` (input encoding). **Never share lifecycle code**; no shared runner module, ever.
- No default mode, no `PIPELEX_EXECUTION_MODE` env var. Breaking change, no compat shims (workspace policy).

**Target layout and fixed names** (each mode `cli.py`: docstring with copy-paste contract → `app` + `output_console`/`progress_console` (stderr) → public lifecycle helper → demo commands + private `_run()` asyncio/error wrapper; `METHODS_DIR = Path(__file__).parent.parent / "methods"` in each mode file):

```
piper/cli.py            root app: load_dotenv callback + add_typer × 3 — nothing else
piper/inputs.py         read_text_input(*, text, file) + build_document_input(file)  [merges file_input.py]
piper/errors.py         kept shared; hints reworded to group paths (see Phase 3)
piper/blocking/cli.py   lifecycle helper: execute_pipe(*, pipe_code, bundle, inputs)          → client.execute
piper/attended/cli.py   lifecycle helper: start_and_wait(*, pipe_code, bundle, inputs)        → client.start + wait_for_result (prints run id first; Ctrl-C hint → `piper detached wait <id>`)
piper/detached/cli.py   start_pipe(*, …) → client.start; attend_run(run_id) backs `wait`; fetchers back `status`/`result`
```

**What gets deleted:** `piper/runner.py`, `piper/file_input.py`, `ExecutionMode`, `--mode`/`ModeOption`/`MODE_HELP`, `_dispatch`, the `RunResults` adaptation in `run_blocking` (each mode returns its natural SDK type / resolved `main_stuff`), the top-level `runs` sub-app.

**Facts a cold session needs (verified 2026-07-13):**
- e2e tests call the runner helpers **directly** (e.g. `run_durable_attended(...)`), not through CliRunner — they swap to the new public lifecycle helpers, no CLI plumbing needed.
- `tests/integration/test_fundamentals.py` and the e2e tests import `METHODS_DIR` from `piper.cli`. The thin root app won't export it; tests compute it themselves (`Path(piper.__file__).parent / "methods"` in the test module or shared via `tests/conftest.py`).
- Unit CLI tests patch runner functions via `piper.cli` today (`mocker.patch("piper.cli.run_durable_attended", …)`); new tests patch each mode's public lifecycle helper (`piper.blocking.cli.execute_pipe`, etc.).
- The bootstrap rename script (`.claude/skills/bootstrap/scripts/bootstrap.py`) already handles bare and dotted package positions in pyproject (`piper`, `piper.generated.*`) — new `piper.blocking|attended|detached` entries ride the same rewrite; verify, don't rewrite.
- `piper/generated/` and `piper/methods/` are untouched by this work; `make codegen-check` must stay green with no regeneration.
- Workspace test rules: pytest-mock only (never unittest.mock), exactly one TestClass per test module, no `__init__.py` in test dirs.
- Checks: `make agent-check` (format/lint/pyright/mypy) and `make agent-test` (offline suite) after every phase; `pipelex_api`/`inference`-marked tests don't run offline — e2e edits are verified by review (or `make test-inference` if a key is at hand).

---

## Phase 1 — Shared input module ✅

- [x] Create `piper/inputs.py`: move `build_document_input()` from `piper/file_input.py` verbatim; move `_read_text_input()` out of `piper/cli.py` as public `read_text_input(*, text: str | None, file: Path | None) -> str` (keeps raising `typer.BadParameter` — this is a CLI starter, typer in a shared CLI-input module is fine).
- [x] Point `piper/cli.py` at the new module; delete `piper/file_input.py`.
- [x] Rename `tests/unit/test_file_input.py` → `tests/unit/test_inputs.py`; add direct `read_text_input` cases (text only / file only / both → error / neither → error). (Class renamed `TestBuildDocumentInput` → `TestInputs`, one TestClass for the module.)
- [x] `make agent-check` and `make agent-test` green.

## Phase 2 — Build the three mode packages (old surface still intact) ✅

Build the new world alongside the old one so the repo stays green mid-flight. Follow the anatomy and sample code in `wip/mode-split-clis.md` closely — the blocking file is spelled out there nearly in full.

- [x] `piper/blocking/__init__.py` + `cli.py`: `execute_pipe()` (one `client.execute` inside a Rich status), the demo commands, `_run()`. `generate-image`'s help text says it is expected to hit the hosted ~30s cap — that failure is the teaching moment.
- [x] `piper/attended/__init__.py` + `cli.py`: `start_and_wait()` — start, print `Run started: <id>` on stderr *before* polling, `wait_for_result` with `on_poll` status updates, `asyncio.CancelledError` → "resume with `piper detached wait <id>`" hint then re-raise. Docstring keeps the note that the SDK's `start_and_wait()` one-liner is the production shortcut; the starter spells it out on purpose.
- [x] `piper/detached/__init__.py` + `cli.py`: demo commands print the run id on **stdout** (pipeable: `RUN_ID=$(piper detached …)`) and the resume hint on stderr; `wait` (via `attend_run()`, prints raw `main_stuff` JSON — generic, no per-demo narrowing), `status` (coarse status + degraded caveat), `result` (no-wait `RunResultState` match: running → hint, completed → same JSON rendering as `wait`, failed → red + exit 1).
- [x] Mount the three groups in root `piper/cli.py` with `add_typer` in reading order, one-line help each ("Start here." / "…wait here for the result." / "…collect it later."). Keep the existing flat commands and `runs` group for now.
- [x] Add `piper.blocking`, `piper.attended`, `piper.detached` to `[tool.setuptools] packages` in `pyproject.toml`.
- [x] Resolve the design's open questions while writing the helpers: (a) how `pipelex-sdk` types `main_stuff` — helpers return it as the SDK types it, the generated-model `model_validate` in each command restores type safety; (b) confirm Typer lists groups in `add_typer` order.
- [x] New unit tests (one TestClass per module): `tests/unit/test_blocking_cli.py`, `test_attended_cli.py`, `test_detached_cli.py` — invoke through the **root** app (`["blocking", "extract-entities", …]`), patch the mode's public lifecycle helper, port the input-handling assertions from `test_cli.py` (text/file exclusivity, document envelope shape, missing-input errors) into their new homes.
- [x] `tests/unit/test_mode_symmetry.py`: assert the three groups expose identical demo command names (detached additionally exposes its lifecycle commands) — the drift guard for the full matrix.
- [x] `make agent-check` and `make agent-test` green.

**CHECKPOINT — end of Phase 2 (reached).** Both surfaces coexist and everything is green (`make agent-check`, `make agent-test`).

**Open questions — resolved:**
- **(a) `main_stuff` typing.** The SDK types it `Any` on both paths, deliberately (`RunResults.main_stuff: Any` — polymorphic content, and a falsy value like `[]` / `0` is valid; `PipelexExecuteResult.main_stuff` is an `Any` property that digs it out of the working memory). So all three lifecycle helpers return `Any` and each demo command's `Model.model_validate(main_stuff)` is what restores type safety, exactly as the design anticipated. Note this made the helper signatures *uniform*: all three return the resolved main output rather than an SDK envelope — `attend_run(run_id) -> Any` too, so `wait` and the e2e tests read the same as the other modes.
- **(b) Group ordering.** Typer lists groups in `add_typer` order (verified with `uv run piper --help`): blocking → attended → detached. No alphabetization. Locked in by `test_mode_symmetry.py::test_the_root_app_mounts_the_modes_in_reading_order`.

**Deviations from the design doc:** none of substance. Two notes:
- `_run()` is byte-identical across the three mode files (SDK errors → presented exit 1; `KeyboardInterrupt` → exit 130). The design's blocking sample omitted the `KeyboardInterrupt` arm; keeping it in all three preserves the "only the lifecycle helper differs" diff contract *and* the current exit-130-on-Ctrl-C behavior.
- `test_mode_symmetry.py` guards more than command names: it also compares each demo's **parameter list** across the three modes, so an argument added to one mode and forgotten in another fails too.

## Phase 3 — Remove the old surface ✅

- [x] Shrink root `piper/cli.py` to the thin assembler (module docstring, `load_dotenv` callback, three `add_typer` calls). Delete the flat demo commands, `runs_app`, `_dispatch`, `_run_cli`, `_render_result_state`, `_print_raw_results`, `ModeOption`, `MODE_HELP`, `METHODS_DIR`.
- [x] Delete `piper/runner.py`.
- [x] Reword the hints in `piper/errors.py` to group paths: timeout → "Rerun the same command with `piper attended …`"; lifecycle-unavailable → "use `piper blocking …`"; run-failed → "Inspect it with `piper detached status <id>`"; run-timeout → "Resume waiting with `piper detached wait <id>`". Update the module docstring (it names the per-command catch site).
- [x] Delete `tests/unit/test_cli.py` (its assertions were ported in Phase 2); update `tests/unit/test_errors.py` hint assertions.
- [x] Fix the `METHODS_DIR` imports in `tests/integration/test_fundamentals.py` and `tests/e2e/*` (compute locally or share via `tests/conftest.py`).
- [x] Re-point the e2e tests, one lifecycle per demo so every mode gets end-to-end coverage: `test_extract_entities` → `piper.blocking.cli.execute_pipe`; `test_summarize_pdf` → `piper.attended.cli.start_and_wait`; `test_generate_image` → `piper.detached.cli.start_pipe` then `attend_run` (also covers the run-id lifecycle). These are direct async helper calls, same style as today.
- [x] Repo-wide sweep for stale references (`runner`, `ExecutionMode`, `--mode`, `PIPELEX_EXECUTION_MODE`, `piper runs`, `file_input`) across `piper/`, `tests/`, `Makefile`, `.env.example`.
- [x] `make agent-check`, `make agent-test`, and `make tb` green.

**CHECKPOINT — end of Phase 3 (reached).** The new surface is the only surface; `make agent-check`, `make agent-test`, `make tb` all green, and `piper --help` lists exactly blocking → attended → detached.

**Beyond the plan, the sweep caught / decided:**
- **`METHODS_DIR` in tests, resolved two ways.** The integration test (mode-agnostic — it only checks the bundles parse and validate) computes it from the package: `Path(piper.__file__).parent / "methods"`. Each e2e test imports it from *the mode it exercises* (`from piper.blocking.cli import METHODS_DIR, execute_pipe`), which reads honestly and doubles as proof the mode file is self-sufficient. No `tests/conftest.py` plumbing was needed.
- **`tests/unit/test_generated_clients.py`** spoke the dead "cli dispatch" vocabulary (comment + `test_input_template_matches_cli_dispatch`). Reworded to name the mode CLIs; the test is now `test_input_template_matches_the_cli_inputs`.
- Remaining `runner` hits across the repo are all legitimate and unrelated: the *bare runner* concept in error hints/`.env.example`, `CliRunner` in tests, GitHub Actions runners.

## Phase 4 — Docs, changelog, packaging polish ✅

- [x] README: quick start becomes `uv run piper blocking extract-entities "…"` (result JSON only — no run-id chatter); "Execution modes" becomes a three-act tour in reading order (blocking → the generate-image timeout → attended → detached), reusing the existing mermaid sequence diagrams one per group; update the project-structure block and "Useful commands".
- [x] Starter `CLAUDE.md`: rewrite the architecture bullets — three mode sub-packages, the sharing rule, public lifecycle helper names, `runs` → `detached`, no `runner.py`/`ExecutionMode`.
- [x] `docs/`: sweep `docs/codegen.md` for stale CLI invocations; add a short `docs/cli-architecture.md` capturing the sharing rule + mode-file anatomy (the durable version of what `wip/mode-split-clis.md` designed — wip docs are not release-facing).
- [x] CHANGELOG entry (breaking): `--mode` and `PIPELEX_EXECUTION_MODE` are gone — the mode is the command group (`piper blocking|attended|detached <demo>`); `piper runs status|result|wait` is now `piper detached status|result|wait`. The previous `[Unreleased]` entry ("`--detach` is gone; detached is now a third `--mode` value") was **folded into** the new one rather than kept: it gave migration advice (`use --mode detached`) that this change invalidates, and neither `--detach` nor `--mode` survives into the next release, so a reader coming from v0.13.0 needs exactly one entry.
- [x] Verify the `/bootstrap` skill against the new layout: run its unit test (`tests/unit/test_bootstrap_script.py`), confirm the pyproject fixture/rename handles the added `piper.*` package entries; extend the fixture with a mode sub-package entry if it isn't representative. → The pyproject transform is generic (quoted-exact `"piper"` + `piper` followed by `.`/`_`/`/`), so `piper.blocking|attended|detached` ride the same rewrite unchanged. The fixture **was** unrepresentative (only `piper.generated.*` dotted entries, no nested source dir); it now carries a `piper.blocking` package entry and a nested `piper/blocking/cli.py` importing a sibling module, so the survivor check actually covers the new shapes.
- [x] Final gate: `make agent-check`, `make agent-test`, `make codegen-check`, `make tb` — all green.
- [~] `make test-inference` — **blocked by an environment outage, not by this change.** `PIPELEX_BASE_URL` points at `api-dev.pipelex.com`, whose authenticated routes are all returning a raw nginx `503 Service Temporarily Unavailable` (an HTML page from the reverse proxy — nothing reaches the app). `/v1/execute`, `/v1/start`, **and** `/v1/validate` all 503, including the pre-existing `test_validate_bundle` integration test whose request-building code this refactor never touched; only the gateway-served `/v1/version` answers (200). Re-run `make test-inference` once the dev runner is back up. Until then the re-pointed e2e paths are verified by review + collection (they import and collect cleanly): each is a direct async call to its mode's public lifecycle helper, the same style as before, and the helpers make the same SDK calls the deleted `runner.py` made.

**WRAP-UP.** ✅ Done — the mode split is implemented, the old surface is gone, and the suite is green offline. The lasting architectural notes now live in [`docs/cli-architecture.md`](docs/cli-architecture.md) (the sharing rule, the mode-file anatomy, why `attended`/`detached`) and in the starter `CLAUDE.md`; `wip/mode-split-clis.md` stays as the design record. The one open item is the live-API e2e run above, waiting on the dev environment.
