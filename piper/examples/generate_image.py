"""Example: generate an image from a text prompt.

The third "copy me" unit — and the one that best demonstrates the durable vs
blocking split. Image generation routinely outlives the hosted gateway's ~30s
synchronous cap, so running it with `--mode blocking` is how you actually see a
`PipelineExecuteTimeoutError`; `--mode durable` (the default) survives it.

The output concept is the built-in `Image`, and even that is not hand-written:
the `Image` model is generated from the bundle by `pipelex codegen` (natives are
materialized into the generated client — see `piper/generated/`). On the hosted
path the runtime returns a storage `url` (`pipelex-storage://…`) *and* a
web-renderable `public_url` (a signed URL); the parsed model keeps both.
"""

from pathlib import Path

from pipelex_sdk.runs import RunResults

from piper.generated.generate_image.models import Image

BUNDLE_PATH = Path(__file__).parent.parent / "methods" / "generate-image" / "main.mthds"
PIPE_CODE = "generate_image"


def parse(results: RunResults) -> Image:
    """Narrow a run result into the generated `Image` model.

    The SDK guarantees a resolved `results.main_stuff` for a completed run (it raises
    `MissingMainStuffError` upstream otherwise), so this only validates the shape.

    Raises:
        pydantic.ValidationError: The content carries no image `url`.
    """
    return Image.model_validate(results.main_stuff)
