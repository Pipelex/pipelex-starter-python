#!/usr/bin/env python3
"""Regenerate the committed typed clients for every method in `piper/methods/`.

This is what `make codegen` runs, and it needs nothing but `PIPELEX_API_KEY`: the
projection is done by the hosted API (`POST /v1/codegen`, reached through
`pipelex-sdk`, the starter's own dependency), not by a local `pipelex` runtime.
The `pipelex` CLI is deliberately not installed here, so asking a Python user to
find one before `make codegen` works was asking them to install the whole engine
to read three models. Its JS twin is `pipelex-starter-js/scripts/codegen.mts`.

One generated tree per method, mirroring `piper/methods/` one-to-one: each method
is its own closure, so each gets its own crate, artifact set and lock. The tree is
written **verbatim** — every `artifacts[]` entry at its `path`, the `lock` as
`codegen.lock` — because that byte-for-byte fidelity is what makes it identical to
a local `pipelex codegen types` run, and therefore what lets the offline drift
check (`make codegen-check`) pass on it. Reformatting an artifact or
re-serializing the lock breaks that trust chain, which is why the writing is
`pipelex-sdk`'s `write_codegen_tree` and not a loop of our own: it validates every
path first, refuses to overwrite a file codegen does not own, writes only what
changed, and prunes stamped artifacts that dropped out of the set.

Nothing here is method-specific: methods are discovered from the filesystem, so
adding one to `piper/methods/` is all it takes for the next run to generate it
(the generated package still has to be listed in `pyproject.toml`, which is what
ships it in a wheel).
"""

from __future__ import annotations

import asyncio
import os
import sys
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv

try:
    from pipelex_sdk.client import DEFAULT_API_BASE_URL, PipelexAPIClient
    from pipelex_sdk.codegen_writer import write_codegen_tree
    from pipelex_sdk.crate_models import CodegenRequest, CodegenTarget, CodegenValidReport, MthdsFileItem
    from pipelex_sdk.errors import ApiResponseError, CodegenError
except ImportError as exc:  # pragma: no cover
    # The floor in pyproject.toml cannot name the release that ships `write_codegen_tree`
    # and the `crate_models` envelope until that release is on PyPI, so say what is
    # missing instead of letting a bare ModuleNotFoundError land on a starter user.
    # Delete this guard when the floor is raised.
    raise SystemExit(
        f"codegen: the installed pipelex-sdk is older than this script needs ({exc}).\n"
        "  `make codegen` needs the pipelex-sdk release that ships `write_codegen_tree`\n"
        "  (pipelex_sdk.codegen_writer). Raise the pipelex-sdk floor in pyproject.toml,\n"
        "  then run `make li`."
    ) from exc

REPO_ROOT = Path(__file__).resolve().parent.parent
METHODS_DIR = REPO_ROOT / "piper" / "methods"
GENERATED_ROOT = REPO_ROOT / "piper" / "generated"

#: Python consumers want self-contained pydantic models — the other targets
#: (`python-structures`, `ts-zod`) are for a Pipelex host and for TypeScript.
TARGET: CodegenTarget = "python-pydantic"

EXIT_OK = 0
EXIT_FAILED = 1


@dataclass(frozen=True)
class MethodSource:
    """One method's closure: its `.mthds` files and the package its tree is written into."""

    name: str
    files: list[MthdsFileItem]
    out_dir: Path


def discover_methods() -> list[MethodSource]:
    """Read every method under `piper/methods/` as a closure, in directory order.

    A method's directory holds its whole closure, so every `.mthds` file in it is sent —
    one for a single-file bundle, several for a multi-file one. The generated package is
    the method's directory name with dashes turned into underscores (`summarize-pdf` →
    `piper/generated/summarize_pdf`), which is the mapping the CLIs' imports already use.
    Each file carries its repo-relative path as `source`, so a diagnostic the server
    raises names a file you can open.
    """
    methods: list[MethodSource] = []
    for method_dir in sorted(path for path in METHODS_DIR.iterdir() if path.is_dir()):
        bundle_files = sorted(method_dir.glob("*.mthds"))
        if not bundle_files:
            continue
        files = [MthdsFileItem(content=path.read_text(), source=str(path.relative_to(REPO_ROOT))) for path in bundle_files]
        methods.append(MethodSource(name=method_dir.name, files=files, out_dir=GENERATED_ROOT / method_dir.name.replace("-", "_")))
    return methods


def explain(exc: Exception, base_url: str) -> str:
    """Turn a failure into an actionable line, naming the fix where we know it."""
    if isinstance(exc, ApiResponseError) and exc.status in (403, 404):
        return (
            f"this base URL does not serve POST /v1/codegen (HTTP {exc.status}).\n"
            f"    Base URL: {base_url}\n"
            "    The hosted Pipelex API serves this route — check PIPELEX_BASE_URL in .env,\n"
            "    or drop it to use the default."
        )
    if isinstance(exc, ApiResponseError):
        return f"HTTP {exc.status} from POST /v1/codegen — {exc.server_message or exc}"
    return str(exc)


async def generate_method(client: PipelexAPIClient, method: MethodSource, base_url: str) -> bool:
    """Generate one method end to end — request, guard, write, report. Returns whether it worked.

    Never raises: a failure is reported and returned, so one bad method neither aborts the
    run nor skips the methods after it.
    """
    try:
        # No `pipe_ref`: the `types` kind is concept-set-wide and rejects it with a 422.
        response = await client.codegen(CodegenRequest(files=method.files, kind="types", target=TARGET))
    # Broad on purpose: every transport and request-shape failure is this method's failure
    # to report, not a reason to abort the methods after it.
    except Exception as exc:
        print(f"\n✗ {method.name} — {explain(exc, base_url)}", file=sys.stderr)
        return False

    # An unresolvable closure is a produced verdict on a 200, so it is branched on rather
    # than caught — and it writes nothing: types projected from a method that does not
    # resolve would describe a method that cannot run.
    if not isinstance(response, CodegenValidReport):
        print(f"\n✗ {method.name} — the closure does not resolve:", file=sys.stderr)
        for item in response.validation_errors:
            print(f"    {item.source or '?'}: {item.message}", file=sys.stderr)
        return False

    try:
        written = write_codegen_tree(response, output_dir=method.out_dir)
    except CodegenError as exc:
        print(f"\n✗ {method.name} — writing the tree failed: {exc}", file=sys.stderr)
        return False

    tree = method.out_dir.relative_to(REPO_ROOT)
    print(f"\n✓ {method.name} → {tree}/  (crate {response.crate_fingerprint[:12]}, engine {response.engine_version})")
    changed = [f"wrote {path}" for path in written.written] + [f"removed {path}" for path in written.removed]
    if written.lock_written:
        changed.append("wrote codegen.lock")
    for line in changed or ["no changes"]:
        print(f"    {line}")
    return True


async def run_codegen() -> int:
    """The whole `make codegen` behaviour, exit code included."""
    load_dotenv()

    base_url = os.environ.get("PIPELEX_BASE_URL") or DEFAULT_API_BASE_URL
    if not os.environ.get("PIPELEX_API_KEY"):
        print("codegen: PIPELEX_API_KEY is not set — add it to .env (see .env.example).", file=sys.stderr)
        return EXIT_FAILED

    methods = discover_methods()
    if not methods:
        print(f"codegen: no methods found under {METHODS_DIR.relative_to(REPO_ROOT)}/.", file=sys.stderr)
        return EXIT_FAILED

    print(f"codegen: {', '.join(method.name for method in methods)} — via {base_url}")
    failed = False
    async with PipelexAPIClient() as client:
        for method in methods:
            if not await generate_method(client, method, base_url):
                failed = True
    return EXIT_FAILED if failed else EXIT_OK


if __name__ == "__main__":
    sys.exit(asyncio.run(run_codegen()))
