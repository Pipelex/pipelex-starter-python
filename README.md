# My Project ⚡️

*Replace "My Project" with your actual project name*

A minimal Python CLI starter that calls the [Pipelex](https://pipelex.com) API via the [`pipelex-sdk`](https://pypi.org/project/pipelex-sdk/) SDK to run AI methods (`.mthds` bundles) — no local Pipelex runtime required.

It ships three demo methods, each exposed as a `my-project` CLI command:

- **`extract-entities`** — given a piece of text, pull out the people, organizations, and dates it mentions.
- **`summarize-pdf`** — given a document (PDF), produce a title, document type, and key points. Shows how to feed a *file* to a pipe.
- **`generate-image`** — given a text prompt, generate an image. Being slow, it's the example that best shows the durable-vs-blocking split (image generation routinely outlives the hosted ~30s blocking cap).

Each prints its result as JSON.

### Use this template

This is a template repository: don't clone it, click the green `Use this template` button at the top-right of the GitHub repo page.
Once you've created your repository from it, clone it and follow the instructions below.

**Next steps after creating from template** (or later when you feel like it)
1. In `pyproject.toml`, replace "my-project" with your project name in the header, then replace "my_project" with your package name (using underscores) in `[tool.mypy]` `packages` and `[tool.pyright]` `include`.
2. Rename the `my_project/` directory to your package name (use underscores).
3. Update this README.md with your project details.
4. Update the package imports in your code as needed.

## Prerequisites

Access to a **Pipelex API** server. You have two options:

- **Hosted** — currently in private beta. Join the waitlist at [go.pipelex.com/waitlist](https://go.pipelex.com/waitlist). Once you have access, get an API key at [app.pipelex.com](https://app.pipelex.com) and point `PIPELEX_BASE_URL` at `https://api.pipelex.com` (the default).
- **Self-hosted** — the Pipelex API is open source at [github.com/Pipelex/pipelex-api](https://github.com/Pipelex/pipelex-api). Run it locally or on your own infra and point `PIPELEX_BASE_URL` at your instance (e.g. `http://127.0.0.1:8081`).

## Quick start

```bash
cp .env.example .env
# edit .env and set PIPELEX_API_KEY (and PIPELEX_BASE_URL if self-hosting)

make install                       # create the venv and install deps with uv
uv run my-project extract-entities "Alice from Acme met Bob on May 3rd, 2026."
```

That prints the extracted people, organizations, and dates as JSON. (`uv run` finds the project's venv; activate it with `source .venv/bin/activate` if you'd rather drop the prefix and just call `my-project ...`.)

## Project structure

```
my_project/
  cli.py                         # the `my-project` Typer CLI (console-script entry point)
  runner.py                      # execution-mode dispatch: blocking / durable attended / detached
  errors.py                      # maps SDK errors to CLI messages + hints
  file_input.py                  # encode a local file into a Pipelex Document input envelope
  examples/                      # one "copy me" unit per demo: bundle path, output model, parse()
    extract_entities.py          #   text → { people, orgs, dates }
    summarize_pdf.py             #   document → { title, doc_type, key_points }
    generate_image.py            #   prompt → image
  methods/                       # the method bundles (sent to the API as content)
    extract-entities/main.mthds
    summarize-pdf/main.mthds
    generate-image/main.mthds
samples/
  sample-invoice.pdf             # a document to try `summarize-pdf` on
tests/
  unit/                          # offline CLI / example / error-mapping tests
  integration/                   # offline boot/bundle checks + API validate (pipelex_api)
  e2e/                           # full run against the API (inference)
.env.example                     # PIPELEX_BASE_URL + PIPELEX_API_KEY
```

## How it works

`my-project extract-entities "<text>"`:

1. Reads the `.mthds` bundle from disk (`extract_entities.BUNDLE_PATH`) and constructs a `PipelexAPIClient`, which picks up `PIPELEX_BASE_URL` / `PIPELEX_API_KEY` from the environment.
2. Runs the pipe against the API in one of **two execution modes** (`--mode`, env var `PIPELEX_EXECUTION_MODE`):
   - **durable** (default) — `client.start()` then poll the run to completion (`client.wait_for_result`). Survives the hosted gateway's ~30s synchronous cap, so long runs succeed; the run id is printed first, so a Ctrl-C leaves it executing server-side and you can resume with `my-project runs wait <id>`.
   - **blocking** — a single `client.execute()` call. Simpler, but behind the hosted gateway a run over ~30s is cut off and surfaces a clear timeout error pointing you at durable mode.
3. Reads the resolved main output — the SDK exposes `results.main_stuff` on both modes — and the example's `parse()` narrower validates it into a typed `ExtractedEntities` model, printed as JSON.

The `.mthds` bundle is sent to the API as content (`mthds_contents`), so nothing about the method needs to live in the runtime — edit `methods/extract-entities/main.mthds` and re-run.

`my_project/runner.py` deliberately branches on the mode explicitly rather than calling the SDK's `start_and_wait()` self-healing one-liner (the production shortcut when you don't care which mode) — teaching the difference between the two paths is the point of this starter. Pass `--detach` (durable only) to start a run and return immediately, then pick it back up later with `my-project runs status|result|wait <id>`.

The other two examples run through the exact same dispatch and lifecycle — they only differ in their input and output shapes:

- **`summarize-pdf <file>`** takes a *file* input. `file_input.build_document_input()` reads the file, base64-encodes it into a `data:` URL, and wraps it in a `{ "concept": "Document", "content": … }` envelope; the API decodes and stores it server-side, so you never host the file yourself.
- **`generate-image "<prompt>"`** is slow enough to routinely exceed the hosted ~30s blocking cap. Run it with `--mode blocking` to watch it hit the wall (a classified `PipelineExecuteTimeoutError` with a hint), then with `--mode durable` (the default) to actually get an image back.

## Useful commands

```bash
uv run my-project extract-entities "Alice from Acme met Bob on May 3rd, 2026."  # text → entities
uv run my-project extract-entities --file notes.txt          # read the input text from a file
uv run my-project summarize-pdf samples/sample-invoice.pdf   # document → { title, doc_type, key_points }
uv run my-project generate-image "a fox reading under a tree"  # prompt → image (use durable, the default)
uv run my-project generate-image "…" --mode blocking         # watch it hit the ~30s cap with a timeout hint
uv run my-project extract-entities "…" --detach              # start a durable run, print its id, return
uv run my-project runs wait <run-id>                         # resume a detached run to completion (also: runs status / runs result)
make validate     # lint/validate the .mthds bundles with plxt (offline)
make agent-check  # fix-imports + format + lint + pyright + mypy
make agent-test   # run the offline test suite (silent on success)
make test-inference  # run the tests that hit the API (needs a key)
```

## Contact & Support

| Channel                                | Use case                                                                  |
| -------------------------------------- | ------------------------------------------------------------------------- |
| **GitHub Discussions → "Show & Tell"** | Share ideas, brainstorm, get early feedback.                              |
| **GitHub Issues**                      | Report bugs or request features.                                          |
| **Email (privacy & security)**         | [security@pipelex.com](mailto:security@pipelex.com)                       |
| **Discord**                            | Real-time chat — [https://go.pipelex.com/discord](https://go.pipelex.com/discord) |

## 📝 License

This project is licensed under the [MIT license](LICENSE). Runtime dependencies are distributed under their own licenses via PyPI.

---

*Happy piping!* 🚀
