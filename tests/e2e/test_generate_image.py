import pytest

from piper.cli import METHODS_DIR
from piper.generated.generate_image.models import Image
from piper.runner import run_durable_attended

BUNDLE_PATH = METHODS_DIR / "generate-image" / "main.mthds"

SAMPLE_PROMPT = "A watercolor painting of a fox reading a book under a tree."


@pytest.mark.inference
@pytest.mark.img_gen
@pytest.mark.pipelex_api
class TestGenerateImage:
    async def test_durable(self):
        # Image generation outlives the ~30s blocking cap, so only the durable path is exercised.
        bundle = BUNDLE_PATH.read_text()
        results = await run_durable_attended(pipe_code="generate_image", bundle=bundle, inputs={"image_prompt": SAMPLE_PROMPT})
        image = Image.model_validate(results.main_stuff)
        assert image.url
