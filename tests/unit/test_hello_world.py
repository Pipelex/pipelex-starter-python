from typing import Any

import pytest
from pytest import CaptureFixture, MonkeyPatch

from my_project import hello_world as hello_world_module
from my_project.hello_world import hello_world


class _FakeResults:
    # Minimal stand-in for pipelex_sdk.runs.RunResults: find_main_content()
    # reads only `.main_stuff` / `.pipe_output`.
    def __init__(self, main_stuff: Any) -> None:
        self.main_stuff = main_stuff
        self.pipe_output = None


class _FakeClient:
    # Stand-in for PipelexAPIClient used as `async with ... as client`, so no
    # network is touched: __aenter__ returns the client and start_and_wait
    # yields the canned results.
    def __init__(self, results: _FakeResults) -> None:
        self._results = results

    async def __aenter__(self) -> "_FakeClient":
        return self

    async def __aexit__(self, *_exc_info: object) -> None:
        return None

    async def start_and_wait(self, *, pipe_code: str, mthds_contents: list[str]) -> _FakeResults:
        return self._results


class TestHelloWorldOutput:
    def _patch_client(self, monkeypatch: MonkeyPatch, main_stuff: Any) -> None:
        results = _FakeResults(main_stuff=main_stuff)
        monkeypatch.setattr(hello_world_module, "PipelexAPIClient", lambda: _FakeClient(results))

    async def test_missing_text_raises(self, monkeypatch: MonkeyPatch):
        # A valid content dict without a `text` key must fail loudly instead of
        # printing `None` and exiting successfully.
        self._patch_client(monkeypatch, main_stuff={"not_text": "oops"})

        with pytest.raises(RuntimeError, match="no text output"):
            await hello_world()

    async def test_valid_text_prints(self, monkeypatch: MonkeyPatch, capsys: CaptureFixture[str]):
        self._patch_client(monkeypatch, main_stuff={"text": "a generated haiku"})

        await hello_world()

        assert "a generated haiku" in capsys.readouterr().out
