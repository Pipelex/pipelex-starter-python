# PR #62 review — deferred items

Review-agent findings on [PR #62](https://github.com/Pipelex/pipelex-starter-python/pull/62) that were verified as real but deliberately **not** fixed in the PR. Each entry records why it was deferred and what a future fix would look like.

## Sample PDF is not packaged into a wheel

- **Reporters:** greptile-apps (`piper/inputs.py:33`), cubic-dev-ai (`piper/attended/cli.py:94`)
- **Finding (verified):** `SAMPLE_INVOICE` resolves to the repo-root `samples/sample-invoice.pdf` via `Path(__file__).parent.parent`, and `pyproject.toml` only ships package data under `piper.*`. On a true wheel install, the zero-argument `summarize-pdf` demo would fail with `FileNotFoundError`.
- **Why deferred:** this repo is a template — README says "Use this template", install is `make install` (uv, editable), and wheel distribution is not a supported or advertised path. The repo-root `samples/` location is deliberately user-facing (README documents `samples/sample-invoice.pdf` as a path to inspect and replace). Fixing this would move the sample under `piper/` (importlib.resources + package-data) and regress that documented UX for a scenario nobody uses.
- **Revisit if:** the template ever starts being consumed as an installed wheel.

## Ctrl-C during the initial `client.start` can lose the run id

- **Reporter:** cubic-dev-ai (`piper/attended/cli.py:54`)
- **Finding (verified):** a Ctrl-C landing while the `client.start` request is in flight — after the server committed the run but before the client printed the id — leaves a durable run with no id to resume from. The window is real in both attended and detached modes.
- **Why deferred:** unsolvable client-side. `PipelexAPIClient.start` has no idempotency-key parameter and no accepted-id recovery; closing the window needs server/SDK support (idempotency keys on `/v1/start`). Building persistence around a not-yet-received id in a teaching starter would be overengineering. The attended module docstring was softened in the PR to scope the "Ctrl-C doesn't lose the run" guarantee to the post-start window.
- **Where the real fix lives:** `pipelex-sdk-python` / the platform API (idempotent submission), not this repo.

