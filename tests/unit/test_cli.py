from pathlib import Path

from pipelex_sdk.runs import RunResults
from pytest_mock import MockerFixture
from typer.testing import CliRunner

from piper.cli import app

ENTITIES_CONTENT = {"people": ["Marie Curie"], "orgs": ["University of Paris"], "dates": ["1906"]}
SUMMARY_CONTENT = {"title": "Q3 Report", "doc_type": "report", "key_points": ["Revenue up 12%"]}
IMAGE_CONTENT = {"url": "https://example.com/cat.png", "public_url": "https://cdn.example.com/cat.png"}

runner = CliRunner()


class TestCli:
    def test_help_lists_commands(self):
        result = runner.invoke(app, ["--help"])
        assert result.exit_code == 0
        for command in ("extract-entities", "summarize-pdf", "generate-image", "runs"):
            assert command in result.output

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

    def test_default_mode_is_durable(self, mocker: MockerFixture):
        durable_mock = mocker.patch("piper.cli.run_durable_attended", return_value=RunResults(pipeline_run_id="run-1", main_stuff=ENTITIES_CONTENT))
        result = runner.invoke(app, ["extract-entities", "some text"])
        assert result.exit_code == 0
        durable_mock.assert_awaited_once()
        assert "Marie Curie" in result.output

    def test_env_var_selects_blocking_mode(self, mocker: MockerFixture):
        blocking_mock = mocker.patch("piper.cli.run_blocking", return_value=RunResults(pipeline_run_id="run-2", main_stuff=ENTITIES_CONTENT))
        result = runner.invoke(app, ["extract-entities", "some text"], env={"PIPELEX_EXECUTION_MODE": "blocking"})
        assert result.exit_code == 0
        blocking_mock.assert_awaited_once()

    def test_file_input_is_read(self, mocker: MockerFixture, tmp_path: Path):
        durable_mock = mocker.patch("piper.cli.run_durable_attended", return_value=RunResults(pipeline_run_id="run-3", main_stuff=ENTITIES_CONTENT))
        input_file = tmp_path / "input.txt"
        input_file.write_text("text from a file")
        result = runner.invoke(app, ["extract-entities", "--file", str(input_file)])
        assert result.exit_code == 0
        assert durable_mock.await_args is not None
        assert durable_mock.await_args.kwargs["inputs"] == {"text": "text from a file"}

    def test_detached_mode_prints_run_id(self, mocker: MockerFixture):
        detached_mock = mocker.patch("piper.cli.start_detached", return_value="run-abc123")
        result = runner.invoke(app, ["extract-entities", "some text", "--mode", "detached"])
        assert result.exit_code == 0
        detached_mock.assert_awaited_once()
        assert "run-abc123" in result.output

    def test_summarize_pdf_requires_file(self):
        result = runner.invoke(app, ["summarize-pdf"])
        assert result.exit_code != 0

    def test_summarize_pdf_rejects_missing_file(self, tmp_path: Path):
        result = runner.invoke(app, ["summarize-pdf", str(tmp_path / "nope.pdf")])
        assert result.exit_code != 0

    def test_summarize_pdf_sends_document_input(self, mocker: MockerFixture, tmp_path: Path):
        durable_mock = mocker.patch("piper.cli.run_durable_attended", return_value=RunResults(pipeline_run_id="run-pdf", main_stuff=SUMMARY_CONTENT))
        pdf = tmp_path / "doc.pdf"
        pdf.write_bytes(b"%PDF-1.4 fake")
        result = runner.invoke(app, ["summarize-pdf", str(pdf)])
        assert result.exit_code == 0
        assert "Q3 Report" in result.output
        assert durable_mock.await_args is not None
        document_input = durable_mock.await_args.kwargs["inputs"]["document"]
        assert document_input["concept"] == "Document"
        assert document_input["content"]["mime_type"] == "application/pdf"
        assert document_input["content"]["url"].startswith("data:application/pdf;base64,")

    def test_generate_image_requires_input(self):
        result = runner.invoke(app, ["generate-image"])
        assert result.exit_code != 0

    def test_generate_image_sends_prompt(self, mocker: MockerFixture):
        durable_mock = mocker.patch("piper.cli.run_durable_attended", return_value=RunResults(pipeline_run_id="run-img", main_stuff=IMAGE_CONTENT))
        result = runner.invoke(app, ["generate-image", "a cat wearing a hat"])
        assert result.exit_code == 0
        assert "example.com/cat.png" in result.output
        assert durable_mock.await_args is not None
        assert durable_mock.await_args.kwargs["inputs"] == {"image_prompt": "a cat wearing a hat"}
