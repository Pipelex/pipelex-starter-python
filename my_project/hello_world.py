import asyncio
from pathlib import Path
from typing import Any, cast

from dotenv import load_dotenv
from pipelex_sdk.client import PipelexAPIClient
from pipelex_sdk.runs import RunResults

# The .mthds bundle lives next to this module.
BUNDLE_PATH = Path(__file__).parent / "hello_world.mthds"


def find_main_content(results: RunResults) -> dict[str, Any] | None:
    """Read the main output's content dict out of a run result.

    The Pipelex API returns one of two shapes (both opaque JSON), so we
    normalize both here:
    - Hosted runs carry `main_stuff` — the main output's content directly
      (for our `hello_world` pipe: `{"text": "..."}`).
    - The bare-runner blocking fallback carries `pipe_output`
      (`{"working_memory": {"root": {<name>: {"content": ...}}}}`); we return
      the first entry's content.
    """
    main_stuff: Any = results.main_stuff
    if isinstance(main_stuff, dict):
        return cast("dict[str, Any]", main_stuff)

    pipe_output = results.pipe_output
    if pipe_output is None:
        return None
    working_memory = pipe_output.get("working_memory")
    if not isinstance(working_memory, dict):
        return None
    root = cast("dict[str, Any]", working_memory).get("root")
    if not isinstance(root, dict):
        return None
    for entry in cast("dict[str, Any]", root).values():
        if not isinstance(entry, dict):
            continue
        content = cast("dict[str, Any]", entry).get("content")
        if isinstance(content, dict):
            return cast("dict[str, Any]", content)
    return None


async def hello_world() -> None:
    """Run a super-simple Pipelex pipeline through the hosted Pipelex API and print its output.

    The `PipelexAPIClient` reads `PIPELEX_API_URL` / `PIPELEX_API_KEY` from the
    environment. `start_and_wait` submits the run and polls it to completion — the
    durable path that survives the hosted gateway's ~30s synchronous cap, and
    self-heals to a blocking `execute` against a bare self-hosted runner.
    """
    bundle = BUNDLE_PATH.read_text()

    async with PipelexAPIClient() as client:
        results = await client.start_and_wait(
            pipe_code="hello_world",
            mthds_contents=[bundle],
        )

    content = find_main_content(results)
    if content is None:
        raise RuntimeError("The pipeline returned no output content.")

    print("Your first Pipelex output:\n")
    print(content.get("text"))


if __name__ == "__main__":
    # Load .env so PIPELEX_API_URL / PIPELEX_API_KEY are available when run directly.
    load_dotenv()
    asyncio.run(hello_world())
