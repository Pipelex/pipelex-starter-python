"""Example: extract people, organizations, and dates from a piece of text.

This module is the "copy me" unit for swapping in your own pipeline: a bundle
path, a Pydantic model mirroring the output concept, and a `parse` narrower
that turns the loose run result into that model. The CLI prints the parsed
model as JSON — same rendering as `runs result` / `runs wait`.
"""

from pathlib import Path

from pipelex_sdk.runs import RunResults
from pydantic import BaseModel

from my_project.run_output import find_main_content

BUNDLE_PATH = Path(__file__).parent.parent / "methods" / "extract-entities" / "main.mthds"
PIPE_CODE = "extract_entities"


class ExtractedEntities(BaseModel):
    """Mirror of the bundle's `ExtractedEntities` output concept."""

    people: list[str]
    orgs: list[str]
    dates: list[str]


def parse(results: RunResults) -> ExtractedEntities:
    """Narrow a run result into a typed `ExtractedEntities`.

    Raises:
        RuntimeError: The run produced no output content at all.
        pydantic.ValidationError: The content doesn't match the concept's shape.
    """
    content = find_main_content(results)
    if content is None:
        msg = "The run returned no output content."
        raise RuntimeError(msg)
    return ExtractedEntities.model_validate(content)
