"""Example: extract people, organizations, and dates from a piece of text.

This module is the "copy me" unit for swapping in your own pipeline: a bundle
path, a Pydantic model mirroring the output concept, and a `parse` narrower
that turns the loose run result into that model. The CLI prints the parsed
model as JSON — same rendering as `runs result` / `runs wait`.
"""

from pathlib import Path

from pipelex_sdk.runs import RunResults
from pydantic import BaseModel

BUNDLE_PATH = Path(__file__).parent.parent / "methods" / "extract-entities" / "main.mthds"
PIPE_CODE = "extract_entities"


class ExtractedEntities(BaseModel):
    """Mirror of the bundle's `ExtractedEntities` output concept."""

    people: list[str]
    orgs: list[str]
    dates: list[str]


def parse(results: RunResults) -> ExtractedEntities:
    """Narrow a run result into a typed `ExtractedEntities`.

    The SDK guarantees a resolved `results.main_stuff` for a completed run (it raises
    `MissingMainStuffError` upstream otherwise), so this only validates the shape.

    Raises:
        pydantic.ValidationError: The content doesn't match the concept's shape.
    """
    return ExtractedEntities.model_validate(results.main_stuff)
