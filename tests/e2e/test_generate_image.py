import pytest

from piper.examples.generate_image import BUNDLE_PATH, PIPE_CODE, parse
from piper.runner import run_durable_attended

SAMPLE_PROMPT = "A watercolor painting of a fox reading a book under a tree."


@pytest.mark.inference
@pytest.mark.img_gen
@pytest.mark.pipelex_api
class TestGenerateImage:
    async def test_durable(self):
        # Image generation outlives the ~30s blocking cap, so only the durable path is exercised.
        bundle = BUNDLE_PATH.read_text()
        results = await run_durable_attended(pipe_code=PIPE_CODE, bundle=bundle, inputs={"image_prompt": SAMPLE_PROMPT})
        image = parse(results)
        assert image.url
