# Generated typed clients

The typed models this starter parses run results into are **generated from the `.mthds` bundles**, not hand-written. The method definition is the single source of truth: its output concepts are projected into Pydantic models, so editing a bundle and regenerating is all it takes to keep the Python side in sync.

## What is generated, and where

| Artifact | Path | Committed | Edited by hand |
| --- | --- | --- | --- |
| Typed models (one module per method) | `piper/generated/<method>/models.py` | Yes | **Never** — regenerate instead |
| Artifact-set lock | `piper/generated/<method>/codegen.lock` | Yes | Never |

Each `models.py` starts with a `pipelex-codegen-stamp` header recording the source crate fingerprint, engine version, projection, and a content hash. The sibling `codegen.lock` records the generated artifact set. Together they make drift detectable offline.

The demo commands in each mode CLI (`piper/blocking/cli.py`, `piper/attended/cli.py`) import the generated models and only add the bundle path, the pipe code, and the narrowing line (`Model.model_validate(main_stuff)`) — nothing method-shaped is hand-written.

## Workflow

Edit a bundle (`piper/methods/<method>/main.mthds`), then:

```bash
make codegen        # regenerate the models through the hosted API (needs PIPELEX_API_KEY)
make codegen-check  # offline drift check: exit 0 current · 1 drift · 2 no lock
```

`make codegen` needs an API key and nothing else. `scripts/codegen.py` discovers every method under `piper/methods/`, posts each one's `.mthds` files to `POST /v1/codegen` with `pipelex-sdk` — the same dependency the starter already runs methods with — and writes the response to disk with the SDK's `write_codegen_tree`. A new method under `piper/methods/` is picked up by the next run with no change to the script or the Makefile; it only has to be added to the `packages` / `package-data` lists in `pyproject.toml` to ship in a wheel. The script needs the `pipelex-sdk` release that ships `write_codegen_tree`; if the installed SDK predates it, the script says which symbol is missing and what to do about it rather than failing with an import error.

The tree is written **verbatim**: every artifact at the path the server named it, the lock as `codegen.lock`, byte for byte. That fidelity is the whole trust chain — it makes the tree identical to what a local `pipelex codegen types` run would have written, which is what lets the offline check pass on it. Writing is the SDK's job rather than this script's for the same reason: `write_codegen_tree` validates every path before writing, refuses to overwrite a file codegen does not own, rewrites only what changed (so regenerating a current tree is a true no-op), and prunes stamped artifacts that dropped out of the set. Do not run a formatter over the result.

`codegen-check` is pure hashing against each `codegen.lock` — no engine boot, no network, no API key. It reports drift by category: missing (a locked artifact was deleted), modified (an artifact no longer matches the locked hash), hand-edited (a generated file was touched below its stamp), and orphan (a stale stamped file the lock no longer lists).

One thing the offline check cannot see is a bundle edit that was never regenerated — detecting that requires resolving the bundle, which is the engine's job. The guard for it is `make codegen` itself: regeneration is write-if-changed, so running it and checking `git diff` is clean proves the committed clients match the bundles.

The generated files are excluded from ruff in `pyproject.toml`: reformatting them would change their content hash and trip the drift check. They still go through pyright and mypy like any other code.

## The one half still on the `pipelex` CLI: `codegen-check`

This starter talks to the **hosted Pipelex API** through `pipelex-sdk`; the `pipelex` runtime is not installed here, and `make codegen` no longer wants it. The offline check is the remaining exception — it is pure local hashing that `pipelex-sdk` does not expose yet — so until it does, point the `PIPELEX` make variable at a pipelex install of **0.47.0 or newer**:

```bash
PIPELEX=/path/to/pipelex/.venv/bin/pipelex make codegen-check
```

0.47.0 is the floor because each committed `codegen.lock` carries a `lock_version` key, and the `CodegenLock` model before that release forbids unknown keys: an older CLI answers `codegen check` with a lock-parse error instead of a drift verdict. When the SDK ships that check, this half moves onto it in one step and the `PIPELEX` variable goes away. Until then, `codegen-check` is the one target a fresh clone cannot run on its own, and CI runs the offline floor below instead.

## There is no committed `inputs.template.json`

Earlier versions of this starter committed a generated `piper/methods/<method>/inputs.template.json` beside each bundle — a scaffold naming the method's inputs, which you copied and filled in. Those files are gone, deliberately:

- **Nothing read them.** Every demo runs with no arguments because `piper/inputs.py` carries a built-in sample per method, and the mode CLIs build their `inputs` dict in code. The templates were documentation in a `.json` file, and documentation that no code reads goes stale without anything noticing.
- **There is nothing to regenerate them from here.** The route that projected them is retired, and the projection now lives in the MTHDS standard's own package (`mthds.protocol.inputs_template`) over the input-form descriptor. Reproducing it would mean a second API call per method and a direct dependency on the standard's package, to write a file the app never opens.
- **The inputs contract is guarded where it is authored.** `tests/unit/test_generated_clients.py` reads each `main.mthds` and asserts the bundle declares exactly the inputs its mode CLIs pass. That holds the moment the bundle is edited, whereas a committed template only held after somebody remembered to regenerate.
- **`pipelex-starter-js` commits none either.** The two starters are meant to be one reference in two languages, and an asymmetry neither language needs is a difference to remove.

When you do want a fill-in template for a method — to hand an agent, or to drive a run from a file — ask the API for the method's input form and project one:

```python
from mthds.protocol.inputs_template import InputsTemplateFormat, render_inputs_template
from pipelex_sdk.validation_models import VALIDATION_VIEW_INPUT_FORM, PipelexValidationReport

report = await client.validate(mthds_contents=[bundle], views=[VALIDATION_VIEW_INPUT_FORM])
if not isinstance(report, PipelexValidationReport):
    raise SystemExit(report.message)
if report.input_form is None:  # the view is lenient-ignored by a runner that does not serve it
    raise SystemExit("this API did not return an input form — it predates the input_form view")
descriptor = report.input_form["extract_entities.extract_entities"]  # pipe_ref -> descriptor
print(render_inputs_template(descriptor=descriptor, explicit=False, output_format=InputsTemplateFormat.JSON))
```

The descriptor is the standard's own artifact: the inputs, their kinds, and which are required. Rendering it is the standard's package's job, and `client.prepare_inputs(files=…, inputs=…)` walks the same descriptor internally when it uploads a method's file inputs. That is where a template comes from now — derived when you need it, against the method as it is today, rather than committed and trusted.

## Offline test floor

`tests/unit/test_generated_clients.py` runs everywhere (no pipelex CLI, no API key): it checks that the generated modules import, carry the stamp + lock, round-trip their own serialization, and that each bundle declares exactly the inputs its mode CLIs send — so an input renamed in a bundle without the CLIs following fails in CI even before `codegen-check` is wired in.
