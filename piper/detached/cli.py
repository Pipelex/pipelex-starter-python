"""The detached CLI — start a durable run and walk away; collect it later.

`client.start(...)` submits the run server-side and this command exits with the run
id on stdout, so it pipes: `RUN_ID=$(piper detached generate-image "a fox")`. All the
run's state lives behind that id, so you pick it back up whenever you like — even
from another terminal, another machine, another day:

- `piper detached wait <id>`   — poll it to completion and print its result.
- `piper detached status <id>` — where is it right now, without waiting.
- `piper detached result <id>` — its result if it is done, without waiting.

Same durable run as `piper attended`; the only difference is who waits.

Copy-paste unit: this file + `piper/inputs.py` + `piper/errors.py`. The three mode
packages never share lifecycle code, so the demo commands below are deliberate
mirrors of their `blocking` / `attended` twins: only `start_pipe()` differs — plus
the run-lifecycle commands, which exist only here.
"""

import asyncio
from pathlib import Path
from typing import Annotated, Any, Coroutine, TypeVar

import httpx
import typer
from mthds.protocol.exceptions import PipelineRequestError
from pipelex_sdk.client import PipelexAPIClient
from pipelex_sdk.runs import PollInfo, RunRead, RunResultCompleted, RunResultFailed, RunResultRunning, RunResultState, WaitForResultOptions
from rich.console import Console

from piper.errors import present_error
from piper.inputs import build_document_input, read_text_input

ResultT = TypeVar("ResultT")

METHODS_DIR = Path(__file__).parent.parent / "methods"

app = typer.Typer(no_args_is_help=True, help="Start a demo as a durable run and exit; collect the result later.")

# Results go to stdout (pipeable); progress chatter goes to stderr.
output_console = Console()
progress_console = Console(stderr=True)


async def start_pipe(*, pipe_code: str, bundle: str, inputs: dict[str, Any]) -> str:
    """The whole detached lifecycle: start a durable run, return its id, don't wait.

    Credentials come from `PIPELEX_API_KEY` / `PIPELEX_BASE_URL`. The run keeps
    executing server-side after this process exits.
    """
    async with PipelexAPIClient() as client:
        start_result = await client.start(pipe_code=pipe_code, mthds_contents=[bundle], inputs=inputs)
    return start_result.pipeline_run_id


async def attend_run(run_id: str) -> Any:
    """Poll an already-started run to completion and resolve its main output."""
    async with PipelexAPIClient() as client:
        short_id = run_id[:8]
        with progress_console.status(f"Run {short_id}… in progress") as status:

            def on_poll(info: PollInfo) -> None:
                status.update(f"Run {short_id}… in progress — {info.elapsed_seconds:.0f}s, poll #{info.attempt}")

            try:
                results = await client.wait_for_result(run_id, options=WaitForResultOptions(on_poll=on_poll))
            except asyncio.CancelledError:
                # Ctrl-C: the run keeps executing server-side — nothing is lost, just wait on it again.
                progress_console.print(f"\nInterrupted — the run is still executing. Resume with: [bold]piper detached wait {run_id}[/bold]")
                raise
    return results.main_stuff


async def fetch_run_status(run_id: str) -> RunRead:
    """Fetch a run's coarse status (`GET /v1/runs/{id}/status`) — no polling."""
    async with PipelexAPIClient() as client:
        return await client.get_run_status(run_id)


async def fetch_run_result(run_id: str) -> RunResultState:
    """Fetch a run's result state (`GET /v1/runs/{id}/results`) — no polling."""
    async with PipelexAPIClient() as client:
        return await client.get_run_result(run_id)


@app.command(name="extract-entities")
def extract_entities(
    text: Annotated[str | None, typer.Argument(help="The text to extract entities from.")] = None,
    file: Annotated[Path | None, typer.Option("--file", help="Read the input text from a file instead of the argument.")] = None,
) -> None:
    """Start extracting people, organizations, and dates from a piece of text."""
    input_text = read_text_input(text=text, file=file)
    bundle = (METHODS_DIR / "extract-entities" / "main.mthds").read_text()
    run_id = _run(start_pipe(pipe_code="extract_entities", bundle=bundle, inputs={"text": input_text}))
    _print_run_id(run_id)


@app.command(name="summarize-pdf")
def summarize_pdf(file: Annotated[Path, typer.Argument(help="Path to the PDF (or other document) to summarize.")]) -> None:
    """Start summarizing a document into a title, type, and key points."""
    if not file.is_file():
        msg = f"No such file: {file}"
        raise typer.BadParameter(msg)
    bundle = (METHODS_DIR / "summarize-pdf" / "main.mthds").read_text()
    inputs = {"document": build_document_input(file)}
    run_id = _run(start_pipe(pipe_code="summarize_pdf", bundle=bundle, inputs=inputs))
    _print_run_id(run_id)


@app.command(name="generate-image")
def generate_image(
    prompt: Annotated[str | None, typer.Argument(help="The text prompt describing the image to generate.")] = None,
    file: Annotated[Path | None, typer.Option("--file", help="Read the prompt from a file instead of the argument.")] = None,
) -> None:
    """Start generating an image from a text prompt.

    The demo that makes detached mode obvious: image generation is slow enough that
    you would rather not hold a terminal open for it.
    """
    image_prompt = read_text_input(text=prompt, file=file)
    bundle = (METHODS_DIR / "generate-image" / "main.mthds").read_text()
    run_id = _run(start_pipe(pipe_code="generate_image", bundle=bundle, inputs={"image_prompt": image_prompt}))
    _print_run_id(run_id)


@app.command(name="wait")
def wait(run_id: Annotated[str, typer.Argument(help="The pipeline run id printed when the run started.")]) -> None:
    """Poll a run to completion, then print its result."""
    main_stuff = _run(attend_run(run_id))
    _print_main_stuff(main_stuff)


@app.command(name="status")
def status(run_id: Annotated[str, typer.Argument(help="The pipeline run id printed when the run started.")]) -> None:
    """Show a run's coarse status without waiting."""
    run = _run(fetch_run_status(run_id))
    pipe_part = f" (pipe: {run.pipe_code})" if run.pipe_code else ""
    output_console.print(f"{run.pipeline_run_id}: [bold]{run.status}[/bold]{pipe_part}")
    if run.degraded:
        output_console.print("[yellow]Status is degraded — last-known value, the status backend was unreachable; retry shortly.[/yellow]")


@app.command(name="result")
def result(run_id: Annotated[str, typer.Argument(help="The pipeline run id printed when the run started.")]) -> None:
    """Fetch a run's result if it is finished (no waiting)."""
    state = _run(fetch_run_result(run_id))
    match state:
        case RunResultRunning():
            progress_console.print(
                f"Run {state.pipeline_run_id} is still running — wait for it with: [bold]piper detached wait {state.pipeline_run_id}[/bold]"
            )
        case RunResultCompleted():
            _print_main_stuff(state.result.main_stuff)
        case RunResultFailed():
            progress_console.print(f"[red]Run {state.pipeline_run_id} ended with status {state.status}: {state.message}[/red]")
            raise typer.Exit(1)


def _print_run_id(run_id: str) -> None:
    """The id on stdout (bare, so `$(piper detached …)` captures it), the hint on stderr."""
    print(run_id)
    progress_console.print(f"Run started — fetch it later with: [bold]piper detached wait {run_id}[/bold]")


def _print_main_stuff(main_stuff: Any) -> None:
    """Print a run's main output as raw JSON — generic, since any run id can land here."""
    output_console.print_json(data=main_stuff)


def _run(coro: Coroutine[Any, Any, ResultT]) -> ResultT:
    """Await the lifecycle, presenting SDK errors and Ctrl-C as clean exits.

    Every error the SDK client raises descends from `PipelineRequestError`, except the
    raw `httpx.HTTPStatusError` its protocol routes surface. Nothing else is caught:
    an unexpected exception crashes loudly with its traceback.
    """
    try:
        return asyncio.run(coro)
    except (PipelineRequestError, httpx.HTTPStatusError) as exc:
        presentation = present_error(exc)
        progress_console.print(f"[red]Error:[/red] {presentation.message}")
        if presentation.hint:
            progress_console.print(f"[yellow]Hint:[/yellow] {presentation.hint}")
        raise typer.Exit(1) from exc
    except KeyboardInterrupt as exc:
        # The resume hint was already printed by `attend_run`; the run keeps executing server-side.
        raise typer.Exit(130) from exc


if __name__ == "__main__":
    app()
