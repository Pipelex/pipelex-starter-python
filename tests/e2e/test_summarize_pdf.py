from pathlib import Path

import pytest

from my_project.examples.summarize_pdf import BUNDLE_PATH, PIPE_CODE, parse
from my_project.file_input import build_document_input
from my_project.runner import run_durable_attended

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
