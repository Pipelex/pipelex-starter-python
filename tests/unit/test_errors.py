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


def _http_status_error(status_code: int) -> httpx.HTTPStatusError:
    request = httpx.Request("POST", "https://api.pipelex.com/v1/execute")
    response = httpx.Response(status_code, request=request)
    return httpx.HTTPStatusError("boom", request=request, response=response)


class TestPresentError:
    def test_execute_timeout_hints_durable(self):
        presentation = present_error(PipelineExecuteTimeoutError("timed out", elapsed_seconds=31.2))
        assert "~30s" in presentation.message
        assert presentation.hint is not None
        assert "--mode durable" in presentation.hint

    def test_lifecycle_unavailable_hints_blocking(self):
        presentation = present_error(RunLifecycleUnavailableError("no run store", api_url="http://localhost:8000"))
        assert "http://localhost:8000" in presentation.message
        assert presentation.hint is not None
        assert "--mode blocking" in presentation.hint

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

    def test_unreachable_hints_base_url(self):
        presentation = present_error(ApiUnreachableError("connect failed", api_url="http://nowhere.invalid"))
        assert "http://nowhere.invalid" in presentation.message
        assert presentation.hint is not None
        assert "PIPELEX_BASE_URL" in presentation.hint

    def test_run_failed_names_run_id(self):
        presentation = present_error(RunFailedError("run failed", run_id="run-9", status=RunStatus.FAILED))
        assert "run-9" in presentation.message
        assert presentation.hint is not None
        assert "runs status run-9" in presentation.hint

    def test_run_timeout_hints_wait(self):
        presentation = present_error(RunTimeoutError("too slow", run_id="run-9", timeout_seconds=1200.0))
        assert presentation.hint is not None
        assert "runs wait run-9" in presentation.hint
