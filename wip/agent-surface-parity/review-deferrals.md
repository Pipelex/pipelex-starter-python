---
status: active
item: L-260906-aa5083
---

# `make add-method` — what the first review round deferred

Findings from review round 1 on `feature/Agent-surface-parity` (profile 4, bar `open`) that were verified as real but deliberately not fixed on the branch. Each entry says why it waited and what a fix would look like.

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
