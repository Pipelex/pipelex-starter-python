"""The blocking CLI — one request, one response, done.

The simplest way to run a method: `client.execute(...)` and you have the result.
Behind the hosted gateway a run longer than ~30s is cut off (run `generate-image`
to see it happen) — that is what `piper attended` and `piper detached` are for.

Copy-paste unit: this file + `piper/inputs.py` + `piper/errors.py`. The three mode
packages never share lifecycle code, so the demo commands below are deliberate
mirrors of their `attended` / `detached` twins: only `execute_pipe()` differs.
"""

import asyncio
from pathlib import Path
from typing import Annotated, Any, Coroutine, TypeVar

import httpx
import typer
from mthds.protocol.exceptions import PipelineRequestError
from pipelex_sdk.client import PipelexAPIClient
from rich.console import Console

from piper.errors import present_error
from piper.generated.extract_entities.models import ExtractedEntities
from piper.generated.generate_image.models import Image
from piper.generated.summarize_pdf.models import DocumentSummary
from piper.inputs import SAMPLE_ENTITIES_TEXT, SAMPLE_IMAGE_PROMPT, SAMPLE_INVOICE, build_document_input, read_text_input

ResultT = TypeVar("ResultT")

METHODS_DIR = Path(__file__).parent.parent / "methods"

app = typer.Typer(no_args_is_help=True, help="Run a demo with a single blocking call (~30s cap on hosted).")

# Results go to stdout (pipeable); progress chatter goes to stderr.
output_console = Console()
progress_console = Console(stderr=True)


async def execute_pipe(*, pipe_code: str, mthds_contents: list[str], inputs: dict[str, Any]) -> Any:
    """The whole blocking lifecycle: one call, and the result comes back in the response.

    Credentials come from `PIPELEX_API_KEY` / `PIPELEX_BASE_URL`. `mthds_contents` is the
    bundle's `.mthds` files as strings — one entry for a single-file bundle, several for a
    multi-file one. The SDK resolves the method's main output for you: `.main_stuff` is
    the content the pipe named as its result (a completed run that names none raises
    `MissingMainStuffError`).
    """
    async with PipelexAPIClient() as client:
        with progress_console.status("Running…"):
            result = await client.execute(pipe_code=pipe_code, mthds_contents=mthds_contents, inputs=inputs)
    return result.main_stuff


@app.command(name="extract-entities")
def extract_entities(
    text: Annotated[str | None, typer.Argument(help="The text to extract entities from.")] = None,
    file: Annotated[Path | None, typer.Option("--file", help="Read the input text from a file instead of the argument.")] = None,
) -> None:
    """Extract people, organizations, and dates from a piece of text."""
    resolved = read_text_input(text=text, file=file, sample=SAMPLE_ENTITIES_TEXT)
    if resolved.is_sample:
        progress_console.print(f"[dim]No text given — using the sample: {resolved.text!r}. Pass your own as an argument or via --file.[/dim]")
    bundle = (METHODS_DIR / "extract-entities" / "main.mthds").read_text()
    main_stuff = _run(execute_pipe(pipe_code="extract_entities", mthds_contents=[bundle], inputs={"text": resolved.text}))
    # Narrow into the generated typed model (validates the concept's shape), then print it as JSON.
    entities = ExtractedEntities.model_validate(main_stuff)
    output_console.print_json(data=entities.model_dump())


@app.command(name="summarize-pdf")
def summarize_pdf(
    file: Annotated[Path | None, typer.Argument(help="Path to the PDF (or other document) to summarize.")] = None,
) -> None:
    """Summarize a document into a title, type, and key points."""
    document = file or SAMPLE_INVOICE
    if not document.is_file():
        msg = f"No such file: {document}"
        raise typer.BadParameter(msg)
    if file is None:
        progress_console.print(f"[dim]No file given — using the sample: {document.name}. Pass a path to summarize your own document.[/dim]")
    bundle = (METHODS_DIR / "summarize-pdf" / "main.mthds").read_text()
    inputs = {"document": build_document_input(document)}
    main_stuff = _run(execute_pipe(pipe_code="summarize_pdf", mthds_contents=[bundle], inputs=inputs))
    summary = DocumentSummary.model_validate(main_stuff)
    output_console.print_json(data=summary.model_dump())


@app.command(name="generate-image")
def generate_image(
    prompt: Annotated[str | None, typer.Argument(help="The text prompt describing the image to generate.")] = None,
    file: Annotated[Path | None, typer.Option("--file", help="Read the prompt from a file instead of the argument.")] = None,
) -> None:
    """Generate an image from a text prompt — expected to hit the hosted ~30s cap.

    Image generation routinely outlives the blocking cap, so this command is here to
    fail: it is the teaching moment for `piper attended` / `piper detached`, which run
    the very same method durably.
    """
    resolved = read_text_input(text=prompt, file=file, sample=SAMPLE_IMAGE_PROMPT)
    if resolved.is_sample:
        progress_console.print(f"[dim]No prompt given — using the sample: {resolved.text!r}. Pass your own as an argument or via --file.[/dim]")
    bundle = (METHODS_DIR / "generate-image" / "main.mthds").read_text()
    main_stuff = _run(execute_pipe(pipe_code="generate_image", mthds_contents=[bundle], inputs={"image_prompt": resolved.text}))
    # On the hosted path the runtime returns a storage `url` (`pipelex-storage://…`)
    # *and* a web-renderable `public_url` (a signed URL); the model keeps both.
    image = Image.model_validate(main_stuff)
    output_console.print_json(data=image.model_dump())


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
            progress_console.print(f"\n[yellow]Hint:[/yellow] {presentation.hint}")
        raise typer.Exit(1) from exc
    except KeyboardInterrupt as exc:
        raise typer.Exit(130) from exc


if __name__ == "__main__":
    app()
