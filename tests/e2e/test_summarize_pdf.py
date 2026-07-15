from pathlib import Path

import pytest

from piper.attended.cli import METHODS_DIR, start_and_wait
from piper.generated.summarize_pdf.models import DocumentSummary
from piper.inputs import build_document_input

BUNDLE_PATH = METHODS_DIR / "summarize-pdf" / "main.mthds"

SAMPLE_PDF = Path(__file__).parents[2] / "samples" / "sample-invoice.pdf"


@pytest.mark.inference
@pytest.mark.llm
@pytest.mark.pipelex_api
class TestSummarizePdf:
    async def test_attended(self):
        # The attended lifecycle end to end: encode the PDF, start a durable run, poll it, narrow.
        bundle = BUNDLE_PATH.read_text()
        inputs = {"document": build_document_input(SAMPLE_PDF)}
        main_stuff = await start_and_wait(pipe_code="summarize_pdf", mthds_contents=[bundle], inputs=inputs)
        summary = DocumentSummary.model_validate(main_stuff)
        assert summary.title
        assert summary.doc_type
        assert summary.key_points
