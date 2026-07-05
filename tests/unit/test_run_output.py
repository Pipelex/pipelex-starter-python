import pytest
from pipelex_sdk.errors import MissingMainStuffError
from pipelex_sdk.execute_result import PipelexExecuteResult

from my_project.run_output import to_run_results

ENTITIES_CONTENT = {"people": ["Marie Curie"], "orgs": ["University of Paris"], "dates": ["1906"]}


def _execute_result(*, main_stuff_name: str, root: dict[str, object]) -> PipelexExecuteResult:
    return PipelexExecuteResult.model_validate(
        {
            "pipeline_run_id": "run-5",
            "main_stuff_name": main_stuff_name,
            "pipe_output": {"working_memory": {"root": root, "aliases": {}}, "pipeline_run_id": "run-5"},
        }
    )


class TestRunOutput:
    def test_to_run_results_surfaces_resolved_main_stuff(self):
        # The blocking `execute` result resolves `.main_stuff` out of its working memory;
        # `to_run_results` lands it on the same `RunResults` shape the durable path returns.
        execute_result = _execute_result(
            main_stuff_name="extracted_entities",
            root={"extracted_entities": {"concept": "extract_entities.ExtractedEntities", "content": ENTITIES_CONTENT}},
        )
        results = to_run_results(execute_result)
        assert results.pipeline_run_id == "run-5"
        assert results.main_stuff == ENTITIES_CONTENT

    def test_to_run_results_raises_when_main_stuff_unlocatable(self):
        # `main_stuff_name` names a stuff absent from the working-memory root — a hard fail.
        execute_result = _execute_result(
            main_stuff_name="missing",
            root={"other": {"concept": "native.Text", "content": {}}},
        )
        with pytest.raises(MissingMainStuffError):
            to_run_results(execute_result)
