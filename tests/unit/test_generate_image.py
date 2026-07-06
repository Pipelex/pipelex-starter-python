import pytest
from pipelex_sdk.runs import RunResults
from pydantic import ValidationError

from my_project.examples.generate_image import parse

IMAGE_CONTENT = {
    "url": "pipelex-storage://runs/abc/image.png",
    "public_url": "https://cdn.example.com/image.png",
    "mime_type": "image/png",
    "caption": "A watercolor fox",
}


class TestGenerateImageParse:
    def test_parse_main_stuff(self):
        results = RunResults(pipeline_run_id="run-1", main_stuff=IMAGE_CONTENT)
        image = parse(results)
        assert image.url == "pipelex-storage://runs/abc/image.png"
        assert image.public_url == "https://cdn.example.com/image.png"
        assert image.mime_type == "image/png"
        assert image.caption == "A watercolor fox"

    def test_parse_url_only(self):
        results = RunResults(pipeline_run_id="run-2", main_stuff={"url": "https://example.com/i.png"})
        image = parse(results)
        assert image.url == "https://example.com/i.png"
        assert image.public_url is None

    def test_parse_missing_url_raises(self):
        results = RunResults(pipeline_run_id="run-3", main_stuff={"caption": "no url here"})
        with pytest.raises(ValidationError):
            parse(results)
