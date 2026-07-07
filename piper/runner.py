"""Execution-mode dispatch for the CLI: blocking, durable attended, durable detached.

Each function opens its own `PipelexAPIClient` (credentials come from
`PIPELEX_API_KEY` / `PIPELEX_BASE_URL`), demonstrates exactly one SDK lifecycle
call, and renders progress with Rich on stderr — stdout stays clean for results.

- blocking          -> `client.execute`          (one call, dies at the hosted ~30s cap)
- durable attended  -> `client.start` + `client.wait_for_result` (survives anything)
- durable detached  -> `client.start` only       (come back later with `runs ...`)

The SDK also offers `start_and_wait`, a self-healing one-liner that picks the
right path by itself — this starter branches explicitly because teaching the
difference is the point.
"""

import asyncio
from enum import Enum
from typing import Any

from pipelex_sdk.client import PipelexAPIClient
from pipelex_sdk.runs import PollInfo, RunRead, RunResults, RunResultState, WaitForResultOptions
from rich.console import Console

# Progress and lifecycle chatter go to stderr so stdout stays pipeable.
progress_console = Console(stderr=True)


class ExecutionMode(str, Enum):
    """How a run is executed against the API — see the module docstring."""

    BLOCKING = "blocking"
    DURABLE = "durable"


async def run_blocking(*, pipe_code: str, bundle: str, inputs: dict[str, Any] | None = None) -> RunResults:
    """Execute synchronously (`POST /v1/execute`) and wait for the response.

    Simple, but behind the hosted gateway a run longer than ~30s raises
    `PipelineExecuteTimeoutError` — the CLI turns that into a "use durable" hint.
    """
    async with PipelexAPIClient() as client:
        with progress_console.status("Running (blocking)…"):
            result = await client.execute(pipe_code=pipe_code, mthds_contents=[bundle], inputs=inputs)
    # Adapt the blocking `execute` result onto `RunResults` so both modes return one type;
    # `.main_stuff` is already resolved by the SDK (it raises `MissingMainStuffError` if a
    # completed run named no main stuff).
    return RunResults(pipeline_run_id=result.pipeline_run_id, main_stuff=result.main_stuff)


async def run_durable_attended(*, pipe_code: str, bundle: str, inputs: dict[str, Any] | None = None) -> RunResults:
    """Start a durable run, print its id immediately, then poll it to completion.

    The id is printed before polling so the run is never lost: Ctrl-C leaves it
    executing server-side and you can resume with `my-project runs wait <id>`.
    """
    async with PipelexAPIClient() as client:
        start_result = await client.start(pipe_code=pipe_code, mthds_contents=[bundle], inputs=inputs)
        run_id = start_result.pipeline_run_id
        progress_console.print(f"Run started: [bold]{run_id}[/bold]")
        return await _attend(client=client, run_id=run_id)


async def start_detached(*, pipe_code: str, bundle: str, inputs: dict[str, Any] | None = None) -> str:
    """Start a durable run and return its id without waiting.

    The run keeps executing server-side; fetch it later with
    `my-project runs status|result|wait <id>` — even from another terminal.
    """
    async with PipelexAPIClient() as client:
        start_result = await client.start(pipe_code=pipe_code, mthds_contents=[bundle], inputs=inputs)
    return start_result.pipeline_run_id


async def wait_for_run(run_id: str) -> RunResults:
    """Poll an already-started run to completion with a live status line."""
    async with PipelexAPIClient() as client:
        return await _attend(client=client, run_id=run_id)


async def fetch_run_status(run_id: str) -> RunRead:
    """Fetch a run's coarse status (`GET /v1/runs/{id}/status`)."""
    async with PipelexAPIClient() as client:
        return await client.get_run_status(run_id)


async def fetch_run_result(run_id: str) -> RunResultState:
    """Fetch a run's result state (`GET /v1/runs/{id}/results`) without polling."""
    async with PipelexAPIClient() as client:
        return await client.get_run_result(run_id)


async def _attend(*, client: PipelexAPIClient, run_id: str) -> RunResults:
    """Poll a run to its terminal state, driving a Rich status line per poll."""
    short_id = run_id[:8]
    with progress_console.status(f"Run {short_id}… in progress") as status:

        def on_poll(info: PollInfo) -> None:
            status.update(f"Run {short_id}… in progress — {info.elapsed_seconds:.0f}s, poll #{info.attempt}")

        try:
            return await client.wait_for_result(run_id, options=WaitForResultOptions(on_poll=on_poll))
        except asyncio.CancelledError:
            # Ctrl-C: the run keeps executing server-side — tell the user how to pick it back up.
            progress_console.print(f"\nInterrupted — the run is still executing. Resume with: [bold]my-project runs wait {run_id}[/bold]")
            raise
