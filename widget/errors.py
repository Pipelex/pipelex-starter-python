"""Present SDK errors as actionable CLI messages.

This module defines no exception classes — it is a presentation mapper. Each mode
package's `_run()` wrapper (`widget/blocking/cli.py`, `widget/attended/cli.py`,
`widget/detached/cli.py`) catches `PipelineRequestError` (the base of every error the
`pipelex-sdk` client raises) exactly once, turns it into an `ErrorPresentation` here —
a message, the lines that explain it, and a hint — prints it with `print_error`, and
exits non-zero. Unexpected exceptions are deliberately NOT caught anywhere: they crash
loudly with a full traceback.

A run that ended without a result is presented from the error report the runner stored
when it failed, which the SDK hands back typed as `RunErrorReport`: `report_lines` reads
out its reason, its next step and its retry advice, and the detached `status` and
`result` commands print the same lines, so a failed run reads the same wherever you
meet it.

Error presentation is orthogonal to execution mode, so it is shared — but the hints
name the mode *groups*, since the fix for a timed-out blocking run is to rerun it under
another group.
"""

import json
from typing import Any, NamedTuple, cast

import httpx
from mthds.protocol.exceptions import PipelineRequestError
from pipelex_sdk.error_models import RunErrorReport, UserAction
from pipelex_sdk.errors import (
    ApiResponseError,
    ApiUnreachableError,
    ArtifactAuthenticationError,
    ArtifactOperationError,
    InputPreparationError,
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
from rich.markup import escape

#: A sentence for each kind of advice the runner names, for a report whose `user_action` carries no
#: `detail`. The kinds are an open set on the wire, so a kind missing here prints no next step rather
#: than a guess — `unknown` among them.
_NEXT_STEP_BY_KIND: dict[str, str] = {
    "wait_and_retry": "Wait a moment, then run it again.",
    "check_billing": "Check your plan and credits.",
    "check_credentials": "Check the credentials the failing call uses.",
    "change_input": "Change the inputs, then run it again.",
    "change_model": "Change the model the failing pipe uses.",
    "contact_support": "Contact support with the run id.",
}


class ErrorPresentation(NamedTuple):
    """What the CLI shows for a failed command: the error, the lines that explain it, and what to do about it."""

    message: str
    hint: str | None
    #: Lines printed under the message — for a failed run, its stored report read out field by field.
    details: tuple[str, ...] = ()


def present_error(exc: PipelineRequestError | httpx.HTTPStatusError) -> ErrorPresentation:
    """Map an SDK error to a CLI-facing message and an actionable hint.

    The SDK's protocol routes (`execute`, `start`, `runs/*`) surface non-2xx
    responses as raw `httpx.HTTPStatusError` (the inherited regime); the typed
    `ApiResponseError` only rides the product routes. Both are mapped here so
    an auth failure gets the API-key hint whichever route raised it.
    """
    if isinstance(exc, httpx.HTTPStatusError):
        return _present_http_status_error(exc)
    if isinstance(exc, PipelineExecuteTimeoutError):
        return ErrorPresentation(
            message=f"The blocking run exceeded the hosted gateway's ~30s synchronous cap ({exc.elapsed_seconds:.0f}s elapsed).",
            hint="Rerun the same command with `widget attended ...` — the durable path survives long runs.",
        )
    if isinstance(exc, RunLifecycleUnavailableError):
        return ErrorPresentation(
            message=f"The server at {exc.api_url} has no run store (durable run lifecycle unavailable).",
            hint="You are talking to a bare runner — use `widget blocking ...`.",
        )
    if isinstance(exc, ApiResponseError):
        if exc.status in (401, 403):
            return ErrorPresentation(
                message=f"The API rejected the request ({exc.status} {exc.status_text}).",
                hint="Set PIPELEX_API_KEY in your environment or .env file — get a key at https://app.pipelex.com",
            )
        return ErrorPresentation(
            message=f"The API answered {exc.status} {exc.status_text}: {exc.server_message or exc}",
            hint=None,
        )
    if isinstance(exc, ApiUnreachableError):
        return ErrorPresentation(
            message=f"Could not reach the Pipelex API at {exc.api_url}.",
            hint="Check PIPELEX_BASE_URL — and if you self-host, make sure your runner is up.",
        )
    if isinstance(exc, RunFailedError):
        return present_failed_run(run_id=exc.run_id, status=exc.status, report=exc.error, platform_message=str(exc))
    if isinstance(exc, RunTimeoutError):
        return ErrorPresentation(
            message=f"Gave up waiting for run {exc.run_id} after {exc.timeout_seconds:.0f}s — the run is still executing server-side.",
            hint=f"Resume waiting with `widget detached wait {exc.run_id}`.",
        )
    # File upload (summarize-pdf) preparation errors — raised before any run is created.
    if isinstance(exc, InputPreparationError):
        return _present_upload_error(exc)
    # Artifact download (generate-image) errors — raised after the run has already been paid for.
    if isinstance(exc, ArtifactOperationError):
        return _present_artifact_error(exc)
    return ErrorPresentation(message=str(exc), hint=None)


def present_failed_run(*, run_id: str, status: RunStatus, report: RunErrorReport | None, platform_message: str | None) -> ErrorPresentation:
    """Present a run that ended without a result, from the report the runner stored when it failed.

    The SDK hands the same three things back wherever such a run surfaces — `RunFailedError` out of
    `wait_for_result`, `start_and_wait` or an artifact download, the failed arm of `get_run_result`, and
    the status read: the terminal `status`, the stored `report` (`None` when the run ended with none,
    as a cancelled run does), and, on the first two, the platform's one sentence about the run.

    With a report, the lines under the message read it out and there is no hint: the report's next
    step is the advice, and a hint pointing at `widget detached status` would only print the same
    lines again. Without one, the platform's sentence is kept — on a stored result the platform
    refuses to serve it is the only thing that says what happened — and the hint says what is left.
    """
    how_it_ended = _how_the_run_ended(status)
    lines = report_lines(report)
    if lines:
        return ErrorPresentation(message=f"Run {run_id} {how_it_ended}.", hint=None, details=lines)
    platform_lines = (f"The platform said: {platform_message}",) if platform_message else ()
    return ErrorPresentation(
        message=f"Run {run_id} {how_it_ended}, and no reason was recorded for it.",
        hint=_hint_without_a_reason(run_id=run_id, status=status),
        details=platform_lines,
    )


def report_lines(report: RunErrorReport | None) -> tuple[str, ...]:
    """A failed run's stored report as the lines a person reads: the reason, the next step, the retry advice.

    The reason is the report's `title` and `message` (its `error_type`, the runner's exception class,
    when it carries neither); the next step is its `user_action`; the retry advice is its `retryable`,
    left unsaid when that is `None`, which means unknown rather than no. Empty when there is no report
    or it carries none of these, so the caller can tell a report worth reading from its absence.

    The report is the runner's verbose one, so `message` can hold a provider's raw text. This is a
    developer's tool, so it is printed as it came; an application in front of end users decides what
    of it they see.
    """
    if report is None:
        return ()
    lines: list[str] = []
    reason = _reason(report)
    if reason:
        lines.append(f"Reason: {reason}")
    next_step = _next_step(report.user_action)
    if next_step:
        lines.append(f"Next step: {next_step}")
    match report.retryable:
        case True:
            lines.append("Retry: running it again may succeed.")
        case False:
            lines.append("Retry: running it again will fail the same way until the cause is fixed.")
        case None:
            pass
    return tuple(lines)


def print_error(console: Console, presentation: ErrorPresentation) -> None:
    """Print a presentation: the message, its detail lines, then the hint.

    Every piece is escaped before it reaches Rich, because the message and the details carry the
    server's text: a bracketed span in a provider's message would otherwise be read as a style tag,
    swallowed, or crash the print as an unmatched closing tag.
    """
    console.print(f"[red]Error:[/red] {escape(presentation.message)}")
    for line in presentation.details:
        console.print(f"  {escape(line)}")
    if presentation.hint:
        console.print(f"\n[yellow]Hint:[/yellow] {escape(presentation.hint)}")


def _how_the_run_ended(status: RunStatus) -> str:
    match status:
        case RunStatus.FAILED:
            return "failed"
        case RunStatus.CANCELLED:
            return "was cancelled"
        case RunStatus.TERMINATED:
            return "was terminated"
        case RunStatus.TIMED_OUT:
            return "timed out"
        case RunStatus.PENDING | RunStatus.STARTED | RunStatus.RUNNING | RunStatus.COMPLETED:
            # Not an ending without a result, so it is named as the status rather than worded as one.
            return f"ended with status {status}"


def _hint_without_a_reason(*, run_id: str, status: RunStatus) -> str:
    match status:
        case RunStatus.FAILED:
            return f"Nothing more is recorded about this failure — contact support with the run id {run_id}."
        case RunStatus.CANCELLED | RunStatus.TERMINATED | RunStatus.TIMED_OUT:
            return "The run stopped before it produced a result — start it again to get one."
        case RunStatus.PENDING | RunStatus.STARTED | RunStatus.RUNNING | RunStatus.COMPLETED:
            return f"Check it again with `widget detached status {run_id}`."


def _reason(report: RunErrorReport) -> str | None:
    """The report's title and message, whichever it carries, or its exception class as a last resort."""
    title = _text(report.title)
    message = _text(report.message)
    if title and message:
        return f"{title} — {message}"
    return title or message or _text(report.error_type)


def _next_step(user_action: UserAction | None) -> str | None:
    """The advice's own words, or a sentence for its kind when it gives none."""
    if user_action is None:
        return None
    return _text(user_action.detail) or _NEXT_STEP_BY_KIND.get(user_action.kind or "")


def _text(value: str | None) -> str | None:
    """A report field as printable text: `None` for a missing or blank one."""
    if value is None:
        return None
    stripped = value.strip()
    return stripped or None


def _present_upload_error(exc: InputPreparationError) -> ErrorPresentation:
    """Present a file-upload (input-preparation) failure. The SDK already gives each a clear
    message; here we add the actionable hint per semantic category."""
    if isinstance(exc, UnsupportedUploadCapabilityError):
        hint = "File upload is a hosted capability — point PIPELEX_BASE_URL at https://api.pipelex.com (a bare runner may not serve /v1/upload)."
    elif isinstance(exc, UploadAuthenticationError):
        hint = "Set PIPELEX_API_KEY in your environment or .env file — get a key at https://app.pipelex.com"
    elif isinstance(exc, RejectedAssetError):
        hint = "The server rejected the file (usually past the service size cap) — try a smaller file."
    elif isinstance(exc, InvalidLocalSourceError):
        hint = "Check the path points at a readable file."
    else:
        hint = "Check PIPELEX_BASE_URL and that the API is reachable."
    return ErrorPresentation(message=str(exc), hint=hint)


def _present_artifact_error(exc: ArtifactOperationError) -> ErrorPresentation:
    """Present a failure to bring a run's produced files down.

    This family is raised by `widget/artifacts.py` *after* the run itself succeeded and its output
    was printed, so no hint here ever says to rerun: the run has been paid for, and what is left
    is to recover the files it produced.
    """
    if isinstance(exc, ArtifactAuthenticationError):
        hint = "Set PIPELEX_API_KEY in your environment or .env file — get a key at https://app.pipelex.com"
    else:
        hint = "The run itself succeeded — check the download directory is writable and is not an existing file."
    return ErrorPresentation(message=str(exc), hint=hint)


def _present_http_status_error(exc: httpx.HTTPStatusError) -> ErrorPresentation:
    """Present a raw protocol-route HTTP error, reading its RFC 7807 problem+json body.

    The protocol routes (`execute`, `start`, `runs/*`) return errors as
    `application/problem+json`: a human `detail`/`title` and a machine `error_type`.
    httpx's own stringification throws all of that away (`Client error '400 Bad
    Request' for url …` plus an MDN link), so we read the body and surface what the
    server actually said — and branch on the structured `error_type`, never the
    transport status, for the cases worth a hint.
    """
    status_code = exc.response.status_code
    problem = _read_problem_json(exc.response)
    if status_code in (401, 403):
        return ErrorPresentation(
            message=f"The API rejected the request ({status_code} {exc.response.reason_phrase}).",
            hint="Set PIPELEX_API_KEY in your environment or .env file — get a key at https://app.pipelex.com",
        )
    # A durable-run endpoint (`/start`) this deployment can't serve: it runs a
    # synchronous-only orchestration, so only `widget blocking` (`/execute`) works here.
    if problem.get("error_type") == "StartRequiresAsyncOrchestration":
        return ErrorPresentation(
            message=problem.get("detail") or "This deployment cannot start durable runs — it has no async orchestration.",
            hint="This runner only does synchronous runs — use `widget blocking ...` instead.",
        )
    detail = problem.get("detail") or problem.get("title")
    if detail:
        return ErrorPresentation(message=f"The API answered {status_code} {exc.response.reason_phrase}: {detail}", hint=None)
    return ErrorPresentation(message=f"The API answered {status_code} {exc.response.reason_phrase}.", hint=None)


def _read_problem_json(response: httpx.Response) -> dict[str, Any]:
    """Best-effort parse of an RFC 7807 problem+json body; `{}` when it isn't JSON."""
    try:
        body: Any = response.json()
    except (json.JSONDecodeError, UnicodeDecodeError):
        # UnicodeDecodeError: `response.json()` is `json.loads(response.content)`,
        # which raises it (not JSONDecodeError) on a non-UTF-8 body.
        return {}
    if isinstance(body, dict):
        # JSON object keys are always strings.
        return cast("dict[str, Any]", body)
    return {}
