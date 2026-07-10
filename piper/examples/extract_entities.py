"""Example: extract people, organizations, and dates from a piece of text.

This module is the "copy me" unit for swapping in your own pipeline: a bundle
path, a *generated* Pydantic model of the output concept, and a `parse` narrower
that turns the loose run result into that model. Nothing method-shaped is
hand-written — `ExtractedEntities` is generated from the `.mthds` bundle by
`pipelex codegen` (see `piper/generated/`, regenerate with `make codegen`).
The CLI prints the parsed model as JSON — same rendering as `runs result` /
`runs wait`.
"""

from pathlib import Path

from pipelex_sdk.runs import RunResults

from piper.generated.extract_entities.models import ExtractedEntities

BUNDLE_PATH = Path(__file__).parent.parent / "methods" / "extract-entities" / "main.mthds"
PIPE_CODE = "extract_entities"


def parse(results: RunResults) -> ExtractedEntities:
    """Narrow a run result into the generated `ExtractedEntities` model.

    The SDK guarantees a resolved `results.main_stuff` for a completed run (it raises
    `MissingMainStuffError` upstream otherwise), so this only validates the shape.

    Raises:
        pydantic.ValidationError: The content doesn't match the concept's shape.
    """
    return ExtractedEntities.model_validate(results.main_stuff)
