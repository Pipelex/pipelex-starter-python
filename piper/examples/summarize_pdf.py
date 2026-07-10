"""Example: summarize a PDF document into a title, type, and key points.

Like `extract_entities`, this is a "copy me" unit: a bundle path, a *generated*
Pydantic model of the output concept (`DocumentSummary`, generated from the
bundle by `pipelex codegen` — see `piper/generated/`), and a `parse` narrower.
What it adds is a *file* input — the CLI passes a `Document` envelope built by
`piper.file_input.build_document_input`, so this is the example that shows
how to feed a PDF (or any document) to a pipe.
"""

from pathlib import Path

from pipelex_sdk.runs import RunResults

from piper.generated.summarize_pdf.models import DocumentSummary

BUNDLE_PATH = Path(__file__).parent.parent / "methods" / "summarize-pdf" / "main.mthds"
PIPE_CODE = "summarize_pdf"


def parse(results: RunResults) -> DocumentSummary:
    """Narrow a run result into the generated `DocumentSummary` model.

    The SDK guarantees a resolved `results.main_stuff` for a completed run (it raises
    `MissingMainStuffError` upstream otherwise), so this only validates the shape.

    Raises:
        pydantic.ValidationError: The content doesn't match the concept's shape.
    """
    return DocumentSummary.model_validate(results.main_stuff)
