# CLI architecture: three modes, three self-contained files

This starter has two jobs: show how easy it is to call the Pipelex API, and be code you would actually copy into your own project. Both push in the same direction — **the shortest possible reading path from a command to the SDK call it makes**.

So the execution mode is not an option you pass, it is the command group you type:

```
piper blocking  extract-entities | summarize-pdf | generate-image
piper attended  extract-entities | summarize-pdf | generate-image
piper detached  extract-entities | summarize-pdf | generate-image
piper detached  wait | status | result   <run-id>
```

## The layout

```
piper/
  cli.py            # the assembler: load .env, mount the three groups in reading order. Nothing else.
  inputs.py         # SHARED — encode the inputs
  errors.py         # SHARED — present an SDK error
  blocking/cli.py   # the whole blocking mode
  attended/cli.py   # the whole attended mode
  detached/cli.py   # the whole detached mode + the run-id lifecycle commands
```

Each mode file is a **copy-paste unit**: that file plus `inputs.py` plus `errors.py` is everything you need to lift the mode into your own project. Nothing else in `piper/` is load-bearing for it.

## The sharing rule

> Share what is orthogonal to execution. **Never share lifecycle code.**

Input encoding and error presentation don't care how a run is executed, so they are shared. The lifecycle — what you call, in what order, and what you do while waiting — *is* the mode, so it lives in the mode's own file, in full, even when that means near-duplicating a demo command across three files.

That duplication is deliberate, and it is the pedagogy: diff `blocking/cli.py` against `attended/cli.py` and the only thing that differs is the lifecycle helper. The moment two modes reach for a shared `runner` helper, a dispatch layer is back between the command and the SDK, and the reading path grows a hop. (The earlier version of this starter had exactly that: a `--mode` option → `_dispatch()` → `match ExecutionMode` → `runner.py` → the SDK. Four layers to answer "how do I call the API?".)

The duplication can drift, so `tests/unit/test_mode_symmetry.py` holds it in place: every demo exists in every mode, with the same parameters. A demo added to one mode and forgotten in another fails CI.

## Anatomy of a mode file

All three have the same four-part shape, so they diff cleanly:

1. **Module docstring** — the mode's contract in a paragraph, plus its copy-paste contract.
2. **App + consoles** — its own `typer.Typer`, its own `Console()` (stdout, for results — pipeable) and `Console(stderr=True)` (stderr, for progress chatter).
3. **The lifecycle helper** — one public async function that *is* the mode. It gets a public name because it is the featured code, and it is what the unit tests patch and the e2e tests call directly.
4. **The demo commands + a private `_run()`** — each command reads its input, reads its bundle, awaits the lifecycle helper through `_run()` (`asyncio.run` + the single `except (PipelineRequestError, httpx.HTTPStatusError)` that presents via `piper/errors.py`), narrows the result into its *generated* model, prints JSON.

| Mode | Lifecycle helper | SDK calls | What the demo prints |
| --- | --- | --- | --- |
| `blocking` | `execute_pipe()` | `client.execute` | the result, as JSON |
| `attended` | `start_and_wait()` | `client.start` + `client.wait_for_result` | the run id (stderr), then the result as JSON |
| `detached` | `start_pipe()` | `client.start` | the run id, bare, on **stdout** |

`detached` additionally owns the run-id lifecycle: `attend_run()` backs `wait`, and thin fetchers back `status` and `result`. It is the only mode with more than the demos, because "start now, collect later" is only a complete story if you can come back for the result.

All three lifecycle helpers return the run's resolved `main_stuff` (the SDK types it `Any` — the content is polymorphic), and each command's `Model.model_validate(main_stuff)` is what restores type safety. The models are generated from the bundles; see [codegen.md](codegen.md).

## Two conventions worth copying

**stdout is the result; stderr is everything else.** Progress spinners, run ids in attended mode, error messages, and hints all go to stderr, so stdout stays pipeable. In detached mode the run id *is* the result, so it goes to stdout bare (`print`, not Rich) — `RUN_ID=$(piper detached generate-image "…")` just works.

**Errors are caught once, at the root of the command.** `_run()` catches `PipelineRequestError` (the base of every error the SDK client raises) and the raw `httpx.HTTPStatusError` its protocol routes surface, maps it to a `(message, hint)` pair via `piper/errors.py`, and exits non-zero. Nothing else is caught anywhere: an unexpected exception crashes loudly with its traceback, which is what you want while you are building.

The hints name the mode *groups*, because the fix for a failed run is usually another group: a blocking run that hit the ~30s cap tells you to rerun it with `piper attended`; a run that timed out while you waited tells you to resume it with `piper detached wait <id>`.

## Why `attended` and `detached`, not `durable`

Both start the *same* durable run — one that lives server-side behind an id and outlives your terminal. The only difference is who waits: `attended` polls from your terminal, `detached` exits and lets you collect the result later. Naming the middle one "durable" would suggest detached is not, which is exactly backwards. The mode names the axis that actually differs.

A nice consequence: Ctrl-C during an attended run doesn't lose anything — it has just turned into a detached run, and the hint you get says so (`piper detached wait <id>`).
