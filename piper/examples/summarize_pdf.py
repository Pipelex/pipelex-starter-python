"""Example: summarize a PDF document into a title, type, and key points.

Like `extract_entities`, this is a "copy me" unit: a bundle path, a Pydantic
model mirroring the output concept, and a `parse` narrower. What it adds is a
*file* input — the CLI passes a `Document` envelope built by
`piper.file_input.build_document_input`, so this is the example that shows
how to feed a PDF (or any document) to a pipe.
"""

from pathlib import Path

from pipelex_sdk.runs import RunResults
from pydantic import BaseModel

BUNDLE_PATH = Path(__file__).parent.parent / "methods" / "summarize-pdf" / "main.mthds"
PIPE_CODE = "summarize_pdf"


class DocumentSummary(BaseModel):
    """Mirror of the bundle's `DocumentSummary` output concept."""

    title: str
    doc_type: str
    key_points: list[str]


def parse(results: RunResults) -> DocumentSummary:
    """Narrow a run result into a typed `DocumentSummary`.

    The SDK guarantees a resolved `results.main_stuff` for a completed run (it raises
    `MissingMainStuffError` upstream otherwise), so this only validates the shape.

    Raises:
        pydantic.ValidationError: The content doesn't match the concept's shape.
    """
    return DocumentSummary.model_validate(results.main_stuff)
