# TODOS — "piper" rename + README DevX + Mermaid illustrations

Implementation plan spanning five phases. Written 2026-07-07 after a taste discussion about the starter's example command lines. Everything below is decided unless listed under **Open questions**.

> ## ▶ START HERE (cold start) — updated 2026-07-07
>
> **Phases 1–4 are DONE and COMMITTED.** Resume at **Phase 5 (verify → changelog → PR)** — the only remaining phase.
>
> - Branch `feature/Parity-to-JS`, **tree clean**, **6 commits ahead of `main`** (after this doc commit): `1a08426` (pre-existing examples) · `97a28b2` (the `git mv` renames) · `6d5adbf` (content edits + bootstrap rework) · `dddc223` (docs(todos): Checkpoint-1 record) · `defe0ec` (**Phase 3–4: README DevX + Mermaid diagrams**) · this `docs(todos)` Checkpoint-2 commit. **No PR opened yet.**
> - Read the **CHECKPOINT 2 — STATUS** block (just below Phase 4) first — it carries what the diagrams show, the final command list, and the exact code state. Then **CHECKPOINT 1 — STATUS** for the rename/bootstrap decisions. The template placeholder is the single token `piper`/`Piper`; the CLI answers to `uv run piper …`.
> - **Still open for Phase 5:** Q4 (changelog history) — see **Open questions**. Q1 (Mermaid ✓), Q2 (branch ✓), Q3 (API key ✓ — real outputs captured) are resolved.
> - **Phase 5's job (all that's left):** write the `CHANGELOG.md` entry (resolve Q4), run `make v` + `make tb` (not yet run this session — `make agent-check`/`make agent-test` already green at `defe0ec`), optionally one real `uv run piper extract-entities …` end-to-end (a working `PIPELEX_API_KEY` is in `.env`), then commit the changelog and open the PR to `main`. The plan's commit split "(2) README DevX + diagrams" is **already done** (`defe0ec`); only the changelog commit remains.
> - **Two carried-over notes:** (a) sibling `pipelex-starter-js` could get the same two diagrams for parity — record as a future task in that repo. (b) the `../docs/workspace-overview.md` fix is committed *nowhere yet* — it sits **uncommitted in the workspace-parent repo** (`/Users/lchoquel/repos/Pipelex`). Commit it there separately or drop it.
>
> Everything from here down is the original plan. The "Context"/"Decisions" sections are the rationale (past tense now); the per-phase checklists show what's ticked.

## Context for a cold start

This repo is a GitHub **template** (`pipelex-starter-python`): a Python CLI starter that calls the hosted Pipelex API via `pipelex-sdk`. It ships three demo commands (`extract-entities`, `summarize-pdf`, `generate-image`) exposed by a Typer CLI, plus a `/bootstrap` skill (`.claude/skills/bootstrap/`) that renames the template's placeholders into the user's real project name. See `CLAUDE.md` for architecture.

### Decisions already taken (with rationale)

- **Rename the placeholder project from `my-project`/`my_project` to `piper`.** Reasons: `my-project` is bland and appears in every runnable command, so it dominates the README's look; `piper` is a Silicon Valley (Pied Piper) wink — the canonical fake startup, which keeps the "placeholder, rename me" signal; it resonates with pipes / Pipelex / pip for exactly our audience; and it reads well everywhere (`uv run piper extract-entities --file notes.txt`, `uv run piper runs wait <run-id>`). Rejected alternatives: `scribe`, `quill`, `intern`, `globex`, `otto`, `acme` (ruled out — the README sample text already uses "Acme" as the extracted org), `pipette` (runner-up). Known collision, considered and dismissed: the `piper` TTS engine ships a `piper` CLI, but this starter is never published and its console script only exists inside the project venv.
- **The repo name does NOT change.** Only the placeholder project/package/CLI name inside the template becomes `piper`. And the name must not read as official Pipelex tooling — the real CLIs are `pipelex`, `plxt`, `mthds`; `piper` is wordplay-adjacent, not brand-bearing, which is intentional.
- **Single word, no hyphen/underscore split.** With `piper`, distribution name, package dir, and CLI command are all the same token, and the title is just `Piper`. This kills the `my-project` vs `my_project` duality in docs. The cost: the bootstrap script's token-replacement scheme relied on that duality to know which occurrences become the user's dash-form vs underscore-form name — see Phase 2 for the chosen fix.
- **Keep `uv run` in the examples; fix the framing, not the command.** `uv run` is Python's `npx`/`npm run` — stateless, shell-agnostic, copy-paste reliable. The activate-the-venv alternative looks cleaner but fails confusingly in every new terminal. The fix: a one-line explainer **before** the first command ("`uv run` runs a command inside this project's environment — think `npx` for Python"). Today that explanation sits in a parenthetical *after* the first command (README "Quick start" section).
- **"Illustrations using Mermaid charts."** The user's request said "remade charts", interpreted as **Mermaid** charts (GitHub renders Mermaid natively in READMEs). Confirm this reading at session start — it's in Open questions.

### Discovered drift (pre-existing) — ✅ RESOLVED in Phase 1/2

- The bootstrap script used to handle a `TestMyProject` class (`TEMPLATE_CAMEL`) and rename `tests/e2e/test_my_project.py`, but no such class existed anymore. **Fixed:** the file is now `tests/e2e/test_extract_entities.py` (matching its siblings `test_summarize_pdf.py` / `test_generate_image.py`), and the camel/test-class machinery is deleted from bootstrap. Bootstrap now has three name forms: dist (dashes), package (underscores), title.

### Current git state — updated 2026-07-07 (Checkpoint 2)

- Branch `feature/Parity-to-JS`, **tree clean**, **6 commits ahead of `main`** (see the START HERE block for the full list). The rename/bootstrap work is `97a28b2` + `6d5adbf`; Phase 3–4 (README DevX + Mermaid diagrams) is `defe0ec`; the two `docs(todos)` commits (`dddc223`, and this Checkpoint-2 one) record the plan progress. `1a08426` is the pre-existing "Complete the set pf examples" (note the typo, it's in history). Branch strategy resolved (stacked; see CHECKPOINT 1 — STATUS). **No PR opened yet.**

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
- **Q2 Branch strategy → stacked on `feature/Parity-to-JS`** (did not merge to main first). Rationale: already on it, and this work builds directly on its "Complete the set of examples" commit. Phases 1–2 are now committed there (see "Current state of the code" below); 3 commits ahead of `main`.
- Q1 (Mermaid), Q3 (API key), Q4 (changelog history) are Phase 3–5 concerns — not needed for this checkpoint, left for the next session to resolve.

**Key deviation (important for the record):** the plan's Phase 2 rule ".py files: every `piper` → package form; no dist-form occurrences exist in code" was **incorrect**. The user-facing CLI hint strings in `piper/cli.py`, `piper/errors.py`, `piper/runner.py` reference the console-script (dist) name. The fix was a **single context-aware char-after rule** used uniformly for `.py` and `.md` (piper before `.`/`_`/`/` → package; else → dist; `Piper` → title), with `pyproject.toml` on targeted per-key edits. Net result is cleaner than the planned per-filetype split.

**Current state of the code:**
- Branch `feature/Parity-to-JS`, **tree clean, Phases 1–2 committed** in two commits: `97a28b2` (the `git mv` renames) then `6d5adbf` (content edits across `pyproject.toml`, `README.md`, `CLAUDE.md`, `piper/**`, `tests/**`, `uv.lock`, plus the `bootstrap` skill + SKILL.md rework). Now 3 ahead of `main`. No PR yet. **Note the two commits do not match the plan's Phase 5 "suggested split"** — they're both Phase 1+2 work (renames, then content+bootstrap); the Phase 3–4 "README DevX + diagrams" commit does not exist yet.
- Package is `piper/`; CLI answers to `uv run piper …`; `uv.lock` pins `piper v0.12.0`.
- At commit time `make agent-check` + `make agent-test` were green on the main repo; standalone `pyright` on `bootstrap.py` clean. (Re-run at the start of Phase 3 to reconfirm — cheap.)
- **Cross-repo loose end (still open):** `../docs/workspace-overview.md` has one **uncommitted** edit in the *workspace-parent* git repo (`/Users/lchoquel/repos/Pipelex`) — `my_project/`→`piper/` plus a stale-dependency-claim fix. It was NOT swept up by the starter-repo commits. Commit it there separately (or drop it). Phase 5's changelog need not mention it.
- The Phase-2 verification scratch clone lived under the *previous* session's scratchpad — it is gone in a fresh session. To re-verify bootstrap, make a new scratch clone (copy the repo, `git init`, run `bootstrap.py` with a two-word `--package`).

**For Phase 3 (next):** the README still has the Phase-1 token-swapped text (H1 `# Piper ⚡️`, the italic *Replace "Piper"…* line, `uv run piper …` commands). When rewording the "Use this template"/"Next steps"/italic blocks, keep `strip_template_block()`/`transform_readme()` anchors in `bootstrap.py` in sync (Phase 2 coupling).

---

## Phase 3 — README DevX pass ("examples must look nice and solid")

Goal: a newcomer skims the README and immediately sees commands that look like a real product and knows what success looks like. Structure and coupling notes:

- [x] Move the `uv run` explainer **before** the first command, reworded around the npx analogy: "`uv run` executes a command inside this project's environment — think `npx` for Python, so there's no virtualenv to activate first." The activate-the-venv alternative is the secondary note after the output block.
- [x] Quick start: after the first command, show **expected output** — real trimmed JSON of the extracted entities. **Captured from an actual run** (Q3 resolved: a working `PIPELEX_API_KEY` is in `.env`). Also added a one-liner explaining the `Run started: run_…` stderr line (durable prints the id first).
- [x] Restructured "Useful commands" into a **"Try the demos"** section: one mini-block per demo — command, trimmed real output, one-line teaching point. `generate-image` block motivates durable mode and the `--mode blocking` ~30s cap. Kept a compact `make`-targets + `--detach`/`runs wait` block at the end under "Useful commands". **Note:** titled "Try the demos" (not "…three demos") and intro says "a handful of demo methods" — dropped the numeral to honor the no-hardcoded-counts rule; the bullet list shows the count.
- [x] "Use this template" now leads with the `/bootstrap` skill as the primary path ("open your new repo in Claude Code and run `/bootstrap`") with the manual steps as fallback. The manual steps were also corrected to name `[project.scripts]` + `[tool.setuptools] packages` (the old list missed them). Kept the `### Use this template` heading + `*Replace "…` line exactly (Phase 2 anchors) — verified the block still strips cleanly (see CHECKPOINT 2 status).
- [x] Reread top-to-bottom; reflowed section order to Quick start → Try the demos → How it works → Execution modes → Project structure → Useful commands. Split the old "How it works" into two H2s so each diagram has a home.
- [x] Style: one-paragraph-per-line (no hard wraps), no hardcoded counts.

## Phase 4 — Mermaid illustrations

Goal: two compact diagrams that carry the starter's two big ideas. GitHub renders Mermaid in fenced ```mermaid blocks natively (both themes). Keep them small — no sprawling boxes.

- [x] **Diagram 1 — how a run works** (flowchart TD, in "How it works"): `piper extract-entities '…'` → read the `.mthds` bundle from disk → `PipelexAPIClient` (env creds) → **edge label "bundle sent as content (mthds_contents)"** → hosted Pipelex API runs the method → `results.main_stuff` → example `parse()` → typed model → JSON on stdout. The content-not-code point rides on the API edge.
- [x] **Diagram 2 — execution modes** (sequence diagram, in a new "Execution modes: durable vs blocking" H2): two lifelines (You / Hosted API) with three `Note over`-labeled regions — **blocking** (`execute`, then a `--x` lost-message "past ~30s → timeout, switch to durable" that makes the cap visually obvious), **durable attended** (`start` → run id printed first → `loop` poll `wait_for_result` → result), **durable detached** (`start` → run id + exit → later `piper runs wait <id>` → result).
- [x] Rendering sanity-check: **validated locally with `mmdc`** (mermaid-cli — same mermaid.js engine GitHub uses); both diagrams render to SVG/PNG cleanly and were visually eyeballed (layout + renamed-command correct). The literal GitHub push-view is deferred to the Phase 5 commit/push (nothing to fix — this is belt-and-suspenders).
- [ ] Follow-up (do NOT do here): `pipelex-starter-js` (sibling repo) could get the same two diagrams for parity — record as a future task in that repo. *(Still to record; carry into Phase 5 wrap-up or a separate note.)*

---

**CHECKPOINT 2** — README reads well end-to-end with diagrams. Update this file: tick boxes, note what the diagrams ended up showing, paste the final example-command list into the notes below for the record.

### CHECKPOINT 2 — STATUS (reached 2026-07-07)

**Done:** Phases 3 and 4 complete and verified. Ready for Phase 5.

**Open-question resolutions taken this session:**
- **Q1 (Mermaid) → confirmed.** Two fenced ` ```mermaid ` blocks, validated locally with `mmdc`.
- **Q3 (API key) → resolved: real outputs captured.** A working `PIPELEX_API_KEY` is present in `.env`. Ran `extract-entities` and `summarize-pdf` against the hosted API for the README's expected-output JSON. Did **not** run `generate-image` (slow/costly) — its block shows the `Image` content shape (`url` / `public_url` / `mime_type` / `caption`) with `…` placeholders, verified against `piper/examples/generate_image.py`'s `GeneratedImage` model.
- **Q4 (changelog history)** stays open for Phase 5.

**What the two diagrams show (for the record):**
- **Diagram 1 (flowchart TD, "How it works"):** `piper extract-entities '…'` → read `.mthds` bundle from disk → `PipelexAPIClient (env creds)` → *[edge: bundle sent as content (mthds_contents)]* → hosted Pipelex API runs the method → `results.main_stuff` → example `parse()` → typed model → JSON on stdout. The "content, not code, lives server-side" point rides the API edge label.
- **Diagram 2 (sequenceDiagram, "Execution modes: durable vs blocking"):** lifelines `You (piper CLI)` / `Hosted Pipelex API`, three `Note over`-labeled regions — **blocking** (`execute` → result-if-under-~30s, then a `--x` lost-message "past ~30s → timeout, switch to durable"), **durable attended** (`start` → run id printed first, `loop` poll `wait_for_result` → result), **durable detached** (`start` → run id + exit → later `piper runs wait <id>` → result). The `--x` cross in the blocking region makes the ~30s cap visually obvious.

**Final example-command list in the README (post-Phase-3/4):**
```
uv run piper extract-entities "Alice from Acme met Bob on May 3rd, 2026."
uv run piper extract-entities --file notes.txt
uv run piper summarize-pdf samples/sample-invoice.pdf
uv run piper generate-image "a fox reading under a tree"                    # durable (default)
uv run piper generate-image "a fox reading under a tree" --mode blocking    # hits the ~30s cap
uv run piper extract-entities "…" --detach
uv run piper runs wait <run-id>                                             # also: runs status | runs result
```

**Current state of the code:**
- Branch `feature/Parity-to-JS`, **6 commits ahead of `main`, tree clean.** Phase 3–4 (README DevX + Mermaid diagrams) was committed this session as **`defe0ec`** — the plan's suggested commit split "(2)". This `TODOS.md` update is the accompanying `docs(todos)` Checkpoint-2 commit (mirrors `dddc223` for Checkpoint 1).
- `make agent-check` + `make agent-test` were green at `defe0ec` (README-only diff). `make v` (offline bundle validate) and `make tb` (boot test) were **not** run this session — they're the first Phase 5 items.
- **Phase 2 coupling re-verified against the reworded README:** ran the bootstrap transform in-process with a two-word name (`invoice_extractor` / `invoice-extractor`) — `strip_template_block()` cleanly removes the `*Replace "…` line and the whole `### Use this template` block (intro flows straight into `## Prerequisites`, no dangling blanks), both diagrams' `piper` tokens rename to the dist form, and the post-run survivor assertion passes with **zero** leftover `[Pp]iper` tokens. A `--clean --dry-run` of the real `bootstrap.py` also exits 0.
- Scratch render artifacts (`d1.png` / `d2.png` / SVGs) lived in the previous session's scratchpad — gone in a fresh session; regenerate with `mmdc -i <file>.mmd -o out.png` from the two fenced ` ```mermaid ` blocks in `README.md` if you want to re-eyeball.

**For Phase 5 (next):** the README DevX + diagrams are **already committed** (`defe0ec`); Phase 5 is now just verify → changelog → PR. Write the `CHANGELOG.md` entry (resolve Q4), run `make v` + `make tb`, optionally one real `uv run piper extract-entities …` end-to-end (key is in `.env`), commit the changelog, then PR to `main`. Two carried-over notes: the sibling `pipelex-starter-js` diagram-parity follow-up, and the uncommitted `../docs/workspace-overview.md` fix in the workspace-parent repo.

---

## Phase 5 — Verification, changelog, wrap-up

- [ ] `make agent-check` (format, lint, plxt, pyright, mypy) and `make agent-test` — both green.
- [ ] `make v` (offline bundle validation) and `make tb` (boot test) — green.
- [ ] If an API key is available: `make test-inference` or at least one real `uv run piper extract-entities "…"` to confirm the renamed CLI end-to-end.
- [ ] `CHANGELOG.md` entry: breaking — the placeholder project/CLI is now `piper` (was `my-project`); README overhauled (npx-framed quick start, expected outputs, Mermaid diagrams); bootstrap skill reworked for the single-token placeholder; e2e test file renamed. Style: write "breaking" (not "pre-1.0 breaking"), no hardcoded counts.
- [ ] Decide with the user: cut a release now via the `/release` skill, or leave for a later batch.
- [ ] Commit(s) on the working branch, PR to `main`. Suggested split: (1) rename sweep + bootstrap rework ✅ (`97a28b2`+`6d5adbf`), (2) README DevX + diagrams ✅ (`defe0ec`). **Remaining: the CHANGELOG commit**, then open the PR. Leave nothing staged-but-uncommitted at handoff.

## Open questions

Still open (resolve at the start of the next session):

4. **CHANGELOG history:** plan says leave old entries' `my_project` references as historical record. Veto if you'd rather rewrite them. *(Still open — Phase 5.)*

Resolved:

1. ~~**"remade charts" = Mermaid charts?**~~ → **RESOLVED: yes, Mermaid** (user confirmed this session). Two fenced ` ```mermaid ` blocks, validated locally with `mmdc`.
2. ~~**Branch strategy**~~ → **RESOLVED: stacked on `feature/Parity-to-JS`** (did not merge to `main` first; no fresh branch cut). Phases 1–2 are committed there.
3. ~~**API key availability**~~ → **RESOLVED: a working `PIPELEX_API_KEY` is in `.env`** (user confirmed "run the API"). Real `extract-entities` + `summarize-pdf` outputs captured for the README; `generate-image` left un-run (shape shown from the model). The key is still available for Phase 5's end-to-end check.

## Key files map (post-Phase-1/2; for orientation, verify with grep — don't trust line numbers)

The placeholder token everywhere below is now `piper` / `Piper` (not `my_project`). Build backend is `[tool.setuptools]`.

- `README.md` — **Phases 3–4 landed here (uncommitted).** H1 `# Piper ⚡️`, `*Replace "Piper"…` line (kept for the anchor), `### Use this template` (bootstrap-first, kept for the anchor), Quick start (npx-framed + real output), "Try the demos", "How it works" (Mermaid flowchart), "Execution modes: durable vs blocking" (Mermaid sequence), Project structure, Useful commands. The two anchors and `[MIT license](LICENSE)` are intact — if Phase 5 rewords the template block, keep them in sync with `bootstrap.py`.
- `.claude/skills/bootstrap/scripts/bootstrap.py` — **Phase 2 rework landed here.** `TEMPLATE_NAME`/`TEMPLATE_TITLE` constants + the `PIPER_*`/`SURVIVING_NAME_RE` regexes near the top; `apply_name_tokens()` (context-aware char-after rule), `transform_pyproject()` (the `key_edits` dict), `strip_template_block()` / `transform_readme()` (README anchors — **keep in sync if Phase 3 rewords the "Use this template"/italic blocks**), `run()` (transform→assert→write).
- `.claude/skills/bootstrap/SKILL.md` — operator instructions; now describes the three name forms (dist/package/title).
- `CLAUDE.md` (repo) — Architecture section names the CLI (`piper`) and package (`piper/`).
- `piper/` — `cli.py`, `runner.py`, `errors.py`, `file_input.py`, `examples/` (per-demo `parse()` + output models — `extract_entities.py` is the shape to match for Phase 3's expected-output JSON), `methods/`.
- `tests/e2e/test_extract_entities.py` — the renamed e2e file; class is `TestExtractEntities`. Siblings `test_summarize_pdf.py`, `test_generate_image.py`.
