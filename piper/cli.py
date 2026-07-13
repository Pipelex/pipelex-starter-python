"""The `piper` CLI — demo Pipelex methods behind a Typer app.

Each demo command is the self-contained "copy me" unit: it reads its bundle
from `piper/methods/`, dispatches on execution mode via `piper.runner`, and
narrows the run result into its *generated* output model (`piper/generated/`,
produced from the bundles by `pipelex codegen` — nothing method-shaped is
hand-written). SDK errors are caught once per command (in `_run_cli`) and
presented by `piper.errors`; anything unexpected crashes loudly.
"""

import asyncio
from pathlib import Path
from typing import Annotated, Any, Coroutine, TypeAlias, TypeVar

import httpx
import typer
from dotenv import load_dotenv
from mthds.protocol.exceptions import PipelineRequestError
from pipelex_sdk.runs import RunResultCompleted, RunResultFailed, RunResultRunning, RunResults, RunResultState
from rich.console import Console

from piper.errors import present_error
from piper.file_input import build_document_input
from piper.generated.extract_entities.models import ExtractedEntities
from piper.generated.generate_image.models import Image
from piper.generated.summarize_pdf.models import DocumentSummary
from piper.runner import (
    ExecutionMode,
    fetch_run_result,
    fetch_run_status,
    progress_console,
    run_blocking,
    run_durable_attended,
    start_detached,
    wait_for_run,
)

ResultT = TypeVar("ResultT")

METHODS_DIR = Path(__file__).parent / "methods"

app = typer.Typer(no_args_is_help=True, help="Run the demo Pipelex methods through the Pipelex API.")
runs_app = typer.Typer(no_args_is_help=True, help="Inspect and resume durable runs by id.")
app.add_typer(runs_app, name="runs")

# Results go to stdout (pipeable); progress/status chatter goes to stderr (see runner.py).
output_console = Console()

MODE_HELP = (
    "How to execute the run: `durable` (start, then poll here until it is done — survives anything), "
    "`detached` (start durably and exit; collect it later with `piper runs ...`), "
    "or `blocking` (single call, ~30s cap on hosted)."
)

# Every demo command takes the same mode option, so it is declared once.
ModeOption: TypeAlias = Annotated[ExecutionMode, typer.Option(envvar="PIPELEX_EXECUTION_MODE", help=MODE_HELP)]


@app.callback()
def main() -> None:
    """Load .env so PIPELEX_BASE_URL / PIPELEX_API_KEY are available."""
    load_dotenv()


@app.command(name="extract-entities")
def extract_entities(
    text: Annotated[str | None, typer.Argument(help="The text to extract entities from.")] = None,
    file: Annotated[Path | None, typer.Option("--file", help="Read the input text from a file instead of the argument.")] = None,
    mode: ModeOption = ExecutionMode.DURABLE,
) -> None:
    """Extract people, organizations, and dates from a piece of text."""
    input_text = _read_text_input(text=text, file=file)
    bundle = (METHODS_DIR / "extract-entities" / "main.mthds").read_text()
    results = _dispatch(
        pipe_code="extract_entities",
        bundle=bundle,
        inputs={"text": input_text},
        mode=mode,
    )
    if results is None:
        return
    # Narrow into the generated typed model (validates the concept's shape), then
    # print it as JSON — the same rendering `runs result` / `runs wait` give.
    entities = ExtractedEntities.model_validate(results.main_stuff)
    output_console.print_json(data=entities.model_dump())


@app.command(name="summarize-pdf")
def summarize_pdf(
    file: Annotated[Path, typer.Argument(help="Path to the PDF (or other document) to summarize.")],
    mode: ModeOption = ExecutionMode.DURABLE,
) -> None:
    """Summarize a document into a title, type, and key points."""
    if not file.is_file():
        msg = f"No such file: {file}"
        raise typer.BadParameter(msg)
    bundle = (METHODS_DIR / "summarize-pdf" / "main.mthds").read_text()
    results = _dispatch(
        pipe_code="summarize_pdf",
        bundle=bundle,
        inputs={"document": build_document_input(file)},
        mode=mode,
    )
    if results is None:
        return
    summary = DocumentSummary.model_validate(results.main_stuff)
    output_console.print_json(data=summary.model_dump())


@app.command(name="generate-image")
def generate_image(
    prompt: Annotated[str | None, typer.Argument(help="The text prompt describing the image to generate.")] = None,
    file: Annotated[Path | None, typer.Option("--file", help="Read the prompt from a file instead of the argument.")] = None,
    mode: ModeOption = ExecutionMode.DURABLE,
) -> None:
    """Generate an image from a text prompt.

    Image generation routinely outlives the hosted ~30s blocking cap, so this is
    the example to run with `--mode blocking` to see a timeout — then `--mode
    durable` (the default) to actually get an image.
    """
    image_prompt = _read_text_input(text=prompt, file=file)
    bundle = (METHODS_DIR / "generate-image" / "main.mthds").read_text()
    results = _dispatch(
        pipe_code="generate_image",
        bundle=bundle,
        inputs={"image_prompt": image_prompt},
        mode=mode,
    )
    if results is None:
        return
    # On the hosted path the runtime returns a storage `url` (`pipelex-storage://…`)
    # *and* a web-renderable `public_url` (a signed URL); the model keeps both.
    image = Image.model_validate(results.main_stuff)
    output_console.print_json(data=image.model_dump())


@runs_app.command(name="status")
def runs_status(run_id: Annotated[str, typer.Argument(help="The pipeline run id printed when the run started.")]) -> None:
    """Show a run's coarse status without waiting."""
    run = _run_cli(fetch_run_status(run_id))
    pipe_part = f" (pipe: {run.pipe_code})" if run.pipe_code else ""
    output_console.print(f"{run.pipeline_run_id}: [bold]{run.status}[/bold]{pipe_part}")
    if run.degraded:
        output_console.print("[yellow]Status is degraded — last-known value, the status backend was unreachable; retry shortly.[/yellow]")


@runs_app.command(name="result")
def runs_result(run_id: Annotated[str, typer.Argument(help="The pipeline run id printed when the run started.")]) -> None:
    """Fetch a run's result if it is finished (no waiting)."""
    state = _run_cli(fetch_run_result(run_id))
    _render_result_state(state)


@runs_app.command(name="wait")
def runs_wait(run_id: Annotated[str, typer.Argument(help="The pipeline run id printed when the run started.")]) -> None:
    """Poll a run to completion, then print its raw result."""
    results = _run_cli(wait_for_run(run_id))
    _print_raw_results(results)


def _read_text_input(*, text: str | None, file: Path | None) -> str:
    if text is not None and file is not None:
        msg = "Give the text either as an argument or via --file, not both."
        raise typer.BadParameter(msg)
    if file is not None:
        return file.read_text()
    if text is not None:
        return text
    msg = "Give the text to process as an argument, or point --file at a text file."
    raise typer.BadParameter(msg)


def _dispatch(*, pipe_code: str, bundle: str, inputs: dict[str, Any], mode: ExecutionMode) -> RunResults | None:
    """Run the pipe in the requested mode; returns None in detached mode, which has no result to print yet."""
    match mode:
        case ExecutionMode.BLOCKING:
            return _run_cli(run_blocking(pipe_code=pipe_code, bundle=bundle, inputs=inputs))
        case ExecutionMode.DURABLE:
            return _run_cli(run_durable_attended(pipe_code=pipe_code, bundle=bundle, inputs=inputs))
        case ExecutionMode.DETACHED:
            run_id = _run_cli(start_detached(pipe_code=pipe_code, bundle=bundle, inputs=inputs))
            print(run_id)
            progress_console.print(f"Run started — fetch it later with: [bold]piper runs wait {run_id}[/bold]")
            return None


def _run_cli(coro: Coroutine[Any, Any, ResultT]) -> ResultT:
    """Await a runner coroutine, presenting SDK errors and Ctrl-C as clean exits."""
    try:
        return asyncio.run(coro)
    except (PipelineRequestError, httpx.HTTPStatusError) as exc:
        presentation = present_error(exc)
        progress_console.print(f"[red]Error:[/red] {presentation.message}")
        if presentation.hint:
            progress_console.print(f"[yellow]Hint:[/yellow] {presentation.hint}")
        raise typer.Exit(1) from exc
    except KeyboardInterrupt as exc:
        # The resume hint was already printed by the runner; the run keeps executing server-side.
        raise typer.Exit(130) from exc


def _render_result_state(state: RunResultState) -> None:
    match state:
        case RunResultRunning():
            progress_console.print(
                f"Run {state.pipeline_run_id} is still running — wait for it with: [bold]piper runs wait {state.pipeline_run_id}[/bold]"
            )
        case RunResultCompleted():
            _print_raw_results(state.result)
        case RunResultFailed():
            progress_console.print(f"[red]Run {state.pipeline_run_id} ended with status {state.status}: {state.message}[/red]")
            raise typer.Exit(1)


def _print_raw_results(results: RunResults) -> None:
    """Print the run's main content as JSON — generic, no per-example narrowing."""
    output_console.print_json(data=results.main_stuff)


if __name__ == "__main__":
    app()
