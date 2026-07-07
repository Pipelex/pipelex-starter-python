from pathlib import Path

import pytest

from piper.examples.summarize_pdf import BUNDLE_PATH, PIPE_CODE, parse
from piper.file_input import build_document_input
from piper.runner import run_durable_attended

SAMPLE_PDF = Path(__file__).parents[2] / "samples" / "sample-invoice.pdf"


@pytest.mark.inference
@pytest.mark.llm
@pytest.mark.pipelex_api
class TestSummarizePdf:
    async def test_durable(self):
        # Full durable lifecycle through the hosted API: encode the PDF, start + poll + narrow.
        bundle = BUNDLE_PATH.read_text()
        inputs = {"document": build_document_input(SAMPLE_PDF)}
        results = await run_durable_attended(pipe_code=PIPE_CODE, bundle=bundle, inputs=inputs)
        summary = parse(results)
        assert summary.title
        assert summary.doc_type
        assert summary.key_points
