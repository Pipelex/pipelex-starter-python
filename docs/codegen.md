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

`make codegen` needs an API key and nothing else. `scripts/codegen.py` discovers every method under `piper/methods/`, posts each one to `POST /v1/codegen` with `pipelex-sdk` — the same dependency the starter already runs methods with — and writes the response to disk with the SDK's `write_codegen_tree`. A new method under `piper/methods/` is picked up by the next run with no change to the script, the Makefile or `pyproject.toml`: the packages are discovered (`[tool.setuptools.packages.find]`) and the per-method `codegen.lock` ships through a package-data glob, so what a wheel carries is derived too. `write_codegen_tree` and the codegen request envelope (`pipelex_sdk.crate_models`) arrived in `pipelex-sdk` 0.10.0, which is the floor `pyproject.toml` declares, so a checkout installed from the lock has them and the script imports them plainly.

The tree is written **verbatim**: every artifact at the path the server named it, the lock as `codegen.lock`, byte for byte. That fidelity is the whole trust chain — it makes the tree identical to what a local `pipelex codegen types` run would have written, which is what lets the offline check pass on it. Writing is the SDK's job rather than this script's for the same reason: `write_codegen_tree` validates every path before writing, refuses to overwrite a file codegen does not own, rewrites only what changed (so regenerating a current tree is a true no-op), and prunes stamped artifacts that dropped out of the set. Do not run a formatter over the result.

`codegen-check` is pure hashing against each `codegen.lock` — no engine boot, no network, no API key. It reports drift by category: missing (a locked artifact was deleted), modified (an artifact no longer matches the locked hash), hand-edited (a generated file was touched below its stamp), and orphan (a stale stamped file the lock no longer lists).

One thing the offline check cannot see is a bundle edit that was never regenerated — detecting that requires resolving the bundle, which is the engine's job. The guard for it is `make codegen` itself: regeneration is write-if-changed, so running it and checking `git diff` is clean proves the committed clients match the bundles.

The generated files are excluded from ruff in `pyproject.toml`: reformatting them would change their content hash and trip the drift check. They still go through pyright and mypy like any other code, and so does `scripts/codegen.py` — `scripts` is named in `[tool.pyright] include` and `[tool.mypy] packages`, so the script's use of the SDK is verified by `make agent-check` rather than by hand.

## Two source kinds

A method directory under `piper/methods/` names its closure in one of exactly two ways, and never both:

| Kind | What the directory holds | What is sent to `POST /v1/codegen` |
| --- | --- | --- |
| **Bundle** | `.mthds` files — the whole closure, nested files included | inline `files`, each labelled with its repo-relative path so a server diagnostic names a file you can open |
| **Manifest** | `method.json`, holding exactly one of `method_id` or `method_ref` | that selector, resolved server-side |

The three demos are bundles. A manifest is what [`make add-method`](add-method.md) writes for a method that lives on the platform (a catalog id) or in a published package (an address), and it holds the selector and nothing else:

```json
{ "method_ref": "github.com/Pipelex/methods/text_stats@v0.1.1" }
```

Keeping it under `piper/methods/` rather than beside the generated tree is what made the second kind almost free. `piper/methods/` stays the source of truth and `piper/generated/` stays purely derived, so `make codegen` regenerates a selector-sourced tree beside a bundle-sourced one through the same call and the same writer, rather than being a second regeneration path with its own rules. A directory holding both kinds is refused rather than resolved in favour of one: the two would disagree about where the tree came from.

The offline gates read the generated tree, so both kinds are covered by them identically. What a manifest-sourced method has no local answer for is the bundle-versus-CLI input check (`test_bundle_declares_exactly_the_cli_inputs`) — there is no bundle on disk to read — and the equivalent there is the scaffolder itself, which derives the command's parameters from the method's own input-form descriptor rather than from anything hand-written.

## The one half still on the `pipelex` CLI: `codegen-check`

This starter talks to the **hosted Pipelex API** through `pipelex-sdk`; the `pipelex` runtime is not installed here, and `make codegen` no longer wants it. This one target is the remaining exception, and it is no longer a missing capability: `pipelex-sdk` ships the same offline check as `pipelex_sdk.codegen_check.run_codegen_check` from 0.10.0, the floor this starter declares, and the test floor below already runs it. It is the make target that has not been moved onto it — so until it is, point the `PIPELEX` make variable at a pipelex install of **0.47.0 or newer**:

```bash
PIPELEX=/path/to/pipelex/.venv/bin/pipelex make codegen-check
```

0.47.0 is the floor because each committed `codegen.lock` carries a `lock_version` key, and the `CodegenLock` model before that release forbids unknown keys: an older CLI answers `codegen check` with a lock-parse error instead of a drift verdict. Moving this target onto the SDK drops both the variable and that floor in one step. Until then, `codegen-check` is the one target a fresh clone cannot run on its own — which is why the gate that protects the committed trees is the test floor below, not this target.

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

`tests/unit/test_generated_clients.py` runs everywhere — no pipelex CLI, no API key, no network — so `tests-check.yml` runs all of it. It is where the committed trees are actually gated:

- **The drift gate.** It runs `pipelex_sdk.codegen_check.run_codegen_check` over each `piper/generated/<method>/` tree, which is the same pure hashing `make codegen-check` performs, reached through the dependency this starter already has. Every artifact's whole body is compared against the SHA-256 its `codegen.lock` records, so a tree regenerated and only half committed, a file hand-edited below its stamp, a locked artifact deleted or a stale one left behind all fail here — and they fail in CI, which a target needing a `pipelex` install cannot do. What it does not prove is that the tree still matches what the *method* resolves to today: that needs the engine, and the guard for it stays `make codegen` itself (write-if-changed, then a clean `git diff`).
- **The inputs contract.** Each bundle must declare exactly the inputs its mode CLIs send, read from the `main.mthds` with `tomllib`, so an input renamed in a bundle that the CLIs do not follow fails the moment the bundle is edited, with no regeneration in between.
- **The models themselves.** They must import, carry their stamp, be tracked by their lock, and round-trip their own serialization.

The methods covered are discovered from `piper/methods/`, the same way `scripts/codegen.py` discovers them, so a method added there is gated by the next test run. The one thing written by hand is the set of input names each mode CLI passes — that is the CLI's half of the contract, and deriving it from the bundle would leave the bundle compared with itself — and a test holds that map against the methods actually on disk, so it cannot quietly omit one.
