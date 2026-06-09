import pytest
from pipelex.pipe_run.exceptions import DryRunError
from pipelex.pipeline.bundle_validator import BundleValidator


# We use gha_disabled here because those tests are called directly and explicitly by the tests-check.yml file before the rest of the tests.
@pytest.mark.gha_disabled
class TestFundamentals:
    def test_boot(self):
        # This test does nothing but the conftest runs Pipelex.make()
        # Therefore this test will fail if Pipelex.make() fails.
        pass

    @pytest.mark.asyncio(loop_scope="class")
    async def test_dry_run_all_pipes(self):
        # acquire_and_validate opens a fresh library, loads my_project, dry-runs every pipe, and tears
        # the library down. It raises DryRunError aggregating any unexpected pipe failures.
        try:
            await BundleValidator().acquire_and_validate(library_dirs=["my_project"])
        except DryRunError as dry_run_error:
            pytest.fail(str(dry_run_error))
