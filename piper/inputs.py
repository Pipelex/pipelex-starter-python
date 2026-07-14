"""Build the inputs a pipe run is given — shared by every execution mode.

Input encoding is orthogonal to *how* a run is executed, so it lives here rather
than in one of the mode packages (`piper/blocking`, `piper/attended`,
`piper/detached`), which never share lifecycle code with each other.

Two shapes cover the demos:

- `read_text_input()` — a text argument or a `--file` pointing at one.
- `build_document_input()` — a local file, base64-encoded into a `data:` URL and
  wrapped in the `Document` envelope the API expects: `{"concept": "Document",
  "content": {"url": ..., "filename": ..., "mime_type": ...}}`. The API decodes
  it server-side and uploads it to storage, so the CLI never has to host the file
  itself. This mirrors `buildDocumentInput` in the JS starter's `fileEncoding.ts`.
"""

import base64
import mimetypes
from pathlib import Path
from typing import Any

import typer

DEFAULT_MIME_TYPE = "application/octet-stream"


def read_text_input(*, text: str | None, file: Path | None) -> str:
    """Resolve a text input given inline as an argument or via `--file` — exactly one of the two.

    Raises:
        typer.BadParameter: both were given, or neither was.
    """
    if text is not None and file is not None:
        msg = "Give the text either as an argument or via --file, not both."
        raise typer.BadParameter(msg)
    if file is not None:
        return file.read_text()
    if text is not None:
        return text
    msg = "Give the text to process as an argument, or point --file at a text file."
    raise typer.BadParameter(msg)


def build_document_input(path: Path) -> dict[str, Any]:
    """Read a file from disk and build its `Document` input envelope.

    The bytes are base64-encoded into a `data:` URL; the MIME type is guessed
    from the extension (falling back to `application/octet-stream`).

    Raises:
        FileNotFoundError: `path` does not point at a readable file.
    """
    data = path.read_bytes()
    mime_type = mimetypes.guess_type(path.name)[0] or DEFAULT_MIME_TYPE
    encoded = base64.b64encode(data).decode("ascii")
    data_url = f"data:{mime_type};base64,{encoded}"
    return {
        "concept": "Document",
        "content": {"url": data_url, "filename": path.name, "mime_type": mime_type},
    }
