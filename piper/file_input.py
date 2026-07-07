"""Turn a local file into a Pipelex `Document` input envelope.

The hosted API accepts a file input as `{"concept": "Document", "content":
{"url": ..., "filename": ..., "mime_type": ...}}`, where `url` may be a base64
`data:` URL. The API decodes it server-side and uploads it to storage, so the
CLI never has to host the file itself. This mirrors `buildDocumentInput` in the
JS starter's `fileEncoding.ts`.
"""

import base64
import mimetypes
from pathlib import Path
from typing import Any

DEFAULT_MIME_TYPE = "application/octet-stream"


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
