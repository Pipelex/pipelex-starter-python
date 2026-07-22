import io
from typing import Any

from pipelex_sdk.execute_result import PipelexExecuteResult
from pipelex_sdk.runs import RunResults, TokensUsageRecord
from rich.console import Console

from piper.usage import RunUsage, print_cost_report, usage_from_execute, usage_from_results


def _render(usage: RunUsage) -> str:
    buffer = io.StringIO()
    # A wide, non-terminal console → plain text, no wrapping, no ANSI styling to assert around.
    print_cost_report(Console(file=buffer, width=200), usage)
    return buffer.getvalue()


def _record(**fields: Any) -> TokensUsageRecord:
    return TokensUsageRecord.model_validate(fields)


class TestUsage:
    def test_reports_records_with_a_total(self):
        usage = RunUsage(
            tokens_usages=[
                _record(pipe_code="extract", inference_model_name="gpt-4o", cost=0.01, nb_tokens_by_category={"input": 100, "output": 50}),
                _record(pipe_code="summarize", inference_model_name="claude", cost=0.02, nb_tokens_by_category={"input": 200, "output": 80}),
            ],
            usage_assembly_error=None,
        )
        output = _render(usage)
        assert "gpt-4o" in output
        assert "claude" in output
        assert "100→50" in output  # the joined `input` total → `output`, never a sum of categories
        assert "$0.0300" in output  # 0.01 + 0.02

    def test_marks_unpriced_calls_and_excludes_them_from_the_total(self):
        usage = RunUsage(
            tokens_usages=[
                _record(pipe_code="gen", model_type="img_gen", cost=None, nb_tokens_by_category=None),
                _record(pipe_code="extract", inference_model_name="gpt-4o", cost=0.05, nb_tokens_by_category={"input": 10, "output": 5}),
            ],
            usage_assembly_error=None,
        )
        output = _render(usage)
        assert "$0.0500" in output  # the total excludes the unpriced (cost is None) call
        assert "unpriced" in output

    def test_assembly_error_is_reported(self):
        output = _render(RunUsage(tokens_usages=None, usage_assembly_error="event read failed"))
        assert "event read failed" in output
        assert "failed" in output.lower()

    def test_none_usage_says_nothing_reported(self):
        # None (off / pre-artifact) is distinct from the assembly-error case above.
        output = _render(RunUsage(tokens_usages=None, usage_assembly_error=None))
        assert "No usage was reported" in output

    def test_empty_usage_says_no_inference(self):
        # [] (ran, but no inference happened) is distinct from None.
        output = _render(RunUsage(tokens_usages=[], usage_assembly_error=None))
        assert "No inference calls" in output

    def test_usage_from_results_passes_the_pair_through(self):
        records = [_record(pipe_code="p", cost=0.01)]
        results = RunResults(pipeline_run_id="run-1", main_stuff={"x": 1}, tokens_usages=records, usage_assembly_error=None)
        usage = usage_from_results(results)
        assert usage.tokens_usages == records
        assert usage.usage_assembly_error is None

    def test_usage_from_execute_lifts_raw_records_off_pipe_output(self):
        result = PipelexExecuteResult.model_validate(
            {
                "pipeline_run_id": "run-1",
                "main_stuff_name": "out",
                "pipe_output": {
                    "pipeline_run_id": "run-1",
                    "working_memory": {"root": {}, "aliases": {}},
                    "tokens_usages": [{"pipe_code": "p", "inference_model_name": "gpt-4o", "cost": 0.01}],
                    "usage_assembly_error": None,
                },
            }
        )
        usage = usage_from_execute(result)
        assert usage.tokens_usages is not None
        assert usage.tokens_usages[0].pipe_code == "p"
        assert usage.tokens_usages[0].cost == 0.01

    def test_usage_from_execute_handles_a_response_without_usage(self):
        result = PipelexExecuteResult.model_validate(
            {
                "pipeline_run_id": "run-1",
                "main_stuff_name": "out",
                "pipe_output": {"pipeline_run_id": "run-1", "working_memory": {"root": {}, "aliases": {}}},
            }
        )
        usage = usage_from_execute(result)
        assert usage.tokens_usages is None
        assert usage.usage_assembly_error is None
