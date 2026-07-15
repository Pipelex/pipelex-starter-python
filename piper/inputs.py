"""Build the inputs a pipe run is given — shared by every execution mode.

Input encoding is orthogonal to *how* a run is executed, so it lives here rather
than in one of the mode packages (`piper/blocking`, `piper/attended`,
`piper/detached`), which never share lifecycle code with each other.

Two shapes cover the demos:

- `read_text_input()` — a text argument, a `--file` pointing at one, or (when you
  give neither) a built-in sample, so every demo runs with zero arguments.
- `build_document_input()` — a local file, base64-encoded into a `data:` URL and
  wrapped in the `Document` envelope the API expects: `{"concept": "Document",
  "content": {"url": ..., "filename": ..., "mime_type": ...}}`. The API decodes
  it server-side and uploads it to storage, so the CLI never has to host the file
  itself. This mirrors `buildDocumentInput` in the JS starter's `fileEncoding.ts`.

The built-in samples let a fresh clone show a working result before you have any
input of your own; they are also the values the README documents.
"""

import base64
import mimetypes
from pathlib import Path
from typing import Any, NamedTuple

import typer

DEFAULT_MIME_TYPE = "application/octet-stream"

# Sample inputs — the zero-argument fallback for each demo (also the README's examples).
SAMPLE_ENTITIES_TEXT = "Alice from Acme met Bob on May 3rd, 2026."
SAMPLE_IMAGE_PROMPT = "a fox reading under a tree"
SAMPLE_INVOICE = Path(__file__).parent.parent / "samples" / "sample-invoice.pdf"


class TextInput(NamedTuple):
    """A resolved text input, plus whether it came from the built-in sample.

    The `is_sample` flag lets a command tell the user it filled in the input for
    them (so the result isn't mysterious) without the input helper owning a console.
    """

    text: str
    is_sample: bool


def read_text_input(*, text: str | None, file: Path | None, sample: str) -> TextInput:
    """Resolve the text to process: an argument, a `--file`, or the built-in `sample`.

    An explicit argument or `--file` wins; with neither, `sample` is used so the
    command runs with no arguments at all.

    Raises:
        typer.BadParameter: both an argument and `--file` were given, or `--file`
            does not point at a readable file.
    """
    if text is not None and file is not None:
        msg = "Give the text either as an argument or via --file, not both."
        raise typer.BadParameter(msg)
    if file is not None:
        if not file.is_file():
            msg = f"No such file: {file}"
            raise typer.BadParameter(msg)
        return TextInput(text=file.read_text(), is_sample=False)
    if text is not None:
        return TextInput(text=text, is_sample=False)
    return TextInput(text=sample, is_sample=True)


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
