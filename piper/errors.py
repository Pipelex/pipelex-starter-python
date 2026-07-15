"""Present SDK errors as actionable CLI messages.

This module defines no exception classes — it is a presentation mapper. Each mode
package's `_run()` wrapper (`piper/blocking/cli.py`, `piper/attended/cli.py`,
`piper/detached/cli.py`) catches `PipelineRequestError` (the base of every error the
`pipelex-sdk` client raises) exactly once, turns it into a `(message, hint)` pair here,
and exits non-zero. Unexpected exceptions are deliberately NOT caught anywhere: they
crash loudly with a full traceback.

Error presentation is orthogonal to execution mode, so it is shared — but the hints
name the mode *groups*, since the fix for a timed-out blocking run is to rerun it under
another group.
"""

import json
from typing import Any, NamedTuple, cast

import httpx
from mthds.protocol.exceptions import PipelineRequestError
from pipelex_sdk.errors import (
    ApiResponseError,
    ApiUnreachableError,
    PipelineExecuteTimeoutError,
    RunFailedError,
    RunLifecycleUnavailableError,
    RunTimeoutError,
)


class ErrorPresentation(NamedTuple):
    """What the CLI shows for a failed command: the error and what to do about it."""

    message: str
    hint: str | None


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
            hint="Rerun the same command with `piper attended ...` — the durable path survives long runs.",
        )
    if isinstance(exc, RunLifecycleUnavailableError):
        return ErrorPresentation(
            message=f"The server at {exc.api_url} has no run store (durable run lifecycle unavailable).",
            hint="You are talking to a bare runner — use `piper blocking ...`.",
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
        return ErrorPresentation(
            message=f"Run {exc.run_id} ended with status {exc.status}: {exc}",
            hint=f"Inspect it with `piper detached status {exc.run_id}`.",
        )
    if isinstance(exc, RunTimeoutError):
        return ErrorPresentation(
            message=f"Gave up waiting for run {exc.run_id} after {exc.timeout_seconds:.0f}s — the run is still executing server-side.",
            hint=f"Resume waiting with `piper detached wait {exc.run_id}`.",
        )
    return ErrorPresentation(message=str(exc), hint=None)


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
    # synchronous-only orchestration, so only `piper blocking` (`/execute`) works here.
    if problem.get("error_type") == "StartRequiresAsyncOrchestration":
        return ErrorPresentation(
            message=problem.get("detail") or "This deployment cannot start durable runs — it has no async orchestration.",
            hint="This runner only does synchronous runs — use `piper blocking ...` instead.",
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
