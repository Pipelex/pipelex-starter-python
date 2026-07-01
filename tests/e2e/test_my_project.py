import pytest

from my_project.hello_world import hello_world


@pytest.mark.inference
@pytest.mark.pipelex_api
class TestMyProject:
    async def test_hello_world(self):
        # Runs the pipeline end-to-end through the hosted Pipelex API (real inference).
        await hello_world()
