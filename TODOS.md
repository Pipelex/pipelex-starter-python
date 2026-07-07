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

- [ ] `git mv my_project piper` (package dir; history follows).
- [ ] `git mv tests/e2e/test_my_project.py tests/e2e/test_extract_entities.py` (drift fix — decouples the test file from the project name).
- [ ] `pyproject.toml`: `[project] name`, `[project.scripts]` entry (`piper = "piper.cli:app"`), hatch `packages`, `[tool.hatch.build] package data` key, `[tool.mypy] packages`, `[tool.pyright] include`, and the placeholder `Repository` URL (`yourusername/my-project` → `yourusername/piper`). Grep the file rather than trusting this list.
- [ ] All imports/references in `piper/*.py`, `piper/examples/*.py`, and `tests/**` (unit, integration, e2e).
- [ ] `README.md`: token swap only in this phase (H1 → `# Piper ⚡️`, adjust the *"Replace …"* italic line, `my-project` → `piper` everywhere). The real prose rewrite is Phase 3.
- [ ] `CLAUDE.md` (repo): update the Architecture section's `my-project` CLI / `my_project/` references.
- [ ] Delete the untracked derived `my_project.egg-info/` directory (it regenerates under the new name).
- [ ] `CHANGELOG.md`: leave historical entries' `my_project` references untouched (they describe past versions); the new entry comes in Phase 5.
- [ ] Grep the workspace root (`../CLAUDE.md`, `../docs/workspace-overview.md`) for stale `my-project` references to this repo; fix if any (separate repo — separate commit there if needed).
- [ ] `make li` — regenerate `uv.lock` for the new distribution name (CI's `package-check.yml` runs `uv lock --locked`).
- [ ] Final sweep: `grep -rn "my-project\|my_project\|My Project\|MyProject" --exclude-dir=.venv --exclude-dir=.git --exclude=uv.lock --exclude=CHANGELOG.md .` must return only the bootstrap skill files (rewritten in Phase 2) until Phase 2 lands, then nothing.

## Phase 2 — Rework the `/bootstrap` skill for the single-token placeholder

Goal: bootstrap still turns the template into a user's project in one deterministic pass, now from `piper`. This is the subtle part of the whole change — read `.claude/skills/bootstrap/scripts/bootstrap.py` fully before touching it.

**The problem:** `apply_name_tokens()` does ordered global string replacement using four distinct source tokens (`TestMyProject`, `My Project`, `my_project`, `my-project`). With a single-word placeholder there is **one** source token (`piper`) that must map to **two** different targets depending on context — the user's dash-form (`invoice-extractor`) in CLI-command and dist positions, the underscore-form (`invoice_extractor`) in imports, paths, and config arrays. Likewise `Piper` (title) is just the capitalized package token.

**Chosen approach — context-aware rules instead of global tokens:**

- [ ] Update the constants: `TEMPLATE_DIST = TEMPLATE_PACKAGE = "piper"` collapses to a single `TEMPLATE_NAME = "piper"`, `TEMPLATE_TITLE = "Piper"`; delete `TEMPLATE_CAMEL` and all `Test{camel}` logic and the test-file rename logic (gone since Phase 1).
- [ ] Replacement rules by file type:
  - `.py` files: every `piper` → package form (imports, module paths, path strings). No dist-form occurrences exist in code.
  - `pyproject.toml`: targeted per-key edits (extend the existing `transform_pyproject()`): `name =` → dist; `[project.scripts]` left-hand side → dist, right-hand side → package; hatch/mypy/pyright arrays → package; Repository URL already handled by `--repo-url`.
  - `.md` files (README, CLAUDE): `piper` followed by `/` or `.` → package (project-structure block, module paths); bare `piper` (command position, prose) → dist; `Piper` → title.
- [ ] Add a post-run hard assertion inside the script: after replacement, no `\bpiper\b` / `\bPiper\b` token may survive in any transformed file — fail loudly with the offending locations. This is the safety net that replaces the old "four distinct tokens can't collide" property.
- [ ] Update `SKILL.md`: the placeholder-forms prose (three forms now: dist, package, title — no test class), Step 1 preflight (`name = "piper"`), Step 2 derived-forms display, Step 4 description of what the script does, and the frontmatter `description`.
- [ ] Keep the `strip_template_block()` / `transform_readme()` hardcoded strings in sync with the Phase 3 README rewrite (they pattern-match README text like the *"Replace …"* line — if Phase 3 rewords those blocks, update the regexes in the same change; do Phases 2 and 3 with this coupling in mind).
- [ ] **Verification (the real proof):** in a scratch clone (copy the repo to the scratchpad dir), run the updated bootstrap end-to-end with a **two-word** name (`--package invoice_extractor …`) — that exercises the dist≠package split, which is the risky path — then run `make li && make agent-check && make agent-test` inside the scratch clone. Also run a `--dry-run` with a one-word name (`acme`) and eyeball the plan.

---

**CHECKPOINT 1** — rename landed and bootstrap proven. Update this file: tick the boxes, record decisions taken and any deviations, note current state (branch, commits, scratch-test result). Good handoff point for a fresh session; Phases 3–4 are independent of the mechanics above.

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
