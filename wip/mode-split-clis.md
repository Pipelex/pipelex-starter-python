# Design: split the execution modes into three self-contained CLIs

- **Status:** design agreed — implementation plan not written yet
- **Date:** 2026-07-13
- **Scope:** `pipelex-starter-python` only

## The problem

The starter has two goals: (1) show how easy it is to call the Pipelex API to execute your methods, and (2) provide best-practice code you'd actually copy into your own project (or start from via the template).

The current architecture serves neither well. Every demo command takes a `--mode` option, which forces a dispatch chain: CLI command → `_dispatch()` helper → `match mode` → `piper/runner.py` helper → the actual SDK call. That `match/case` over `ExecutionMode` exists purely to showcase all three SDK lifecycles behind one option — no real project needs a runtime mode switch, so nobody would ever copy it. And a newcomer tracing "how do I call the API?" has to hop through four layers before reaching `client.execute(...)`, which is the opposite of demonstrating simplicity.

## The idea

Make each execution mode a completely separate CLI sub-package, discovered in reading order:

1. **`blocking`** — the front door. One call, one response. Trivially simple.
2. **`attended`** — start a durable run, wait here for the result. Still simple.
3. **`detached`** — start a durable run and exit; collect it later. Slightly more going on (a run-id lifecycle), but by the time a reader gets here they understand the model — and it's still copy-pasteable.

Each sub-package's `cli.py` is a **self-contained copy-paste unit**: the whole mode's story — commands, the SDK lifecycle, progress rendering — in one file, with no dispatch layer and no mode enum. The `--mode` option, `PIPELEX_EXECUTION_MODE` env var, `ExecutionMode`, `_dispatch()`, and `piper/runner.py` all disappear.

## Decisions taken (2026-07-13, with Louis)

| Question | Decision |
|---|---|
| CLI surface | **Command groups under one binary**: `piper blocking …`, `piper attended …`, `piper detached …`. One console script, one `--help` discovery page, bootstrap/rename stays trivial. (Rejected: three console scripts — heavier pyproject/bootstrap, no unified help.) |
| Naming | **`blocking` / `attended` / `detached`**. Attended and detached read as a natural pair — both run durably; the difference is who waits. (Rejected: `durable` for the middle one — detached is durable too, so the pair was misleading.) |
| Demo spread | **Full matrix**: every demo command exists in every mode group. Symmetric and diffable — compare two mode files and *only* the execution lifecycle differs. |
| Run lifecycle commands | **Inside `detached`**: `piper detached wait\|status\|result <run-id>`. The detached package is the complete "start now, collect later" story. (Rejected: top-level `piper runs` — scatters the detached story across two places.) |

## Target CLI surface

```
piper --help                        # lists the three modes, in reading order
piper blocking  extract-entities | summarize-pdf | generate-image
piper attended  extract-entities | summarize-pdf | generate-image
piper detached  extract-entities | summarize-pdf | generate-image
piper detached  wait | status | result   <run-id>
```

- The demo commands keep their existing arguments (`text`/`--file`, PDF path, prompt/`--file`). Only the mode selection moves from an option into the command path.
- There is no default mode anymore — the mode is explicit in every invocation, which is itself the lesson. The quick start becomes `piper blocking extract-entities "…"`, the cleanest possible first contact (no run-id chatter on stderr, just the JSON result).
- `piper blocking generate-image` is *expected to fail* on hosted (~30s cap) — that's deliberate. It's the teaching moment for why attended/detached exist, and its help text says so. The full matrix keeps this demo alive without special-casing.

## Package layout

```
piper/
  cli.py            # root Typer app: loads .env, add_typer × 3 in reading order — nothing else
  errors.py         # SHARED: SDK error → (message, hint) presentation — mode-agnostic
  inputs.py         # SHARED: read_text_input (text-or-file) + build_document_input (file → Document envelope)
  blocking/
    __init__.py
    cli.py          # the whole blocking mode in one file
  attended/
    __init__.py
    cli.py          # the whole attended mode in one file
  detached/
    __init__.py
    cli.py          # start commands + wait/status/result lifecycle in one file
  generated/        # unchanged
  methods/          # unchanged
```

**Sharing rule:** share what is orthogonal to execution modes — input encoding (`inputs.py`) and error presentation (`errors.py`). **Never share execution lifecycle code.** The moment two mode packages share a "runner" helper, the dispatch indirection is back. The copy-paste contract, stated in each mode file's docstring: *this file + `piper/inputs.py` + `piper/errors.py`*.

`piper/inputs.py` merges today's `file_input.py` (the `Document` envelope builder) with the `_read_text_input` text-or-file helper currently private to `cli.py`. One shared input module instead of two keeps the copy unit small. (`file_input.py` is deleted; its tests move accordingly.)

## Anatomy of a mode package

Every mode `cli.py` has the same four-part shape, so the three files diff cleanly:

1. **Module docstring** — the mode's contract in one paragraph, plus the copy-paste contract.
2. **App + consoles** — its own `typer.Typer` and its own `Console()` / `Console(stderr=True)` (two lines; not worth sharing — results on stdout stay pipeable, progress goes to stderr, same convention as today).
3. **The lifecycle helper** — one public async function that *is* the mode. This is the featured code, so it gets a public name (also what unit tests patch):
   - `blocking/cli.py` → `execute_pipe(...)`: `client.execute(...)`, done.
   - `attended/cli.py` → `start_and_wait(...)`: `client.start(...)`, print the run id (so Ctrl-C never loses the run), then `client.wait_for_result(...)` with a Rich status line.
   - `detached/cli.py` → `start_pipe(...)`: `client.start(...)`, return the id. Plus `attend_run(run_id)` backing the `wait` command, and thin fetchers backing `status` / `result`.
4. **The demo commands + a `_run()` wrapper** — each command parses its input, reads its bundle, awaits the lifecycle helper through `_run()` (asyncio.run + the one `except (PipelineRequestError, httpx.HTTPStatusError)` presenting via `piper.errors`), narrows into its generated model, prints JSON.

### `piper/blocking/cli.py` — the proof of goal 1

The file a Pipelex newcomer reads first, in full (imports elided):

```python
"""The blocking CLI — one request, one response, done.

Simplest way to run a method: `client.execute(...)` and you have the result.
On the hosted API a run longer than ~30s is cut off (try `generate-image` to
see it) — that's what `piper attended` and `piper detached` are for.

Copy-paste unit: this file + piper/inputs.py + piper/errors.py.
"""

METHODS_DIR = Path(__file__).parent.parent / "methods"

app = typer.Typer(no_args_is_help=True, help="Run a demo with a single blocking call (~30s cap on hosted).")
output_console = Console()
progress_console = Console(stderr=True)


async def execute_pipe(*, pipe_code: str, bundle: str, inputs: dict[str, Any]) -> Any:
    """The whole blocking lifecycle: one call, the result comes back in the response."""
    async with PipelexAPIClient() as client:
        with progress_console.status("Running…"):
            result = await client.execute(pipe_code=pipe_code, mthds_contents=[bundle], inputs=inputs)
    return result.main_stuff


@app.command(name="extract-entities")
def extract_entities(
    text: Annotated[str | None, typer.Argument(help="The text to extract entities from.")] = None,
    file: Annotated[Path | None, typer.Option("--file", help="Read the input text from a file.")] = None,
) -> None:
    """Extract people, organizations, and dates from a piece of text."""
    input_text = read_text_input(text=text, file=file)
    bundle = (METHODS_DIR / "extract-entities" / "main.mthds").read_text()
    main_stuff = _run(execute_pipe(pipe_code="extract_entities", bundle=bundle, inputs={"text": input_text}))
    entities = ExtractedEntities.model_validate(main_stuff)
    output_console.print_json(data=entities.model_dump())

# … summarize-pdf and generate-image follow the same shape …

def _run(coro: Coroutine[Any, Any, ResultT]) -> ResultT:
    """Await the lifecycle, presenting SDK errors as clean exits."""
    try:
        return asyncio.run(coro)
    except (PipelineRequestError, httpx.HTTPStatusError) as exc:
        presentation = present_error(exc)
        progress_console.print(f"[red]Error:[/red] {presentation.message}")
        if presentation.hint:
            progress_console.print(f"[yellow]Hint:[/yellow] {presentation.hint}")
        raise typer.Exit(1) from exc
```

Reading path from command to API call: `extract_entities` → `execute_pipe` → `client.execute`. Two hops, both in the same file, no enum, no dispatch. A nice simplification falls out for free: today `run_blocking` adapts its result onto `RunResults` purely so `_dispatch` could return one type across modes — with no dispatch, each mode uses its natural SDK type and the adaptation is deleted.

### `piper/attended/cli.py`

Same shape; only the lifecycle helper differs:

```python
async def start_and_wait(*, pipe_code: str, bundle: str, inputs: dict[str, Any]) -> Any:
    """The attended lifecycle: start a durable run, print its id, wait here for the result."""
    async with PipelexAPIClient() as client:
        start_result = await client.start(pipe_code=pipe_code, mthds_contents=[bundle], inputs=inputs)
        run_id = start_result.pipeline_run_id
        progress_console.print(f"Run started: [bold]{run_id}[/bold]")
        with progress_console.status(f"Run {run_id[:8]}… in progress") as status:
            def on_poll(info: PollInfo) -> None:
                status.update(f"Run {run_id[:8]}… in progress — {info.elapsed_seconds:.0f}s, poll #{info.attempt}")
            try:
                results = await client.wait_for_result(run_id, options=WaitForResultOptions(on_poll=on_poll))
            except asyncio.CancelledError:
                progress_console.print(f"\nInterrupted — the run is still executing. Resume with: [bold]piper detached wait {run_id}[/bold]")
                raise
    return results.main_stuff
```

The docstring keeps the current teaching note: the SDK's `start_and_wait()` one-liner is the production shortcut when you don't care which path runs — this starter spells the lifecycle out because teaching it is the point.

Note the Ctrl-C hint now points at `piper detached wait <id>` — and reads *better* than before: an interrupted attended run has literally become a detached run, so you resume it with the detached tooling. This cross-mode reference is a string, not an import; the packages stay decoupled.

### `piper/detached/cli.py`

The demo commands call `start_pipe(...)`, print the run id on stdout (pipeable — `RUN_ID=$(piper detached generate-image "…")` works) and the resume hint on stderr. The lifecycle commands complete the story:

- `wait <run-id>` — `attend_run()`: poll to completion with the same Rich status line, print the raw `main_stuff` as JSON (generic — no per-demo narrowing, since any run id can be waited on).
- `status <run-id>` — coarse status via `client.get_run_status`, including the degraded-status caveat.
- `result <run-id>` — no-wait fetch via `client.get_run_result`, rendering the running/completed/failed states (the `RunResultState` match stays, unchanged from today's `runs result`).

This is the "third act" file: more commands than the others, but each one is still a straight line to a single SDK call.

## What gets deleted

- `piper/runner.py` — dissolved into the three mode files.
- `ExecutionMode`, the `--mode` option, `ModeOption`, `MODE_HELP`, the `PIPELEX_EXECUTION_MODE` env var.
- `_dispatch()` and the `RunResults` adaptation in `run_blocking`.
- The top-level `runs` sub-app (absorbed by `detached`).
- `piper/file_input.py` (merged into `piper/inputs.py`).

`piper/cli.py` shrinks to the root app: the `load_dotenv()` callback and three `add_typer` calls, in reading order, with one-line group help texts that teach the progression ("Start here." / "…wait here for the result." / "…collect it later.").

## Error hints

`piper/errors.py` stays shared and mode-agnostic, but its hints currently speak `--mode` and `piper runs`; they become group-path commands:

- `PipelineExecuteTimeoutError` → "Rerun the same command with `piper attended …` — the durable path survives long runs."
- `RunLifecycleUnavailableError` → "You are talking to a bare runner — use `piper blocking …`."
- `RunFailedError` → "Inspect it with `piper detached status <id>`."
- `RunTimeoutError` → "Resume waiting with `piper detached wait <id>`."

## Duplication policy and the drift guard

The full matrix means the demo commands are deliberately near-duplicated across the three mode files. That duplication *is* the pedagogy — diff `blocking/cli.py` against `attended/cli.py` and the only difference is the lifecycle helper — but it can drift. Two guards:

1. Each mode file's docstring states the mirror contract: demo commands identical across modes, only the lifecycle differs.
2. A symmetry unit test (e.g. `tests/unit/test_mode_symmetry.py`) asserts the three groups expose the same demo command names (detached additionally exposing its lifecycle commands), so a demo added to one mode and forgotten in another fails CI.

## Tests

- `tests/unit/test_cli.py` splits into one module per mode (one TestClass per module, per workspace rules): `test_blocking_cli.py`, `test_attended_cli.py`, `test_detached_cli.py`, plus `test_mode_symmetry.py`. Mocking gets simpler and more honest: each test patches its mode's *public* lifecycle helper (`piper.blocking.cli.execute_pipe`, `piper.attended.cli.start_and_wait`, `piper.detached.cli.start_pipe` / `attend_run`) instead of today's runner functions — no more "which runner function does this mode hit" indirection in the tests either.
- Mode-specific assertions that were previously option-flavored become group-flavored: the detached demo prints the run id on stdout; the bad-mode test (`--mode bogus`) becomes a bad-group test (unknown command → non-zero, courtesy of Typer).
- E2E suggestion: assign one lifecycle per demo so all three modes get end-to-end coverage without tripling the suite — `extract-entities` via blocking, `summarize-pdf` via attended, `generate-image` via detached (`start` then `wait`). The generate-image assignment doubles as e2e coverage of the run-id lifecycle.
- `tests/unit/test_errors.py` hint assertions update to the new command paths; `test_file_input.py` follows the module merge into `inputs.py`.

## Packaging, bootstrap, docs

- `pyproject.toml`: add `piper.blocking`, `piper.attended`, `piper.detached` to `[tool.setuptools] packages`. `[project.scripts]` unchanged — still the single `piper = "piper.cli:app"` entry, which is what keeps the `/bootstrap` rename trivial (verify the bootstrap script's package rename handles the nested `piper.*` imports; it should, since it rewrites the import prefix globally).
- README: the quick start becomes `piper blocking extract-entities "…"`; the "Execution modes" section becomes a three-act tour matching the reading order (blocking → the timeout → attended → detached), reusing the existing mermaid sequence diagrams one-per-group; the project-structure block and "Useful commands" update to the new paths.
- `CLAUDE.md` (starter repo): the architecture bullet describing `runner.py` / `ExecutionMode` / `--mode` is rewritten around the three sub-packages and the sharing rule.
- CHANGELOG (at implementation time): breaking — `--mode` and `PIPELEX_EXECUTION_MODE` are gone, the mode is now the command group (`piper blocking|attended|detached …`); `piper runs …` is now `piper detached wait|status|result`.

## Rejected alternatives (summary)

- **Three console scripts** (`piper-blocking`, …) — real separation, but three pyproject entries to bootstrap-rename and no single `--help` telling the story.
- **`durable` as the middle group's name** — detached runs are durable too; `attended`/`detached` names the actual axis (who waits).
- **Curated demo spread** (each mode carrying only the demos that motivate it) — shorter files, but breaks the diffability of the full matrix and forbids legitimate combinations (e.g. summarize-pdf detached).
- **Top-level `piper runs` group** — "execute vs inspect" separation is principled, but it splits the detached story across two places, which is exactly the scatter this redesign removes.
- **A shared runner module called by all three packages** — recreates the indirection under a new name; lifecycle code is never shared, period.

## Open questions

- **`main_stuff` typing in the lifecycle helpers:** the helpers return the SDK-resolved `main_stuff` (typed as the SDK types it). If the SDK's typing is loose (`Any`), the generated-model `model_validate` narrowing in each command is what restores type safety — acceptable, but worth a look at the SDK types during implementation.
- **Group help ordering:** Typer lists groups in `add_typer` order with default settings — confirm at implementation time (if it alphabetizes, blocking/attended/detached conveniently still reads okay, but verify).
- **`piper detached result` vs `wait` output parity:** both print raw `main_stuff` JSON; keep the rendering identical so scripts can use either interchangeably.
