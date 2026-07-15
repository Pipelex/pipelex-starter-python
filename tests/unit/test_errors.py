from collections.abc import Mapping

import httpx
from pipelex_sdk.errors import (
    ApiUnreachableError,
    PipelineExecuteTimeoutError,
    RunFailedError,
    RunLifecycleUnavailableError,
    RunTimeoutError,
)
from pipelex_sdk.runs import RunStatus

from piper.errors import present_error


def _http_status_error(status_code: int, *, problem: Mapping[str, object] | None = None) -> httpx.HTTPStatusError:
    request = httpx.Request("POST", "https://api.pipelex.com/v1/start")
    response = httpx.Response(status_code, request=request, json=problem) if problem is not None else httpx.Response(status_code, request=request)
    return httpx.HTTPStatusError("boom", request=request, response=response)


class TestPresentError:
    def test_execute_timeout_hints_attended(self):
        presentation = present_error(PipelineExecuteTimeoutError("timed out", elapsed_seconds=31.2))
        assert "~30s" in presentation.message
        assert presentation.hint is not None
        assert "piper attended" in presentation.hint

    def test_lifecycle_unavailable_hints_blocking(self):
        presentation = present_error(RunLifecycleUnavailableError("no run store", api_url="http://localhost:8000"))
        assert "http://localhost:8000" in presentation.message
        assert presentation.hint is not None
        assert "piper blocking" in presentation.hint

    def test_http_auth_error_hints_api_key(self):
        # The protocol routes (execute/start/runs) raise raw httpx.HTTPStatusError,
        # not ApiResponseError — an auth failure must still get the key hint.
        for status_code in (401, 403):
            presentation = present_error(_http_status_error(status_code))
            assert str(status_code) in presentation.message
            assert presentation.hint is not None
            assert "PIPELEX_API_KEY" in presentation.hint

    def test_http_server_error_has_no_hint(self):
        presentation = present_error(_http_status_error(500))
        assert presentation.hint is None

    def test_start_without_async_orchestration_hints_blocking(self):
        # A synchronous-only runner rejects /start with this RFC 7807 error_type;
        # the fix is to run the same demo under `piper blocking`.
        problem = {
            "error_type": "StartRequiresAsyncOrchestration",
            "detail": "Orchestration mode 'direct' cannot honor fire-and-forget delivery. Use /execute instead.",
            "status": 400,
        }
        presentation = present_error(_http_status_error(400, problem=problem))
        assert "Orchestration mode 'direct'" in presentation.message
        assert presentation.hint is not None
        assert "piper blocking" in presentation.hint

    def test_http_error_surfaces_the_problem_detail(self):
        problem = {"title": "Bad input", "detail": "Missing required input 'text'.", "status": 400}
        presentation = present_error(_http_status_error(400, problem=problem))
        assert "Missing required input 'text'." in presentation.message
        assert presentation.hint is None

    def test_unreachable_hints_base_url(self):
        presentation = present_error(ApiUnreachableError("connect failed", api_url="http://nowhere.invalid"))
        assert "http://nowhere.invalid" in presentation.message
        assert presentation.hint is not None
        assert "PIPELEX_BASE_URL" in presentation.hint

    def test_run_failed_names_run_id(self):
        presentation = present_error(RunFailedError("run failed", run_id="run-9", status=RunStatus.FAILED))
        assert "run-9" in presentation.message
        assert presentation.hint is not None
        assert "piper detached status run-9" in presentation.hint

    def test_run_timeout_hints_wait(self):
        presentation = present_error(RunTimeoutError("too slow", run_id="run-9", timeout_seconds=1200.0))
        assert presentation.hint is not None
        assert "piper detached wait run-9" in presentation.hint
