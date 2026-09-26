import io
from collections.abc import Mapping

import httpx
import pytest
from pipelex_sdk.artifact_models import ArtifactScope, DownloadArtifactsResult
from pipelex_sdk.error_models import RunErrorReport, UserAction
from pipelex_sdk.errors import (
    ApiUnreachableError,
    ArtifactAuthenticationError,
    ArtifactOperationError,
    InvalidLocalSourceError,
    PipelineExecuteTimeoutError,
    RejectedAssetError,
    RunFailedError,
    RunLifecycleUnavailableError,
    RunTimeoutError,
    UnsupportedUploadCapabilityError,
    UploadAuthenticationError,
)
from pipelex_sdk.runs import RunStatus
from rich.console import Console

from widget.errors import ErrorPresentation, present_error, print_error, report_lines

# A failed run's stored report as the runner writes it for an inference failure, and the platform's
# sentence about the run with and without one (`Run finished with status <STATUS>: <message>`).
MODEL_REPORT = RunErrorReport(
    error_type="LLMCompletionError",
    title="LLM completion",
    message="The model refused the request.",
    error_domain="runtime",
    retryable=True,
    user_action=UserAction(kind="change_input", detail="Rephrase the prompt, or pick another model."),
)
REPORTED_DETAIL = "Run finished with status FAILED: The model refused the request."
UNREPORTED_DETAIL = "Run finished with status FAILED; no result available"


def _http_status_error(status_code: int, *, problem: Mapping[str, object] | None = None) -> httpx.HTTPStatusError:
    request = httpx.Request("POST", "https://api.pipelex.com/v1/start")
    response = httpx.Response(status_code, request=request, json=problem) if problem is not None else httpx.Response(status_code, request=request)
    return httpx.HTTPStatusError("boom", request=request, response=response)


class TestPresentError:
    def test_execute_timeout_hints_attended(self):
        presentation = present_error(PipelineExecuteTimeoutError("timed out", elapsed_seconds=31.2))
        assert "~30s" in presentation.message
        assert presentation.hint is not None
        assert "widget attended" in presentation.hint

    def test_lifecycle_unavailable_hints_blocking(self):
        presentation = present_error(RunLifecycleUnavailableError("no run store", api_url="http://localhost:8000"))
        assert "http://localhost:8000" in presentation.message
        assert presentation.hint is not None
        assert "widget blocking" in presentation.hint

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
        # the fix is to run the same demo under `widget blocking`.
        problem = {
            "error_type": "StartRequiresAsyncOrchestration",
            "detail": "Orchestration mode 'direct' cannot honor fire-and-forget delivery. Use /execute instead.",
            "status": 400,
        }
        presentation = present_error(_http_status_error(400, problem=problem))
        assert "Orchestration mode 'direct'" in presentation.message
        assert presentation.hint is not None
        assert "widget blocking" in presentation.hint

    def test_http_error_with_undecodable_body_falls_back_to_status(self):
        # A non-UTF-8 body makes `response.json()` raise UnicodeDecodeError (not
        # JSONDecodeError); the best-effort problem+json parse must still fall
        # back to the status-only message instead of crashing mid-presentation.
        request = httpx.Request("POST", "https://api.pipelex.com/v1/start")
        response = httpx.Response(400, request=request, headers={"content-type": "application/problem+json"}, content=b"\xffnot-json")
        presentation = present_error(httpx.HTTPStatusError("boom", request=request, response=response))
        assert presentation.message == "The API answered 400 Bad Request."
        assert presentation.hint is None

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

    def test_run_failed_reads_out_the_stored_report(self):
        presentation = present_error(RunFailedError(REPORTED_DETAIL, run_id="run-9", status=RunStatus.FAILED, error=MODEL_REPORT))
        assert presentation.message == "Run run-9 failed."
        assert presentation.details == (
            "Reason: LLM completion — The model refused the request.",
            "Next step: Rephrase the prompt, or pick another model.",
            "Retry: running it again may succeed.",
        )
        # The next step is the advice, so no hint sends the reader to a command that prints the same lines again.
        assert presentation.hint is None

    def test_run_failed_without_a_stored_report_still_says_what_happened(self):
        presentation = present_error(RunFailedError(UNREPORTED_DETAIL, run_id="run-9", status=RunStatus.FAILED))
        assert presentation.message == "Run run-9 failed, and no reason was recorded for it."
        # The platform's own sentence is kept: on a refused stored result it is the only thing that says what happened.
        assert presentation.details == (f"The platform said: {UNREPORTED_DETAIL}",)
        assert presentation.hint is not None
        assert "support" in presentation.hint
        assert "run-9" in presentation.hint

    def test_a_cancelled_run_without_a_report_is_told_to_start_again(self):
        presentation = present_error(
            RunFailedError("Run finished with status CANCELLED; no result available", run_id="run-9", status=RunStatus.CANCELLED)
        )
        assert presentation.message == "Run run-9 was cancelled, and no reason was recorded for it."
        assert presentation.hint is not None
        assert "start it again" in presentation.hint.lower()

    def test_a_report_carrying_nothing_to_read_out_is_treated_as_no_report(self):
        presentation = present_error(RunFailedError(UNREPORTED_DETAIL, run_id="run-9", status=RunStatus.TIMED_OUT, error=RunErrorReport()))
        assert presentation.message == "Run run-9 timed out, and no reason was recorded for it."
        assert presentation.details == (f"The platform said: {UNREPORTED_DETAIL}",)

    def test_run_timeout_hints_wait(self):
        presentation = present_error(RunTimeoutError("too slow", run_id="run-9", timeout_seconds=1200.0))
        assert presentation.hint is not None
        assert "widget detached wait run-9" in presentation.hint

    def test_unsupported_upload_capability_hints_the_hosted_api(self):
        # summarize-pdf uploads the file; a runner without /v1/upload must point at the hosted API.
        presentation = present_error(UnsupportedUploadCapabilityError("no /v1/upload route here"))
        assert "no /v1/upload route here" in presentation.message
        assert presentation.hint is not None
        assert "PIPELEX_BASE_URL" in presentation.hint

    def test_upload_authentication_hints_api_key(self):
        presentation = present_error(UploadAuthenticationError("not authorized (401)", status=401))
        assert presentation.hint is not None
        assert "PIPELEX_API_KEY" in presentation.hint

    def test_rejected_asset_hints_a_smaller_file(self):
        presentation = present_error(RejectedAssetError("too large", filename="huge.pdf", status=413))
        assert presentation.hint is not None
        assert "smaller" in presentation.hint

    def test_invalid_local_source_hints_the_path(self):
        presentation = present_error(InvalidLocalSourceError("cannot read", source="/nope.pdf"))
        assert presentation.hint is not None
        assert "path" in presentation.hint

    def test_artifact_authentication_hints_api_key(self):
        # The download runs after the run was paid for, so a key that expired between the two gets
        # the same actionable hint the upload family gets one step earlier — not a bare SDK string.
        verdict = DownloadArtifactsResult(scope=ArtifactScope.MAIN_STUFF, all_saved=False)
        presentation = present_error(ArtifactAuthenticationError("not authorized (401)", status=401, verdict=verdict))
        assert presentation.hint is not None
        assert "PIPELEX_API_KEY" in presentation.hint

    def test_artifact_operation_hints_the_download_directory_without_saying_rerun(self):
        presentation = present_error(ArtifactOperationError("downloads/ is a file"))
        assert "downloads/ is a file" in presentation.message
        assert presentation.hint is not None
        assert "download directory" in presentation.hint
        # The run itself succeeded — a hint that sent the reader back to rerun it would cost them.
        assert "rerun" not in presentation.hint.lower()

    @pytest.mark.parametrize(
        ("report", "expected_lines"),
        [
            pytest.param(None, (), id="no report"),
            pytest.param(RunErrorReport(message="The input 'text' is empty."), ("Reason: The input 'text' is empty.",), id="message alone"),
            pytest.param(RunErrorReport(title="LLM completion"), ("Reason: LLM completion",), id="title alone"),
            pytest.param(RunErrorReport(error_type="SandboxProvisioningError"), ("Reason: SandboxProvisioningError",), id="class as last resort"),
            pytest.param(
                RunErrorReport(message="Rate limited.", user_action=UserAction(kind="wait_and_retry")),
                ("Reason: Rate limited.", "Next step: Wait a moment, then run it again."),
                id="kind speaks without detail",
            ),
            pytest.param(
                RunErrorReport(message="Something broke.", user_action=UserAction(kind="unknown")),
                ("Reason: Something broke.",),
                id="unknown kind without detail",
            ),
            pytest.param(
                RunErrorReport(message="The model does not exist.", retryable=False),
                ("Reason: The model does not exist.", "Retry: running it again will fail the same way until the cause is fixed."),
                id="not retryable",
            ),
            # `None` means the runner does not know, never "no" — so nothing is claimed either way.
            pytest.param(RunErrorReport(message="Something broke."), ("Reason: Something broke.",), id="retry advice unknown"),
        ],
    )
    def test_report_lines_read_out_what_the_report_carries(self, report: RunErrorReport | None, expected_lines: tuple[str, ...]):
        assert report_lines(report) == expected_lines

    def test_print_error_prints_the_message_the_details_and_the_hint(self):
        buffer = io.StringIO()
        print_error(Console(file=buffer, width=200), ErrorPresentation(message="Run run-9 failed.", hint="Do this.", details=("Reason: it broke.",)))
        rendered = buffer.getvalue()
        assert "Error: Run run-9 failed." in rendered
        assert "Reason: it broke." in rendered
        assert "Hint: Do this." in rendered

    def test_print_error_prints_server_text_verbatim_rather_than_as_markup(self):
        # A report's message is the runner's text, provider wording included: a bracketed span in it
        # must neither vanish as a style tag nor crash the print as an unmatched closing tag.
        buffer = io.StringIO()
        presentation = ErrorPresentation(message="Bad value [x] in [/y].", hint=None, details=("Reason: list [1, 2] [bold]",))
        print_error(Console(file=buffer, width=200), presentation)
        rendered = buffer.getvalue()
        assert "Bad value [x] in [/y]." in rendered
        assert "Reason: list [1, 2] [bold]" in rendered
