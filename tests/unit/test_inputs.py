import base64
from pathlib import Path

import pytest
import typer

from piper.inputs import build_document_input, read_text_input


class TestInputs:
    def test_read_text_input_from_argument(self):
        assert read_text_input(text="inline text", file=None) == "inline text"

    def test_read_text_input_from_file(self, tmp_path: Path):
        input_file = tmp_path / "input.txt"
        input_file.write_text("text from a file")
        assert read_text_input(text=None, file=input_file) == "text from a file"

    def test_read_text_input_rejects_both(self, tmp_path: Path):
        input_file = tmp_path / "input.txt"
        input_file.write_text("text from a file")
        with pytest.raises(typer.BadParameter):
            read_text_input(text="inline text", file=input_file)

    def test_read_text_input_rejects_neither(self):
        with pytest.raises(typer.BadParameter):
            read_text_input(text=None, file=None)

    def test_pdf_envelope(self, tmp_path: Path):
        pdf = tmp_path / "invoice.pdf"
        payload = b"%PDF-1.4 hello"
        pdf.write_bytes(payload)
        envelope = build_document_input(pdf)
        assert envelope["concept"] == "Document"
        content = envelope["content"]
        assert content["filename"] == "invoice.pdf"
        assert content["mime_type"] == "application/pdf"
        expected = base64.b64encode(payload).decode("ascii")
        assert content["url"] == f"data:application/pdf;base64,{expected}"

    def test_unknown_extension_falls_back_to_octet_stream(self, tmp_path: Path):
        blob = tmp_path / "data.unknownext"
        blob.write_bytes(b"\x00\x01\x02")
        envelope = build_document_input(blob)
        assert envelope["content"]["mime_type"] == "application/octet-stream"

    def test_missing_file_raises(self, tmp_path: Path):
        with pytest.raises(FileNotFoundError):
            build_document_input(tmp_path / "nope.pdf")
