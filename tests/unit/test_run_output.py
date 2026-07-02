from mthds.runners.api.models import DictPipeOutputAbstract, DictRunResultExecute, DictStuffAbstract, DictWorkingMemoryAbstract
from pipelex_sdk.runs import RunResults

from my_project.run_output import find_main_content, to_run_results

ENTITIES_CONTENT = {"people": ["Marie Curie"], "orgs": ["University of Paris"], "dates": ["1906"]}


class TestRunOutput:
    def test_main_stuff_shape(self):
        # Hosted durable runs: main_stuff carries the content directly.
        results = RunResults(pipeline_run_id="run-1", main_stuff=ENTITIES_CONTENT)
        assert find_main_content(results) == ENTITIES_CONTENT

    def test_pipe_output_shape(self):
        # Bare-runner / blocking fallback: content sits inside the working memory root.
        results = RunResults(
            pipeline_run_id="run-2",
            pipe_output={
                "working_memory": {
                    "root": {"extracted_entities": {"concept": "extract_entities.ExtractedEntities", "content": ENTITIES_CONTENT}},
                    "aliases": {},
                },
                "pipeline_run_id": "run-2",
            },
        )
        assert find_main_content(results) == ENTITIES_CONTENT

    def test_no_content_returns_none(self):
        results = RunResults(pipeline_run_id="run-3")
        assert find_main_content(results) is None

    def test_malformed_pipe_output_returns_none(self):
        results = RunResults(pipeline_run_id="run-4", pipe_output={"working_memory": {"root": {"bad": "not-a-dict"}, "aliases": {}}})
        assert find_main_content(results) is None

    def test_to_run_results_normalizes_execute_response(self):
        # The blocking `execute` response must land in the same RunResults shape
        # the durable path returns, so find_main_content works on both.
        execute_result = DictRunResultExecute(
            pipeline_run_id="run-5",
            pipe_output=DictPipeOutputAbstract(
                working_memory=DictWorkingMemoryAbstract(
                    root={"extracted_entities": DictStuffAbstract(concept="extract_entities.ExtractedEntities", content=ENTITIES_CONTENT)},
                    aliases={},
                ),
                pipeline_run_id="run-5",
            ),
        )
        results = to_run_results(execute_result)
        assert results.pipeline_run_id == "run-5"
        assert results.main_stuff is None
        assert find_main_content(results) == ENTITIES_CONTENT
