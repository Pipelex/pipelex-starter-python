import pytest

from piper.cli import METHODS_DIR
from piper.generated.extract_entities.models import ExtractedEntities
from piper.runner import run_blocking, run_durable_attended

BUNDLE_PATH = METHODS_DIR / "extract-entities" / "main.mthds"

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
        results = await run_durable_attended(pipe_code="extract_entities", bundle=bundle, inputs={"text": SAMPLE_TEXT})
        entities = ExtractedEntities.model_validate(results.main_stuff)
        assert any("Curie" in person for person in entities.people)

    async def test_blocking(self):
        # Blocking `execute` path (extraction is fast enough for the ~30s cap).
        bundle = BUNDLE_PATH.read_text()
        results = await run_blocking(pipe_code="extract_entities", bundle=bundle, inputs={"text": SAMPLE_TEXT})
        entities = ExtractedEntities.model_validate(results.main_stuff)
        assert any("Curie" in person for person in entities.people)
