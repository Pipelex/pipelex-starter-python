import pytest
from pipelex_sdk.runs import RunResults
from pydantic import ValidationError

from my_project.examples.summarize_pdf import parse

SUMMARY_CONTENT = {
    "title": "Q3 Financial Report",
    "doc_type": "report",
    "key_points": ["Revenue grew 12%", "Costs held flat", "Cash runway extended to 2028"],
}


class TestSummarizePdfParse:
    def test_parse_main_stuff(self):
        results = RunResults(pipeline_run_id="run-1", main_stuff=SUMMARY_CONTENT)
        summary = parse(results)
        assert summary.title == "Q3 Financial Report"
        assert summary.doc_type == "report"
        assert summary.key_points == ["Revenue grew 12%", "Costs held flat", "Cash runway extended to 2028"]

    def test_parse_shape_mismatch_raises(self):
        results = RunResults(pipeline_run_id="run-2", main_stuff={"title": "x", "doc_type": "y", "key_points": "not-a-list"})
        with pytest.raises(ValidationError):
            parse(results)
