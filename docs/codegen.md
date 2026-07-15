# Generated typed clients

The typed models this starter parses run results into are **generated from the `.mthds` bundles**, not hand-written. The method definition is the single source of truth: its output concepts are projected into Pydantic models, so editing a bundle and regenerating is all it takes to keep the Python side in sync.

## What is generated, and where

| Artifact | Path | Committed | Edited by hand |
| --- | --- | --- | --- |
| Typed models (one module per method) | `piper/generated/<method>/models.py` | Yes | **Never** — regenerate instead |
| Artifact-set lock | `piper/generated/<method>/codegen.lock` | Yes | Never |
| Runnable input template | `piper/methods/<method>/inputs.template.json` | Yes | Yes — it is a scaffold: copy it, fill in real values |

Each `models.py` starts with a `pipelex-codegen-stamp` header recording the source crate fingerprint, engine version, projection, and a content hash. The sibling `codegen.lock` records the generated artifact set. Together they make drift detectable offline.

The demo commands in each mode CLI (`piper/blocking/cli.py`, `piper/attended/cli.py`) import the generated models and only add the bundle path, the pipe code, and the narrowing line (`Model.model_validate(main_stuff)`) — nothing method-shaped is hand-written.

## Workflow

Edit a bundle (`piper/methods/<method>/main.mthds`), then:

```bash
make codegen        # regenerate models + input templates (writes only what changed)
make codegen-check  # offline drift check: exit 0 current · 1 drift · 2 no lock
```

`codegen-check` is pure hashing against each `codegen.lock` — no engine boot, no network, no API key. It reports drift by category: missing (a locked artifact was deleted), modified (an artifact no longer matches the locked hash), hand-edited (a generated file was touched below its stamp), and orphan (a stale stamped file the lock no longer lists).

One thing the offline check cannot see is a bundle edit that was never regenerated — detecting that requires resolving the bundle, which is the engine's job. The guard for it is `make codegen` itself: regeneration is write-if-changed, so running it and checking `git diff` is clean proves the committed clients match the bundles.

The generated files are excluded from ruff in `pyproject.toml`: reformatting them would change their content hash and trip the drift check. They still go through pyright and mypy like any other code.

## The `pipelex` CLI is not a dependency of this starter

This starter talks to the **hosted Pipelex API** through `pipelex-sdk`; the `pipelex` runtime that ships the `codegen` command is not installed here. Point the `PIPELEX` make variable at a pipelex install:

```bash
PIPELEX=/path/to/pipelex/.venv/bin/pipelex make codegen
PIPELEX=/path/to/pipelex/.venv/bin/pipelex make codegen-check
```

Once a released `pipelex` ships `codegen`, `codegen-check` is meant to run in CI so a bundle edit can never land without its regenerated client.

## Offline test floor

`tests/unit/test_generated_clients.py` runs everywhere (no pipelex CLI, no API key): it checks the generated modules import, carry the stamp + lock, round-trip their own serialization, and that each committed input template names exactly the inputs the CLI passes — so a regenerated template that no longer matches what `piper/<mode>/cli.py` sends fails in CI even before `codegen-check` is wired in.
