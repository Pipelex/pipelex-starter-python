import pytest

from piper.examples.extract_entities import BUNDLE_PATH, PIPE_CODE, parse
from piper.runner import run_blocking, run_durable_attended

SAMPLE_TEXT = (
    "Marie Curie joined the University of Paris in 1906, two years after Pierre Curie won recognition from the Royal Swedish Academy of Sciences."
)


@pytest.mark.inference
@pytest.mark.llm
@pytest.mark.pipelex_api
class TestExtractEntities:
    async def test_durable(self):
        # Full durable lifecycle through the hosted API: start + poll + narrow.
        bundle = BUNDLE_PATH.read_text()
        results = await run_durable_attended(pipe_code=PIPE_CODE, bundle=bundle, inputs={"text": SAMPLE_TEXT})
        entities = parse(results)
        assert any("Curie" in person for person in entities.people)

    async def test_blocking(self):
        # Blocking `execute` path (extraction is fast enough for the ~30s cap).
        bundle = BUNDLE_PATH.read_text()
        results = await run_blocking(pipe_code=PIPE_CODE, bundle=bundle, inputs={"text": SAMPLE_TEXT})
        entities = parse(results)
        assert any("Curie" in person for person in entities.people)
