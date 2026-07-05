from pathlib import Path

from pipelex_sdk.runs import RunResults
from pytest_mock import MockerFixture
from typer.testing import CliRunner

from my_project.cli import app

ENTITIES_CONTENT = {"people": ["Marie Curie"], "orgs": ["University of Paris"], "dates": ["1906"]}

runner = CliRunner()


class TestCli:
    def test_help_lists_commands(self):
        result = runner.invoke(app, ["--help"])
        assert result.exit_code == 0
        assert "extract-entities" in result.output
        assert "runs" in result.output

    def test_runs_help_lists_subcommands(self):
        result = runner.invoke(app, ["runs", "--help"])
        assert result.exit_code == 0
        for subcommand in ("status", "result", "wait"):
            assert subcommand in result.output

    def test_extract_entities_requires_input(self):
        result = runner.invoke(app, ["extract-entities"])
        assert result.exit_code != 0

    def test_extract_entities_rejects_both_text_and_file(self, tmp_path: Path):
        input_file = tmp_path / "input.txt"
        input_file.write_text("from a file")
        result = runner.invoke(app, ["extract-entities", "inline text", "--file", str(input_file)])
        assert result.exit_code != 0

    def test_extract_entities_rejects_bad_mode(self):
        result = runner.invoke(app, ["extract-entities", "some text", "--mode", "bogus"])
        assert result.exit_code != 0

    def test_extract_entities_rejects_blocking_detach(self):
        result = runner.invoke(app, ["extract-entities", "some text", "--mode", "blocking", "--detach"])
        assert result.exit_code != 0

    def test_default_mode_is_durable(self, mocker: MockerFixture):
        durable_mock = mocker.patch(
            "my_project.cli.run_durable_attended", return_value=RunResults(pipeline_run_id="run-1", main_stuff=ENTITIES_CONTENT)
        )
        result = runner.invoke(app, ["extract-entities", "some text"])
        assert result.exit_code == 0
        durable_mock.assert_awaited_once()
        assert "Marie Curie" in result.output

    def test_env_var_selects_blocking_mode(self, mocker: MockerFixture):
        blocking_mock = mocker.patch("my_project.cli.run_blocking", return_value=RunResults(pipeline_run_id="run-2", main_stuff=ENTITIES_CONTENT))
        result = runner.invoke(app, ["extract-entities", "some text"], env={"PIPELEX_EXECUTION_MODE": "blocking"})
        assert result.exit_code == 0
        blocking_mock.assert_awaited_once()

    def test_file_input_is_read(self, mocker: MockerFixture, tmp_path: Path):
        durable_mock = mocker.patch(
            "my_project.cli.run_durable_attended", return_value=RunResults(pipeline_run_id="run-3", main_stuff=ENTITIES_CONTENT)
        )
        input_file = tmp_path / "input.txt"
        input_file.write_text("text from a file")
        result = runner.invoke(app, ["extract-entities", "--file", str(input_file)])
        assert result.exit_code == 0
        assert durable_mock.await_args is not None
        assert durable_mock.await_args.kwargs["inputs"] == {"text": "text from a file"}

    def test_detach_prints_run_id(self, mocker: MockerFixture):
        mocker.patch("my_project.cli.start_detached", return_value="run-abc123")
        result = runner.invoke(app, ["extract-entities", "some text", "--detach"])
        assert result.exit_code == 0
        assert "run-abc123" in result.output
