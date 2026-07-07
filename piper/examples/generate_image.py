"""Example: generate an image from a text prompt.

The third "copy me" unit — and the one that best demonstrates the durable vs
blocking split. Image generation routinely outlives the hosted gateway's ~30s
synchronous cap, so running it with `--mode blocking` is how you actually see a
`PipelineExecuteTimeoutError`; `--mode durable` (the default) survives it.

The output concept is the built-in `Image`, so `main_stuff` is an image content
dict — a `url` plus optional `public_url` / `mime_type` / `caption`. On the
hosted path the runtime returns a storage `url` (`pipelex-storage://…`) *and* a
web-renderable `public_url` (a signed URL); `parse` keeps both.
"""

from pathlib import Path

from pipelex_sdk.runs import RunResults
from pydantic import BaseModel

BUNDLE_PATH = Path(__file__).parent.parent / "methods" / "generate-image" / "main.mthds"
PIPE_CODE = "generate_image"


class GeneratedImage(BaseModel):
    """Mirror of the bundle's built-in `Image` output content."""

    url: str
    public_url: str | None = None
    mime_type: str | None = None
    caption: str | None = None


def parse(results: RunResults) -> GeneratedImage:
    """Narrow a run result into a typed `GeneratedImage`.

    The SDK guarantees a resolved `results.main_stuff` for a completed run (it raises
    `MissingMainStuffError` upstream otherwise), so this only validates the shape.

    Raises:
        pydantic.ValidationError: The content carries no image `url`.
    """
    return GeneratedImage.model_validate(results.main_stuff)
