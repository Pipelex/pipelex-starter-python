from pathlib import Path

from pipelex_sdk.runs import RunRead, RunResultCompleted, RunResultFailed, RunResultRunning, RunResults, RunStatus
from pytest_mock import MockerFixture
from typer.testing import CliRunner

from piper.cli import app
from piper.inputs import SAMPLE_ENTITIES_TEXT, SAMPLE_IMAGE_PROMPT

ENTITIES_CONTENT = {"people": ["Marie Curie"], "orgs": ["University of Paris"], "dates": ["1906"]}
RUN_ID = "run-abc123"

runner = CliRunner()


class TestDetachedCli:
    def test_help_lists_the_demos_and_the_lifecycle_commands(self):
        result = runner.invoke(app, ["detached", "--help"])
        assert result.exit_code == 0
        for command in ("extract-entities", "summarize-pdf", "generate-image", "wait", "status", "result"):
            assert command in result.output

    def test_extract_entities_starts_the_run_and_prints_its_id(self, mocker: MockerFixture):
        start_mock = mocker.patch("piper.detached.cli.start_pipe", return_value=RUN_ID)
        result = runner.invoke(app, ["detached", "extract-entities", "some text"])
        assert result.exit_code == 0
        start_mock.assert_awaited_once()
        assert start_mock.await_args is not None
        assert start_mock.await_args.kwargs["pipe_code"] == "extract_entities"
        assert start_mock.await_args.kwargs["inputs"] == {"text": "some text"}
        # The bare id on stdout is the contract: RUN_ID=$(piper detached extract-entities "…")
        assert result.stdout.strip() == RUN_ID

    def test_extract_entities_falls_back_to_the_sample(self, mocker: MockerFixture):
        start_mock = mocker.patch("piper.detached.cli.start_pipe", return_value=RUN_ID)
        result = runner.invoke(app, ["detached", "extract-entities"])
        assert result.exit_code == 0
        assert start_mock.await_args is not None
        assert start_mock.await_args.kwargs["inputs"] == {"text": SAMPLE_ENTITIES_TEXT}
        # The sample notice goes to stderr, so stdout stays the bare run id.
        assert result.stdout.strip() == RUN_ID

    def test_extract_entities_rejects_both_text_and_file(self, tmp_path: Path):
        input_file = tmp_path / "input.txt"
        input_file.write_text("from a file")
        result = runner.invoke(app, ["detached", "extract-entities", "inline text", "--file", str(input_file)])
        assert result.exit_code != 0

    def test_extract_entities_reads_the_file_input(self, mocker: MockerFixture, tmp_path: Path):
        start_mock = mocker.patch("piper.detached.cli.start_pipe", return_value=RUN_ID)
        input_file = tmp_path / "input.txt"
        input_file.write_text("text from a file")
        result = runner.invoke(app, ["detached", "extract-entities", "--file", str(input_file)])
        assert result.exit_code == 0
        assert start_mock.await_args is not None
        assert start_mock.await_args.kwargs["inputs"] == {"text": "text from a file"}

    def test_summarize_pdf_falls_back_to_the_sample_invoice(self, mocker: MockerFixture):
        start_mock = mocker.patch("piper.detached.cli.start_pipe", return_value=RUN_ID)
        result = runner.invoke(app, ["detached", "summarize-pdf"])
        assert result.exit_code == 0
        assert start_mock.await_args is not None
        document_input = start_mock.await_args.kwargs["inputs"]["document"]
        assert document_input["concept"] == "Document"
        assert document_input["content"]["filename"] == "sample-invoice.pdf"

    def test_summarize_pdf_rejects_a_missing_file(self, tmp_path: Path):
        result = runner.invoke(app, ["detached", "summarize-pdf", str(tmp_path / "nope.pdf")])
        assert result.exit_code != 0

    def test_summarize_pdf_sends_the_document_envelope(self, mocker: MockerFixture, tmp_path: Path):
        start_mock = mocker.patch("piper.detached.cli.start_pipe", return_value=RUN_ID)
        pdf = tmp_path / "doc.pdf"
        pdf.write_bytes(b"%PDF-1.4 fake")
        result = runner.invoke(app, ["detached", "summarize-pdf", str(pdf)])
        assert result.exit_code == 0
        assert start_mock.await_args is not None
        document_input = start_mock.await_args.kwargs["inputs"]["document"]
        assert document_input["concept"] == "Document"
        assert document_input["content"]["mime_type"] == "application/pdf"
        assert document_input["content"]["url"].startswith("data:application/pdf;base64,")

    def test_generate_image_falls_back_to_the_sample(self, mocker: MockerFixture):
        start_mock = mocker.patch("piper.detached.cli.start_pipe", return_value=RUN_ID)
        result = runner.invoke(app, ["detached", "generate-image"])
        assert result.exit_code == 0
        assert start_mock.await_args is not None
        assert start_mock.await_args.kwargs["inputs"] == {"image_prompt": SAMPLE_IMAGE_PROMPT}
        assert result.stdout.strip() == RUN_ID

    def test_generate_image_sends_the_prompt(self, mocker: MockerFixture):
        start_mock = mocker.patch("piper.detached.cli.start_pipe", return_value=RUN_ID)
        result = runner.invoke(app, ["detached", "generate-image", "a cat wearing a hat"])
        assert result.exit_code == 0
        assert start_mock.await_args is not None
        assert start_mock.await_args.kwargs["inputs"] == {"image_prompt": "a cat wearing a hat"}
        assert result.stdout.strip() == RUN_ID

    def test_wait_prints_the_raw_main_stuff(self, mocker: MockerFixture):
        attend_mock = mocker.patch("piper.detached.cli.attend_run", return_value=ENTITIES_CONTENT)
        result = runner.invoke(app, ["detached", "wait", RUN_ID])
        assert result.exit_code == 0
        attend_mock.assert_awaited_once_with(RUN_ID)
        assert "Marie Curie" in result.output

    def test_status_reports_the_run_status(self, mocker: MockerFixture):
        run = RunRead(pipeline_run_id=RUN_ID, pipe_code="extract_entities", status=RunStatus.RUNNING, created_at="2026-07-13T10:00:00Z")
        mocker.patch("piper.detached.cli.fetch_run_status", return_value=run)
        result = runner.invoke(app, ["detached", "status", RUN_ID])
        assert result.exit_code == 0
        assert RUN_ID in result.output
        assert "RUNNING" in result.output
        assert "extract_entities" in result.output

    def test_status_flags_a_degraded_reading(self, mocker: MockerFixture):
        run = RunRead(pipeline_run_id=RUN_ID, status=RunStatus.RUNNING, created_at="2026-07-13T10:00:00Z", degraded=True)
        mocker.patch("piper.detached.cli.fetch_run_status", return_value=run)
        result = runner.invoke(app, ["detached", "status", RUN_ID])
        assert result.exit_code == 0
        assert "degraded" in result.output

    def test_result_hints_at_wait_while_the_run_is_running(self, mocker: MockerFixture):
        mocker.patch("piper.detached.cli.fetch_run_result", return_value=RunResultRunning(pipeline_run_id=RUN_ID))
        result = runner.invoke(app, ["detached", "result", RUN_ID])
        assert result.exit_code == 0
        assert "piper detached wait" in result.output

    def test_result_prints_the_raw_main_stuff_when_completed(self, mocker: MockerFixture):
        completed = RunResultCompleted(pipeline_run_id=RUN_ID, result=RunResults(pipeline_run_id=RUN_ID, main_stuff=ENTITIES_CONTENT))
        mocker.patch("piper.detached.cli.fetch_run_result", return_value=completed)
        result = runner.invoke(app, ["detached", "result", RUN_ID])
        assert result.exit_code == 0
        assert "Marie Curie" in result.output

    def test_result_exits_non_zero_when_the_run_failed(self, mocker: MockerFixture):
        failed = RunResultFailed(pipeline_run_id=RUN_ID, status=RunStatus.FAILED, message="the pipe blew up")
        mocker.patch("piper.detached.cli.fetch_run_result", return_value=failed)
        result = runner.invoke(app, ["detached", "result", RUN_ID])
        assert result.exit_code == 1
        assert "the pipe blew up" in result.output
