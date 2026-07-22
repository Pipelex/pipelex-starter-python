import pytest
from dotenv import load_dotenv
from pipelex_sdk.upload import UploadRecord
from pytest_mock import MockerFixture

# Load .env so the Pipelex API client picks up PIPELEX_BASE_URL / PIPELEX_API_KEY
# (the tests marked `pipelex_api` / `inference` reach the hosted API).
load_dotenv()

# The storage URI the offline `stub_upload` fixture pretends the hosted upload returned.
STUB_UPLOAD_URI = "pipelex-storage://stub-upload"


@pytest.fixture
def stub_upload(mocker: MockerFixture) -> str:
    """Patch the hosted file upload so `summarize-pdf` CLI tests stay offline.

    `inputs.upload_document_input` opens a `PipelexAPIClient` and calls `upload_file`; here we
    replace the client with a fake whose `upload_file` returns a fixed `pipelex-storage://` URI.
    The real `build_document_input` still runs, so the envelope keeps the real filename / MIME
    from the path — only the network upload is stubbed. Returns the stub URI for assertions.
    """
    record = UploadRecord(uri=STUB_UPLOAD_URI, filename="stub", content_type="application/octet-stream", size=0)
    fake_client = mocker.AsyncMock()
    fake_client.upload_file.return_value = record
    async_cm = mocker.MagicMock()
    async_cm.__aenter__ = mocker.AsyncMock(return_value=fake_client)
    async_cm.__aexit__ = mocker.AsyncMock(return_value=None)
    mocker.patch("piper.inputs.PipelexAPIClient", return_value=async_cm)
    return STUB_UPLOAD_URI
