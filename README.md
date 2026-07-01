# My Project ⚡️

*Replace "My Project" with your actual project name*

A minimal Python CLI starter that calls the [Pipelex](https://pipelex.com) API via the [`pipelex-sdk`](https://pypi.org/project/pipelex-sdk/) SDK to run AI methods (`.mthds` bundles) — no local Pipelex runtime required.

It ships one demo pipeline, `my_project/hello_world.mthds`, which asks an LLM to write a haiku about "Hello World" and prints it.

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

- **Hosted** — currently in private beta. Join the waitlist at [go.pipelex.com/waitlist](https://go.pipelex.com/waitlist). Once you have access, get an API key at [app.pipelex.com](https://app.pipelex.com) and point `PIPELEX_API_URL` at `https://api.pipelex.com` (the default).
- **Self-hosted** — the Pipelex API is open source at [github.com/Pipelex/pipelex-api](https://github.com/Pipelex/pipelex-api). Run it locally or on your own infra and point `PIPELEX_API_URL` at your instance (e.g. `http://127.0.0.1:8081`).

## Quick start

```bash
cp .env.example .env
# edit .env and set PIPELEX_API_KEY (and PIPELEX_API_URL if self-hosting)

make install                       # create the venv and install deps with uv
python -m my_project.hello_world   # run the hello_world example against the API
```

That prints the generated haiku.

## Project structure

```
my_project/
  hello_world.mthds   # the method bundle: text → { text } haiku
  hello_world.py      # the CLI entry point that runs the bundle via the SDK
tests/
  integration/        # offline boot/bundle checks + API validate (pipelex_api)
  e2e/                # full run against the API (inference)
.env.example          # PIPELEX_API_URL + PIPELEX_API_KEY
```

## How it works

`my_project/hello_world.py`:

1. Reads the `.mthds` bundle from disk (`BUNDLE_PATH`).
2. Constructs a `PipelexAPIClient`, which reads `PIPELEX_API_URL` / `PIPELEX_API_KEY` from the environment.
3. Calls `start_and_wait(pipe_code="hello_world", mthds_contents=[bundle])` — the durable start-and-poll path that survives the hosted gateway's ~30s synchronous cap and self-heals to a blocking `execute` against a bare self-hosted runner.
4. Reads the main output's content (`{"text": ...}`) out of the loosely-typed result and prints it.

The `.mthds` bundle is sent to the API as content (`mthds_contents`), so nothing about the method needs to live in the runtime — edit `hello_world.mthds` and re-run.

## Useful commands

```bash
python -m my_project.hello_world  # run the hello_world example
make validate     # lint/validate the .mthds bundle with plxt (offline)
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
