import pytest
from pipelex_sdk.client import PipelexAPIClient

from my_project.examples.extract_entities import BUNDLE_PATH


class TestFundamentals:
    def test_boot(self):
        # Constructing the client resolves credentials + base URL (no network).
        # This fails if PIPELEX_BASE_URL is malformed.
        client = PipelexAPIClient()
        assert client.base_url

    def test_bundle_exists(self):
        assert BUNDLE_PATH.exists()
        assert BUNDLE_PATH.read_text().strip()

    @pytest.mark.pipelex_api
    async def test_validate_bundle(self):
        # Parse, validate, and dry-run the bundle through the hosted API.
        # The verdict rides a 200 body (never raised); assert it is valid.
        bundle = BUNDLE_PATH.read_text()
        async with PipelexAPIClient() as client:
            report = await client.validate([bundle])
        assert report.is_valid, report.rendered_markdown
