# TODOS — "piper" rename + README DevX + Mermaid illustrations

Implementation plan for the next session. Written 2026-07-07 after a taste discussion about the starter's example command lines. Everything below is decided unless listed under **Open questions**. No code has been written yet.

## Context for a cold start

This repo is a GitHub **template** (`pipelex-starter-python`): a Python CLI starter that calls the hosted Pipelex API via `pipelex-sdk`. It ships three demo commands (`extract-entities`, `summarize-pdf`, `generate-image`) exposed by a Typer CLI, plus a `/bootstrap` skill (`.claude/skills/bootstrap/`) that renames the template's placeholders into the user's real project name. See `CLAUDE.md` for architecture.

### Decisions already taken (with rationale)

- **Rename the placeholder project from `my-project`/`my_project` to `piper`.** Reasons: `my-project` is bland and appears in every runnable command, so it dominates the README's look; `piper` is a Silicon Valley (Pied Piper) wink — the canonical fake startup, which keeps the "placeholder, rename me" signal; it resonates with pipes / Pipelex / pip for exactly our audience; and it reads well everywhere (`uv run piper extract-entities --file notes.txt`, `uv run piper runs wait <run-id>`). Rejected alternatives: `scribe`, `quill`, `intern`, `globex`, `otto`, `acme` (ruled out — the README sample text already uses "Acme" as the extracted org), `pipette` (runner-up). Known collision, considered and dismissed: the `piper` TTS engine ships a `piper` CLI, but this starter is never published and its console script only exists inside the project venv.
- **The repo name does NOT change.** Only the placeholder project/package/CLI name inside the template becomes `piper`. And the name must not read as official Pipelex tooling — the real CLIs are `pipelex`, `plxt`, `mthds`; `piper` is wordplay-adjacent, not brand-bearing, which is intentional.
- **Single word, no hyphen/underscore split.** With `piper`, distribution name, package dir, and CLI command are all the same token, and the title is just `Piper`. This kills the `my-project` vs `my_project` duality in docs. The cost: the bootstrap script's token-replacement scheme relied on that duality to know which occurrences become the user's dash-form vs underscore-form name — see Phase 2 for the chosen fix.
- **Keep `uv run` in the examples; fix the framing, not the command.** `uv run` is Python's `npx`/`npm run` — stateless, shell-agnostic, copy-paste reliable. The activate-the-venv alternative looks cleaner but fails confusingly in every new terminal. The fix: a one-line explainer **before** the first command ("`uv run` runs a command inside this project's environment — think `npx` for Python"). Today that explanation sits in a parenthetical *after* the first command (README "Quick start" section).
- **"Illustrations using Mermaid charts."** The user's request said "remade charts", interpreted as **Mermaid** charts (GitHub renders Mermaid natively in READMEs). Confirm this reading at session start — it's in Open questions.

### Discovered drift (pre-existing, fix as part of this work)

- The bootstrap script still handles a `TestMyProject` class (`TEMPLATE_CAMEL` in `scripts/bootstrap.py`) and renames `tests/e2e/test_my_project.py`, but **no `TestMyProject` class exists anymore** — the e2e classes were renamed when the demo set was completed (`TestExtractEntities`, `TestSummarizePdf`, `TestGenerateImage`). Only the *file name* `test_my_project.py` still carries the placeholder. Fix: rename that file to `tests/e2e/test_extract_entities.py` (matching its siblings) and delete the camel/test-class machinery from bootstrap entirely. After that, bootstrap has only three name forms: dist (dashes), package (underscores), title.

### Current git state

- Branch `feature/Parity-to-JS`, clean tree, one commit ahead of `main` ("Complete the set pf examples" — note the typo, it's in history). Decide branch strategy at session start (Open questions).

---

## Phase 1 — Rename sweep: `my-project` / `my_project` / `My Project` → `piper` / `Piper`

Goal: every placeholder occurrence in the template becomes `piper` (or `Piper` for the title), the tree passes all checks, and the CLI answers to `uv run piper …`.

- [x] `git mv my_project piper` (package dir; history follows).
- [x] `git mv tests/e2e/test_my_project.py tests/e2e/test_extract_entities.py` (drift fix — decouples the test file from the project name).
- [x] `pyproject.toml`: `[project] name`, `[project.scripts]` entry (`piper = "piper.cli:app"`), `packages`, package-data key, `[tool.mypy] packages`, `[tool.pyright] include`, and the placeholder `Repository` URL (`yourusername/my-project` → `yourusername/piper`). **Note:** the build backend is `[tool.setuptools]`, not hatch as the plan text guessed — the actual setuptools keys were updated.
- [x] All imports/references in `piper/*.py`, `piper/examples/*.py`, and `tests/**` (unit, integration, e2e).
- [x] `README.md`: token swap only in this phase (H1 → `# Piper ⚡️`, adjusted the *"Replace …"* italic line, `my-project` → `piper` everywhere). The real prose rewrite is Phase 3.
- [x] `CLAUDE.md` (repo): updated the Architecture section's `my-project` CLI / `my_project/` references.
- [x] Deleted the untracked derived `my_project.egg-info/` directory (it regenerates under the new name).
- [x] `CHANGELOG.md`: left historical entries' `my_project` references untouched (they describe past versions); the new entry comes in Phase 5.
- [x] Grepped the workspace root: only `../docs/workspace-overview.md:110` referenced this repo's `my_project/`. Fixed → `piper/`, and also corrected the same line's stale "Depends on `pipelex` (editable)" claim → "Calls the hosted Pipelex API via `pipelex-sdk`". **Left UNCOMMITTED in the separate workspace-parent repo** for separate review (`../CLAUDE.md` had no stale refs to this repo).
- [x] `make li` — regenerated `uv.lock` (`Removed my-project v0.12.0`, `Added piper v0.12.0`).
- [x] Final sweep: the old-token grep now returns only `TODOS.md` (this plan doc, which discusses the migration) — the bootstrap skill files were rewritten in Phase 2 and no longer carry the old tokens.

## Phase 2 — Rework the `/bootstrap` skill for the single-token placeholder

Goal: bootstrap still turns the template into a user's project in one deterministic pass, now from `piper`. This is the subtle part of the whole change — read `.claude/skills/bootstrap/scripts/bootstrap.py` fully before touching it.

**The problem:** `apply_name_tokens()` does ordered global string replacement using four distinct source tokens (`TestMyProject`, `My Project`, `my_project`, `my-project`). With a single-word placeholder there is **one** source token (`piper`) that must map to **two** different targets depending on context — the user's dash-form (`invoice-extractor`) in CLI-command and dist positions, the underscore-form (`invoice_extractor`) in imports, paths, and config arrays. Likewise `Piper` (title) is just the capitalized package token.

**Chosen approach — context-aware rules instead of global tokens:**

- [x] Updated the constants: collapsed to `TEMPLATE_NAME = "piper"`, `TEMPLATE_TITLE = "Piper"`; deleted `TEMPLATE_CAMEL`, `camel_from_package()`, the `Names.camel` field, all `Test{camel}` logic, and the test-file rename block in `run()` (gone since Phase 1).
- [x] Replacement rules — **deviated from the plan here (plan was wrong):** the plan said ".py files: every `piper` → package form. No dist-form occurrences exist in code." **That is false** — the CLI hint strings in `cli.py`/`errors.py`/`runner.py` (e.g. `` `piper runs wait <id>` ``) name the console-script, which is the **dist** name, so they must become dash-form. Resolution: a **single context-aware char-after rule** handles `.py` **and** `.md` uniformly (`piper` before `.`/`_`/`/` → package; any other boundary → dist; `Piper` → title). This is simpler than the plan's per-filetype split and provably correct.
  - `pyproject.toml`: targeted per-key edits in `transform_pyproject()` (a `key_edits` dict): `name =` → dist; `[project.scripts]` LHS → dist, RHS → package; setuptools `packages` + package-data key + mypy `packages` + pyright `include` → package; Repository slug → dist (or `--repo-url`). Kept off the generic char-after pass because bare `["piper"]` array strings read as command position.
- [x] Added the post-run hard assertion (`SURVIVING_NAME_RE = \b[Pp]iper\b`). Restructured the edit loop to **transform-all → assert → write** so a leftover token aborts *before* any file is written. `\b…\b` avoids false-positives on a user name embedding the token (verified against `sandpiper`).
- [x] Updated `SKILL.md`: frontmatter `description`, placeholder-forms prose (three forms, no test class), Step 1 preflight (`name = "piper"`), Step 2 derived-forms display, Step 4 script description, and the stale "renames"/"four forms" mentions (Steps 3/6).
- [x] `strip_template_block()` / `transform_readme()` anchors (`### Use this template`, `*Replace "…"`) still match the current README; updated their comments `My Project`→`Piper`. **Phase 3 coupling still live:** if Phase 3 rewords those README blocks, update these anchors in the same change.
- [x] **Verification (the real proof):** scratch clone at `scratchpad/scratch-clone` (git-init'd so the `git mv` path runs). Two-word real bootstrap (`--package invoice_extractor`, dist `invoice-extractor`) → `make li` + `make agent-check` (ruff/plxt/pyright 0 errors/mypy) + `make agent-test` **all green**; `invoice-extractor --help` works (console script is the dash form ✓). One-word (`acme`) dry-run eyeballed. Also an in-process logic check over representative `.py`/`.md`/pyproject strings — all pass.

---

**CHECKPOINT 1** — rename landed and bootstrap proven. Update this file: tick the boxes, record decisions taken and any deviations, note current state (branch, commits, scratch-test result). Good handoff point for a fresh session; Phases 3–4 are independent of the mechanics above.

### CHECKPOINT 1 — STATUS (reached 2026-07-07)

**Done:** Phases 1 and 2 complete and verified. Ready for Phase 3.

**Open-question resolutions taken this session:**
- **Q2 Branch strategy → stacked on `feature/Parity-to-JS`** (did not merge to main first). Rationale: already on it, tree was clean, and this work builds directly on its "Complete the set of examples" commit. Still one commit ahead of `main` + this uncommitted work.
- Q1 (Mermaid), Q3 (API key), Q4 (changelog history) are Phase 3–5 concerns — not needed for this checkpoint, left for the next session to resolve.

**Key deviation (important for the record):** the plan's Phase 2 rule ".py files: every `piper` → package form; no dist-form occurrences exist in code" was **incorrect**. The user-facing CLI hint strings in `piper/cli.py`, `piper/errors.py`, `piper/runner.py` reference the console-script (dist) name. The fix was a **single context-aware char-after rule** used uniformly for `.py` and `.md` (piper before `.`/`_`/`/` → package; else → dist; `Piper` → title), with `pyproject.toml` on targeted per-key edits. Net result is cleaner than the planned per-filetype split.

**Current state of the code:**
- Branch `feature/Parity-to-JS`. **Nothing committed** (per "commit only when asked"). Staging is mixed exactly as bootstrap itself produces: package-dir + test-file renames are **staged** (`R`/`RM`, from `git mv`); content edits are **unstaged** (`M`); `TODOS.md` is staged (`A`).
- Package is `piper/`; CLI answers to `uv run piper …`; `uv.lock` regenerated to `piper v0.12.0`.
- `make agent-check` + `make agent-test` green on the main repo; standalone `pyright` on `bootstrap.py` clean.
- **Cross-repo:** `../docs/workspace-overview.md` has one **uncommitted** edit in the *workspace-parent* git repo (`/Users/lchoquel/repos/Pipelex`). Commit it there separately (or drop it) — it is not part of this repo's change set. Phase 5's changelog need not mention it.
- Scratch clone (with its own `.venv`) lives at `scratchpad/scratch-clone` — ephemeral, safe to ignore/delete.

**For Phase 3 (next):** the README still has the Phase-1 token-swapped text (H1 `# Piper ⚡️`, the italic *Replace "Piper"…* line, `uv run piper …` commands). When rewording the "Use this template"/"Next steps"/italic blocks, keep `strip_template_block()`/`transform_readme()` anchors in `bootstrap.py` in sync (Phase 2 coupling).

---

## Phase 3 — README DevX pass ("examples must look nice and solid")

Goal: a newcomer skims the README and immediately sees commands that look like a real product and knows what success looks like. Structure and coupling notes:

- [ ] Move the `uv run` explainer **before** the first command, reworded around the npx analogy: "`uv run` runs a command inside this project's environment — think `npx` for Python." Keep the activate-the-venv alternative as the secondary note after it.
- [ ] Quick start: after the first command, show **expected output** — a short, real, trimmed JSON of the extracted entities so the user can recognize success. Capture from an actual run (needs `PIPELEX_API_KEY`; see Open questions). If no key is available in-session, use output copied from a previous real run and verify the shape against `piper/examples/extract_entities.py`'s model.
- [ ] Restructure "Useful commands" into a "Try the three demos" section: one mini-block per demo — the command, a trimmed expected output (or, for `generate-image`, what gets saved/printed), and a one-line teaching point (`generate-image` is the demo that motivates durable mode; `--mode blocking` shows the ~30s cap). Keep a compact `make` targets block at the end.
- [ ] "Next steps after creating from template" currently describes the manual rename only — make the `/bootstrap` skill the primary path ("open the repo in Claude Code and run `/bootstrap`") with the manual steps as fallback. Keep wording consistent with what `strip_template_block()` expects to find (Phase 2 coupling).
- [ ] Reread the whole README top to bottom for flow once the pieces are in; the tone bar: commands should read like a real product's docs, not a template's.
- [ ] Style rules that apply (workspace `CLAUDE.md`): no hard-wrapped lines (one paragraph = one line), no hardcoded counts.

## Phase 4 — Mermaid illustrations

Goal: two compact diagrams that carry the starter's two big ideas. GitHub renders Mermaid in fenced ```mermaid blocks natively (both themes). Keep them small — no sprawling boxes.

- [ ] **Diagram 1 — how a run works** (flowchart, in "How it works"): CLI command → reads `.mthds` bundle from disk → `PipelexAPIClient` → hosted Pipelex API runs the method → `results.main_stuff` → example's `parse()` → typed model → JSON to stdout. Emphasize that the bundle is sent as *content* (nothing method-specific lives server-side).
- [ ] **Diagram 2 — execution modes** (sequence diagram, next to the durable/blocking explanation): three lifelines-worth of comparison — **blocking** (`execute`, cut off past the hosted ~30s cap), **durable attended** (`start` → poll `wait_for_result`, survives the cap, run id printed first), **durable detached** (`start` → exit; later `piper runs status|result|wait <id>`). This is the starter's core teaching point; the diagram should make the ~30s cap visually obvious.
- [ ] Sanity-check rendering on GitHub (push the branch, view the README) — Mermaid syntax errors render as an error block, not silently.
- [ ] Follow-up to note, not to do here: `pipelex-starter-js` (sibling repo) could get the same two diagrams for parity — record as a future task in that repo.

---

**CHECKPOINT 2** — README reads well end-to-end with diagrams. Update this file: tick boxes, note what the diagrams ended up showing, paste the final example-command list into the notes below for the record.

---

## Phase 5 — Verification, changelog, wrap-up

- [ ] `make agent-check` (format, lint, plxt, pyright, mypy) and `make agent-test` — both green.
- [ ] `make v` (offline bundle validation) and `make tb` (boot test) — green.
- [ ] If an API key is available: `make test-inference` or at least one real `uv run piper extract-entities "…"` to confirm the renamed CLI end-to-end.
- [ ] `CHANGELOG.md` entry: breaking — the placeholder project/CLI is now `piper` (was `my-project`); README overhauled (npx-framed quick start, expected outputs, Mermaid diagrams); bootstrap skill reworked for the single-token placeholder; e2e test file renamed. Style: write "breaking" (not "pre-1.0 breaking"), no hardcoded counts.
- [ ] Decide with the user: cut a release now via the `/release` skill, or leave for a later batch.
- [ ] Commit(s) on the working branch, PR to `main`. Suggested split: (1) rename sweep + bootstrap rework, (2) README DevX + diagrams. Leave nothing staged-but-uncommitted at handoff.

## Open questions (resolve at session start)

1. **"remade charts" = Mermaid charts?** Assumed yes (speech-to-text reading). Confirm before Phase 4.
2. **Branch strategy:** `feature/Parity-to-JS` is one commit ahead of `main` and this work builds on its examples. Stack on it, or merge it to `main` first and start a fresh branch (suggested name: `feature/piper-rename-readme-devx`)?
3. **API key availability:** capturing real expected outputs for the README (Phase 3) and the end-to-end check (Phase 5) needs `PIPELEX_API_KEY` in `.env`. Is one available in the session?
4. **CHANGELOG history:** plan says leave old entries' `my_project` references as historical record. Veto if you'd rather rewrite them.

## Key files map (for orientation, verify with grep — don't trust line numbers)

- `pyproject.toml` — placeholder in: project name, `[project.scripts]`, hatch packages/package-data, mypy `packages`, pyright `include`, Repository URL.
- `.claude/skills/bootstrap/SKILL.md` — the skill's operator instructions; describes the (soon obsolete) four name forms.
- `.claude/skills/bootstrap/scripts/bootstrap.py` — `TEMPLATE_*` constants near the top; `apply_name_tokens()`, `transform_pyproject()`, `strip_template_block()`, `transform_readme()`, `transform_generic()`, `gather_target_files()` are the functions the Phase 2 rework touches.
- `README.md` — H1 + italic replace-me line, "Use this template" block, Quick start, Project structure, How it works, Useful commands.
- `CLAUDE.md` (repo) — Architecture section names the CLI and package.
- `piper/` (post-rename; today `my_project/`) — `cli.py`, `runner.py`, `errors.py`, `file_input.py`, `examples/`, `methods/`.
- `tests/e2e/test_my_project.py` — contains `TestExtractEntities` (not `TestMyProject`); renamed in Phase 1.
