# CLI architecture: three modes, three self-contained files

This starter has two jobs: show how easy it is to call the Pipelex API, and be code you would actually copy into your own project. Both push in the same direction — **the shortest possible reading path from a command to the SDK call it makes**.

So the execution mode is not an option you pass, it is the command group you type:

```
piper blocking  extract-entities     # or summarize-pdf, generate-image
piper attended  extract-entities     # or summarize-pdf, generate-image
piper detached  extract-entities     # or summarize-pdf, generate-image
piper detached  wait <run-id>        # or status, result
```

## The layout

```
piper/
  cli.py            # the assembler: load .env, mount the three groups in reading order. Nothing else.
  inputs.py         # SHARED — prepare the inputs (text/file; incl. the hosted file upload)
  errors.py         # SHARED — present an SDK error
  usage.py          # SHARED — read + print the run's cost report
  blocking/cli.py   # the whole blocking mode
  attended/cli.py   # the whole attended mode
  detached/cli.py   # the whole detached mode + the run-id lifecycle commands
```

Each mode file is a **copy-paste unit**: that file plus `inputs.py` plus `errors.py` plus `usage.py` is all the *lifecycle* code you need to lift the mode into your own project. A runnable copy also carries the method-specific artifacts the demos reference — the bundles (`piper/methods/`), the generated models (`piper/generated/`), and the sample document — but those are exactly what you replace with your own method anyway. No other code in `piper/` is load-bearing for a mode.

## The sharing rule

> Share what is orthogonal to execution. **Never share lifecycle code.**

Input preparation, error presentation, and cost-report formatting don't care how a run is executed, so they are shared. The lifecycle — what you call, in what order, and what you do while waiting — *is* the mode, so it lives in the mode's own file, in full, even when that means near-duplicating a demo command across three files. (Cost *extraction* is the one seam that differs per mode — the durable modes read a typed `RunResults.tokens_usages`, blocking lifts the same records raw off its execute result — so each helper picks the right `usage.py` reader; the *formatting* is shared.)

That duplication is deliberate, and it is the pedagogy: diff `blocking/cli.py` against `attended/cli.py` and the only thing that differs is the lifecycle helper. The moment two modes reach for a shared `runner` helper, a dispatch layer is back between the command and the SDK, and the reading path grows a hop. (The earlier version of this starter had exactly that: a `--mode` option → `_dispatch()` → `match ExecutionMode` → `runner.py` → the SDK. Four layers to answer "how do I call the API?".)

The duplication can drift, so `tests/unit/test_mode_symmetry.py` holds it in place: every demo exists in every mode, with the same parameters. A demo added to one mode and forgotten in another fails CI.

## Anatomy of a mode file

All three have the same four-part shape, so they diff cleanly:

1. **Module docstring** — the mode's contract in a paragraph, plus its copy-paste contract.
2. **App + consoles** — its own `typer.Typer`, its own `Console()` (stdout, for results — pipeable) and `Console(stderr=True)` (stderr, for progress chatter).
3. **The lifecycle helper** — one public async function that *is* the mode (`detached` adds the run-id lifecycle helpers described below). It gets a public name because it is the featured code, and it is what the unit tests patch and the e2e tests call directly.
4. **The demo commands + a private `_run()`** — each command reads its input, reads its bundle, awaits the lifecycle helper through `_run()` (`asyncio.run` + the single `except (PipelineRequestError, httpx.HTTPStatusError)` that presents via `piper/errors.py`), narrows the result into its *generated* model, prints JSON to stdout, and prints the run's cost report to stderr.

The lifecycle helpers take the bundle as `mthds_contents: list[str]` — one string per `.mthds` file — and pass it straight to the SDK. The three demos are single-file methods, so each reads its `main.mthds` and wraps it as `mthds_contents=[bundle]`. A method dir may instead hold several `.mthds` files (a multi-file bundle split across pipes with `signature_for` cross-file declarations); read them all with `[p.read_text() for p in sorted((METHODS_DIR / "<name>").glob("*.mthds"))]` and hand that list to the helper unchanged. Concatenating the files into one string would be invalid TOML — the list is the interface for exactly this reason.

| Mode | Lifecycle helper | SDK calls | What the demo prints |
| --- | --- | --- | --- |
| `blocking` | `execute_pipe()` | `client.execute` | the result as JSON, then a cost report (stderr) |
| `attended` | `start_and_wait()` | `client.start` + `client.wait_for_result` | the run id (stderr), then the result as JSON + a cost report (stderr) |
| `detached` | `start_pipe()` | `client.start` | the run id, bare, on **stdout** (no cost — the run isn't done yet) |

`detached` additionally owns the run-id lifecycle: `attend_run()` backs `wait`, and thin fetchers back `status` and `result`. It is the only mode with more than the demos, because "start now, collect later" is only a complete story if you can come back for the result. The cost report lands where the *result* does, so in detached mode it prints from `wait` and `result` (collection time), not from the start-only demo commands.

The result-producing helpers — `execute_pipe()`, `start_and_wait()`, and detached's `attend_run()` — return a `(main_stuff, usage)` pair: the run's resolved `main_stuff` (the SDK types it `Any` — the content is polymorphic) and its `RunUsage` (the per-call cost/token records, read via `piper/usage.py`). In blocking and attended mode each demo command narrows `main_stuff` with `Model.model_validate(main_stuff)`, which is what restores type safety (the models are generated from the bundles — see [codegen.md](codegen.md)), then prints `usage` as a cost report to stderr. Detached is different by design: `start_pipe()` returns only the run id, and the run-id commands (`wait`, `result`) print the output generically — at collection time the command doesn't know which method the run executed, so there is no model to narrow into.

### Cost reports and file upload

Two SDK capabilities show up in every result-producing path:

- **Cost report.** A completed run reports what its inference calls consumed. `piper/usage.py` reads that off the SDK result (`usage_from_results` for the durable modes' typed `RunResults.tokens_usages`; `usage_from_execute` for blocking, which still lifts the records raw off `pipe_output`) and `print_cost_report` renders a per-call table plus a USD total — always to **stderr**, so stdout stays the clean, pipeable result. It respects the SDK's semantics: an unpriced call (`cost is None`: mock / own-GPU / dry-run) is not a zero-cost call, and token categories are never summed (`input_cached` is a subset of `input`).
- **File upload.** `summarize-pdf` feeds a *file* to a pipe. A hosted run cannot see your filesystem, so `inputs.py`'s `upload_document_input` uploads the file first (`client.upload_file`) and the run request carries only the returned `pipelex-storage://` URI — never the bytes. Preparation is a step of its own, before the run: an unreadable file or an upload-incapable deployment fails before any run is created, presented through the same `piper/errors.py` path as every other SDK error.

## Two conventions worth copying

**stdout is the result; stderr is everything else.** Progress spinners, run ids in attended mode, error messages, and hints all go to stderr, so stdout stays pipeable. In detached mode the run id *is* the result, so it goes to stdout bare (`print`, not Rich) — `RUN_ID=$(piper detached generate-image "…")` just works.

**SDK errors are presented once, at the root of the command.** `_run()` catches `PipelineRequestError` (the base of every error the SDK client raises) and the raw `httpx.HTTPStatusError` its protocol routes surface, maps it to a `(message, hint)` pair via `piper/errors.py`, and exits non-zero. Ctrl-C is handled separately: the durable lifecycle helpers catch the cancellation just long enough to print the resume hint before re-raising, and `_run()` maps the resulting `KeyboardInterrupt` to exit 130. Beyond those two, nothing is caught: an unexpected exception crashes loudly with its traceback, which is what you want while you are building.

The protocol routes (`execute`/`start`/`runs/*`) surface a non-2xx as a raw `httpx.HTTPStatusError`, whose default string is useless (`Client error '400 Bad Request' for url …` + an MDN link). `piper/errors.py` instead reads the API's RFC 7807 **problem+json** body and shows the server's own `detail`, branching on the structured `error_type` (never the transport status) for the cases worth a hint — a `/start` against a synchronous-only runner (`StartRequiresAsyncOrchestration`) is presented with a hint pointing at `piper blocking`.

The hints name the mode *groups*, because the fix for a failed run is usually another group: a blocking run that hit the ~30s cap tells you to rerun it with `piper attended`; a run that timed out while you waited tells you to resume it with `piper detached wait <id>`; a durable run against a runner that can't do them tells you to use `piper blocking`.

**Every demo runs with zero arguments.** When you give neither an argument nor `--file`, the input helper returns a bundled sample (`piper/inputs.py`'s `SAMPLE_*` constants), and the command prints a one-line notice on stderr saying so. A fresh clone shows a working result on its very first command once your API key is set; stdout stays the clean, pipeable result because the notice is on stderr. Sample data is orthogonal to execution, so like input encoding it is shared, not duplicated per mode.

## Why `attended` and `detached`, not `durable`

Both start the *same* durable run — one that lives server-side behind an id and outlives your terminal. The only difference is who waits: `attended` polls from your terminal, `detached` exits and lets you collect the result later. Naming the middle one "durable" would suggest detached is not, which is exactly backwards. The mode names the axis that actually differs.

A nice consequence: Ctrl-C during an attended run doesn't lose anything — it has just turned into a detached run, and the hint you get says so (`piper detached wait <id>`).
