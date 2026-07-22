from pathlib import Path

from pytest_mock import MockerFixture
from typer.testing import CliRunner

from piper.cli import app
from piper.inputs import SAMPLE_ENTITIES_TEXT, SAMPLE_IMAGE_PROMPT
from piper.usage import RunUsage

ENTITIES_CONTENT = {"people": ["Marie Curie"], "orgs": ["University of Paris"], "dates": ["1906"]}
SUMMARY_CONTENT = {"title": "Q3 Report", "doc_type": "report", "key_points": ["Revenue up 12%"]}
IMAGE_CONTENT = {"url": "https://example.com/cat.png", "public_url": "https://cdn.example.com/cat.png"}

# The lifecycle helpers return (main_stuff, RunUsage); these offline tests don't exercise cost.
NO_USAGE = RunUsage(tokens_usages=None, usage_assembly_error=None)

runner = CliRunner()


class TestBlockingCli:
    def test_help_lists_the_demos(self):
        result = runner.invoke(app, ["blocking", "--help"])
        assert result.exit_code == 0
        for command in ("extract-entities", "summarize-pdf", "generate-image"):
            assert command in result.output

    def test_extract_entities_executes_and_prints_result(self, mocker: MockerFixture):
        execute_mock = mocker.patch("piper.blocking.cli.execute_pipe", return_value=(ENTITIES_CONTENT, NO_USAGE))
        result = runner.invoke(app, ["blocking", "extract-entities", "some text"])
        assert result.exit_code == 0
        execute_mock.assert_awaited_once()
        assert execute_mock.await_args is not None
        assert execute_mock.await_args.kwargs["pipe_code"] == "extract_entities"
        assert execute_mock.await_args.kwargs["inputs"] == {"text": "some text"}
        assert "Marie Curie" in result.output

    def test_extract_entities_falls_back_to_the_sample(self, mocker: MockerFixture):
        execute_mock = mocker.patch("piper.blocking.cli.execute_pipe", return_value=(ENTITIES_CONTENT, NO_USAGE))
        result = runner.invoke(app, ["blocking", "extract-entities"])
        assert result.exit_code == 0
        assert execute_mock.await_args is not None
        assert execute_mock.await_args.kwargs["inputs"] == {"text": SAMPLE_ENTITIES_TEXT}

    def test_extract_entities_rejects_both_text_and_file(self, tmp_path: Path):
        input_file = tmp_path / "input.txt"
        input_file.write_text("from a file")
        result = runner.invoke(app, ["blocking", "extract-entities", "inline text", "--file", str(input_file)])
        assert result.exit_code != 0

    def test_extract_entities_reads_the_file_input(self, mocker: MockerFixture, tmp_path: Path):
        execute_mock = mocker.patch("piper.blocking.cli.execute_pipe", return_value=(ENTITIES_CONTENT, NO_USAGE))
        input_file = tmp_path / "input.txt"
        input_file.write_text("text from a file")
        result = runner.invoke(app, ["blocking", "extract-entities", "--file", str(input_file)])
        assert result.exit_code == 0
        assert execute_mock.await_args is not None
        assert execute_mock.await_args.kwargs["inputs"] == {"text": "text from a file"}

    def test_summarize_pdf_falls_back_to_the_sample_invoice(self, mocker: MockerFixture, stub_upload: str):
        execute_mock = mocker.patch("piper.blocking.cli.execute_pipe", return_value=(SUMMARY_CONTENT, NO_USAGE))
        result = runner.invoke(app, ["blocking", "summarize-pdf"])
        assert result.exit_code == 0
        assert execute_mock.await_args is not None
        document_input = execute_mock.await_args.kwargs["inputs"]["document"]
        assert document_input["concept"] == "Document"
        assert document_input["content"]["filename"] == "sample-invoice.pdf"
        assert document_input["content"]["url"] == stub_upload

    def test_summarize_pdf_rejects_a_missing_file(self, tmp_path: Path):
        result = runner.invoke(app, ["blocking", "summarize-pdf", str(tmp_path / "nope.pdf")])
        assert result.exit_code != 0

    def test_summarize_pdf_sends_the_document_envelope(self, mocker: MockerFixture, tmp_path: Path, stub_upload: str):
        execute_mock = mocker.patch("piper.blocking.cli.execute_pipe", return_value=(SUMMARY_CONTENT, NO_USAGE))
        pdf = tmp_path / "doc.pdf"
        pdf.write_bytes(b"%PDF-1.4 fake")
        result = runner.invoke(app, ["blocking", "summarize-pdf", str(pdf)])
        assert result.exit_code == 0
        assert "Q3 Report" in result.output
        assert execute_mock.await_args is not None
        document_input = execute_mock.await_args.kwargs["inputs"]["document"]
        assert document_input["concept"] == "Document"
        assert document_input["content"]["mime_type"] == "application/pdf"
        assert document_input["content"]["url"] == stub_upload

    def test_generate_image_falls_back_to_the_sample(self, mocker: MockerFixture):
        execute_mock = mocker.patch("piper.blocking.cli.execute_pipe", return_value=(IMAGE_CONTENT, NO_USAGE))
        result = runner.invoke(app, ["blocking", "generate-image"])
        assert result.exit_code == 0
        assert execute_mock.await_args is not None
        assert execute_mock.await_args.kwargs["inputs"] == {"image_prompt": SAMPLE_IMAGE_PROMPT}

    def test_generate_image_sends_the_prompt(self, mocker: MockerFixture):
        execute_mock = mocker.patch("piper.blocking.cli.execute_pipe", return_value=(IMAGE_CONTENT, NO_USAGE))
        result = runner.invoke(app, ["blocking", "generate-image", "a cat wearing a hat"])
        assert result.exit_code == 0
        assert "example.com/cat.png" in result.output
        assert execute_mock.await_args is not None
        assert execute_mock.await_args.kwargs["inputs"] == {"image_prompt": "a cat wearing a hat"}
