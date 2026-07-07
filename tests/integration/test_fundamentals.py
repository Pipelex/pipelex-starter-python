from pathlib import Path

import pytest
from pipelex_sdk.client import PipelexAPIClient

from piper.examples.extract_entities import BUNDLE_PATH as EXTRACT_ENTITIES_BUNDLE
from piper.examples.generate_image import BUNDLE_PATH as GENERATE_IMAGE_BUNDLE
from piper.examples.summarize_pdf import BUNDLE_PATH as SUMMARIZE_PDF_BUNDLE

BUNDLE_PATHS = [EXTRACT_ENTITIES_BUNDLE, SUMMARIZE_PDF_BUNDLE, GENERATE_IMAGE_BUNDLE]


class TestFundamentals:
    def test_boot(self):
        # Constructing the client resolves credentials + base URL (no network).
        # This fails if PIPELEX_BASE_URL is malformed.
        client = PipelexAPIClient()
        assert client.base_url

    @pytest.mark.parametrize("bundle_path", BUNDLE_PATHS)
    def test_bundle_exists(self, bundle_path: Path):
        assert bundle_path.exists()
        assert bundle_path.read_text().strip()

    @pytest.mark.pipelex_api
    @pytest.mark.parametrize("bundle_path", BUNDLE_PATHS)
    async def test_validate_bundle(self, bundle_path: Path):
        # Parse, validate, and dry-run the bundle through the hosted API.
        # The verdict rides a 200 body (never raised); assert it is valid.
        bundle = bundle_path.read_text()
        async with PipelexAPIClient() as client:
            report = await client.validate([bundle])
        assert report.is_valid, report.rendered_markdown
