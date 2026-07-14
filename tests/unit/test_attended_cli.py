from pathlib import Path

from pytest_mock import MockerFixture
from typer.testing import CliRunner

from piper.cli import app

ENTITIES_CONTENT = {"people": ["Marie Curie"], "orgs": ["University of Paris"], "dates": ["1906"]}
SUMMARY_CONTENT = {"title": "Q3 Report", "doc_type": "report", "key_points": ["Revenue up 12%"]}
IMAGE_CONTENT = {"url": "https://example.com/cat.png", "public_url": "https://cdn.example.com/cat.png"}

runner = CliRunner()


class TestAttendedCli:
    def test_help_lists_the_demos(self):
        result = runner.invoke(app, ["attended", "--help"])
        assert result.exit_code == 0
        for command in ("extract-entities", "summarize-pdf", "generate-image"):
            assert command in result.output

    def test_extract_entities_starts_waits_and_prints_result(self, mocker: MockerFixture):
        attended_mock = mocker.patch("piper.attended.cli.start_and_wait", return_value=ENTITIES_CONTENT)
        result = runner.invoke(app, ["attended", "extract-entities", "some text"])
        assert result.exit_code == 0
        attended_mock.assert_awaited_once()
        assert attended_mock.await_args is not None
        assert attended_mock.await_args.kwargs["pipe_code"] == "extract_entities"
        assert attended_mock.await_args.kwargs["inputs"] == {"text": "some text"}
        assert "Marie Curie" in result.output

    def test_extract_entities_requires_input(self):
        result = runner.invoke(app, ["attended", "extract-entities"])
        assert result.exit_code != 0

    def test_extract_entities_rejects_both_text_and_file(self, tmp_path: Path):
        input_file = tmp_path / "input.txt"
        input_file.write_text("from a file")
        result = runner.invoke(app, ["attended", "extract-entities", "inline text", "--file", str(input_file)])
        assert result.exit_code != 0

    def test_extract_entities_reads_the_file_input(self, mocker: MockerFixture, tmp_path: Path):
        attended_mock = mocker.patch("piper.attended.cli.start_and_wait", return_value=ENTITIES_CONTENT)
        input_file = tmp_path / "input.txt"
        input_file.write_text("text from a file")
        result = runner.invoke(app, ["attended", "extract-entities", "--file", str(input_file)])
        assert result.exit_code == 0
        assert attended_mock.await_args is not None
        assert attended_mock.await_args.kwargs["inputs"] == {"text": "text from a file"}

    def test_summarize_pdf_requires_a_file(self):
        result = runner.invoke(app, ["attended", "summarize-pdf"])
        assert result.exit_code != 0

    def test_summarize_pdf_rejects_a_missing_file(self, tmp_path: Path):
        result = runner.invoke(app, ["attended", "summarize-pdf", str(tmp_path / "nope.pdf")])
        assert result.exit_code != 0

    def test_summarize_pdf_sends_the_document_envelope(self, mocker: MockerFixture, tmp_path: Path):
        attended_mock = mocker.patch("piper.attended.cli.start_and_wait", return_value=SUMMARY_CONTENT)
        pdf = tmp_path / "doc.pdf"
        pdf.write_bytes(b"%PDF-1.4 fake")
        result = runner.invoke(app, ["attended", "summarize-pdf", str(pdf)])
        assert result.exit_code == 0
        assert "Q3 Report" in result.output
        assert attended_mock.await_args is not None
        document_input = attended_mock.await_args.kwargs["inputs"]["document"]
        assert document_input["concept"] == "Document"
        assert document_input["content"]["mime_type"] == "application/pdf"
        assert document_input["content"]["url"].startswith("data:application/pdf;base64,")

    def test_generate_image_requires_input(self):
        result = runner.invoke(app, ["attended", "generate-image"])
        assert result.exit_code != 0

    def test_generate_image_sends_the_prompt(self, mocker: MockerFixture):
        attended_mock = mocker.patch("piper.attended.cli.start_and_wait", return_value=IMAGE_CONTENT)
        result = runner.invoke(app, ["attended", "generate-image", "a cat wearing a hat"])
        assert result.exit_code == 0
        assert "example.com/cat.png" in result.output
        assert attended_mock.await_args is not None
        assert attended_mock.await_args.kwargs["inputs"] == {"image_prompt": "a cat wearing a hat"}
