"""Normalize the Pipelex API's run-output shapes into plain content dicts.

The API returns one of two opaque JSON shapes depending on the path taken:
hosted durable runs carry `main_stuff` (the main output's content directly),
while the blocking / bare-runner path carries `pipe_output` (a serialized
working memory). Everything downstream (the per-example `parse` functions)
goes through `find_main_content` so it never has to care which path ran.
"""

from typing import Any, cast

from mthds.runners.api.models import DictRunResultExecute
from pipelex_sdk.runs import RunResults


def find_main_content(results: RunResults) -> dict[str, Any] | None:
    """Read the main output's content dict out of a run result.

    The Pipelex API returns one of two shapes (both opaque JSON), so we
    normalize both here:
    - Hosted runs carry `main_stuff` — the main output's content directly
      (e.g. `{"people": [...], "orgs": [...], "dates": [...]}`).
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


def to_run_results(result: DictRunResultExecute) -> RunResults:
    """Normalize a blocking `execute` response into the lifecycle's `RunResults`.

    The blocking path returns the runner's native shape (`pipe_output`); the
    hosted-durable artifacts (`main_stuff`, `graph_spec`) don't exist on that
    path and stay `None`. This mirrors what the SDK's `start_and_wait` does
    internally, so both execution modes hand the same type to `find_main_content`.
    """
    return RunResults(
        pipeline_run_id=result.pipeline_run_id,
        main_stuff=None,
        graph_spec=None,
        pipe_output=result.pipe_output.model_dump(),
    )
