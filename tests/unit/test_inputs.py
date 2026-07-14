import base64
from pathlib import Path

import pytest

from piper.file_input import build_document_input


class TestBuildDocumentInput:
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
