---
status: active
item: L-260906-aa5083
---

# `make add-method` — what the review rounds deferred

Findings from the review rounds on `feature/Agent-surface-parity` that were deliberately not fixed on the branch. Each entry says which round deferred it, whether a verifier confirmed it, why it waited and what a fix would look like. The first two come from round 1 (profile 4, bar `open`); the next three from round 2 (profile 4, bar `defects`), which reviewed `97ceac6`; the last two from round 3.

## `make codegen-check` skips a generated tree whose lock was deleted

- **Reporter:** code-review (`Makefile`, the `codegen-check` target).
- **Finding (verified):** the target loops over `piper/generated/*/codegen.lock`, so a tree whose `codegen.lock` was removed is not visited and the target exits 0. Before the branch it named each tree explicitly and a missing lock failed with exit 2. With no lock at all, the shell passes the literal glob through and the check fails closed with the confusing "No codegen.lock found in '…/piper/generated/*'".
- **Why deferred:** CI never runs this target. The gate CI does run, `test_generated_tree_matches_its_lock` in `tests/unit/test_generated_clients.py`, fails on exactly that state, so the drift is caught before a merge; only the local convenience target is lenient.
- **What a fix looks like:** loop over the generated package directories instead of their locks (skipping `__pycache__`) and let `codegen check` report the missing lock with its own exit 2 — or move the target onto `pipelex_sdk.codegen_check.run_codegen_check`, which the Makefile comment already names as the remaining step.

## A concept whose code two domains share is refused as having no output model

- **Found by:** the verifier of round 1, while refuting the claim that codegen emits no class for a native output.
- **Finding (verified by reading the emitter):** when two domains of one method declare a concept with the same code, codegen disambiguates the classes as `alpha__Result` and `beta__Result`. `output_model_name` in `scripts/add_method.py` derives the class name from the concept ref's last segment, `Result`, so the pre-write check ("the generated models declare no `Result`") refuses the scaffold in every mode, `detached` included, where the command imports no model at all.
- **Why deferred:** it fails loudly and writes nothing, so it costs a person a scaffold they have to write by hand rather than a broken file; it is a limitation of the name derivation, not a defect that corrupts anything.
- **What a fix looks like:** derive the class name from the generated artifacts (or from the codegen lock's concept-to-class mapping, if it carries one) instead of from the concept ref, and skip the model check in `detached`, which never imports the model.

## A broken or missing `method.json` ends a scaffolded command in a traceback

- **Round:** 2. **Reporter:** code-review. **Verified.**
- **Finding:** the emitted command calls `read_manifest(...)` as the first line of its body, outside `_run`, which catches only the SDK's request errors. A `method.json` left invalid by a hand edit exits 1 with a long Rich traceback ending in `ManifestError: …/method.json: not valid JSON — …`, and a deleted one ends in `FileNotFoundError`.
- **Why deferred:** the defect does not matter at this bar. The last line of the traceback names the file and the problem, the exit code is the same 1 a clean message would give, and nothing is uploaded or run before the manifest is read. What it costs is a noisier message.
- **What a fix looks like:** have the emitted command catch `ManifestError` and `FileNotFoundError` around the read and print one line naming the file before exiting 1, the way `_run` reports a failed request. Update the AST honesty test's reserved names for whatever the new lines read.

## `DRY_RUN=0` still means a dry run

- **Round:** 2. **Reporter:** code-review. **Unverified.**
- **Finding (as reported):** the Makefile passes `--dry-run` whenever `DRY_RUN` is non-empty on the command line, so `DRY_RUN=0` or `DRY_RUN=false` still stops before the write.
- **Why deferred:** it fails safe. The run prints the plan, says it is a dry run and writes nothing, so a user who meant "no" reruns without the variable.
- **What a fix looks like:** pass `--dry-run` only for an agreed truthy spelling (`1`, `true`, `yes`), or refuse any other value naming the accepted ones.

## Two scaffolds into the same mode at once can lose one command

- **Round:** 2. **Reporter:** codex:adversarial. **Unverified.**
- **Finding (as reported):** two runs targeting the same mode can both read the original mode file before either writes, and the second write then replaces the whole file with its own snapshot, so the first command and its import disappear while both runs report success. A retry of the lost scaffold is refused because its method directory already exists.
- **Why deferred:** it needs two scaffolds of the same mode running concurrently in one checkout, which is not how the gesture is used or documented. The recommended fix, a per-mode interprocess lock held across the read, the checks, the merge and the rollback, is more machinery than a starter template should carry for that case.
- **What a fix looks like:** a cheaper guard first: re-read the mode file just before writing it and refuse, rolling back, when it no longer matches the text the plan was merged into. A lock only if that proves insufficient.

## Two inputs can derive the same command-line flag

- **Round:** 3 (profile 4, bar `necessity`, reviewing `669e364`). **Reporter:** cubic. **Unverified.**
- **Finding (as reported):** the scaffolder checks that each input name is a usable Python identifier but never checks the flags derived from them. A boolean input `strict` emits `--strict/--no-strict`, so a second input named `no_strict` also emits `--no-strict`, and one of the two becomes unreachable. The report's other example, an optional input named `help` colliding with Typer's `--help`, is already refused by round 2's builtin check, since `help` is a builtin.
- **Why deferred:** it needs two inputs whose names collide once a boolean's negative flag is derived, which is contrived for a method's inputs, and it is not a defect round 2's changes introduced.
- **What a fix looks like:** collect every flag a plan derives, including each boolean's `--no-` form, and refuse a plan in which two parameters share one, naming both inputs.

## A generated model that includes native `Date` cannot be imported, and a scaffolded import of it takes the whole CLI down

- **Round:** 3. **Found by:** the verifier, while settling a finding about date outputs. **Verified** on pipelex 0.57.0.
- **Finding:** when a method's concept closure contains native `Date`, the `python-pydantic` emitter writes `class Date(BaseModel)` with fields named `date` and `time`, which shadow the `datetime` types imported at the top of `models.py`. Importing the module fails with `TypeError: unsupported operand type(s) for |: 'FieldInfo' and 'NoneType'`. The scaffolder's pre-write check only looks for the class name, so it passes, and the import it inserts into `piper/<mode>/cli.py` then breaks that mode file. `piper/cli.py` imports all three modes eagerly, so every `piper` command, the demos included, stops working.
- **Why deferred:** the defect is in the codegen emitter, which `pipelex` owns, and it predates this branch. It is filed on the workspace ledger against `pipelex` as `L-260913-8f1f22`. The scaffolder-side guard is an improvement, not a fix this bar admits.
- **What a fix looks like here:** after writing the generated tree and before inserting the import, import the generated `models` module, and roll the whole slice back when it does not import, naming the error.
