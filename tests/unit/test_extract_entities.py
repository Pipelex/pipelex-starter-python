import pytest
from pipelex_sdk.runs import RunResults
from pydantic import ValidationError

from my_project.examples.extract_entities import parse

ENTITIES_CONTENT = {"people": ["Marie Curie", "Pierre Curie"], "orgs": ["University of Paris"], "dates": ["1906"]}


class TestExtractEntitiesParse:
    def test_parse_main_stuff_shape(self):
        results = RunResults(pipeline_run_id="run-1", main_stuff=ENTITIES_CONTENT)
        entities = parse(results)
        assert entities.people == ["Marie Curie", "Pierre Curie"]
        assert entities.orgs == ["University of Paris"]
        assert entities.dates == ["1906"]

    def test_parse_pipe_output_shape(self):
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
        entities = parse(results)
        assert entities.people == ["Marie Curie", "Pierre Curie"]

    def test_parse_shape_mismatch_raises(self):
        results = RunResults(pipeline_run_id="run-3", main_stuff={"people": "not-a-list", "orgs": [], "dates": []})
        with pytest.raises(ValidationError):
            parse(results)

    def test_parse_no_content_raises(self):
        results = RunResults(pipeline_run_id="run-4")
        with pytest.raises(RuntimeError, match="no output content"):
            parse(results)
