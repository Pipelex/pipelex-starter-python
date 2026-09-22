import pytest
from dotenv import load_dotenv
from pipelex_sdk.artifact_models import ArtifactScope, DownloadArtifactsResult, DownloadedArtifact
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
    mocker.patch("widget.inputs.PipelexAPIClient", return_value=async_cm)
    return STUB_UPLOAD_URI


# What the offline `stub_download` fixture pretends the hosted artifact stack brought down.
STUB_ARTIFACT_URI = "pipelex-storage://stub-run/cat.png"
STUB_ARTIFACT_PATH = "/tmp/stub-run/cat.png"


@pytest.fixture
def stub_download(mocker: MockerFixture) -> str:
    """Patch the hosted artifact download so CLI tests over a file-producing method stay offline.

    `artifacts.download_produced_files` short-circuits offline when the output references no stored
    file, which is why the text demos need nothing here. Past that short-circuit it opens a real
    `PipelexAPIClient`, so any test whose fixture output carries a `pipelex-storage://` reference —
    which is the shape the hosted runtime really returns for an image — must take this fixture or
    it will reach for the network. Returns the path the stub pretends it wrote, for assertions.
    """
    artifact = DownloadedArtifact(uri=STUB_ARTIFACT_URI, path=STUB_ARTIFACT_PATH, content_type="image/png", size=3)
    result = DownloadArtifactsResult(scope=ArtifactScope.MAIN_STUFF, artifacts=[artifact], saved_paths=[STUB_ARTIFACT_PATH], all_saved=True)
    fake_client = mocker.AsyncMock()
    fake_client.download_artifacts.return_value = result
    async_cm = mocker.MagicMock()
    async_cm.__aenter__ = mocker.AsyncMock(return_value=fake_client)
    async_cm.__aexit__ = mocker.AsyncMock(return_value=None)
    mocker.patch("widget.artifacts.PipelexAPIClient", return_value=async_cm)
    return STUB_ARTIFACT_PATH
