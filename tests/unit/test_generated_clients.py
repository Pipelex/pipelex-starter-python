"""Smoke tests for the generated typed clients (`piper/generated/`).

Everything here runs offline: the generated models must import, carry the codegen stamp + lock,
round-trip their own serialization, and stay aligned with the inputs their bundles declare.
The cryptographic drift check is `make codegen-check` (offline, against each `codegen.lock`);
these tests are the CI-runnable floor that needs no pipelex CLI at all.
"""

import tomllib
from pathlib import Path
from typing import Any

import pytest

from piper.generated.extract_entities.models import ExtractedEntities
from piper.generated.generate_image.models import Image
from piper.generated.summarize_pdf.models import DocumentSummary

PIPER_DIR = Path(__file__).parent.parent.parent / "piper"

# method dir -> (generated package dir, the input names every mode CLI passes for that method —
# the three modes are symmetric on inputs, which `test_mode_symmetry.py` guards)
METHODS = {
    "extract-entities": ("extract_entities", {"text"}),
    "summarize-pdf": ("summarize_pdf", {"document"}),
    "generate-image": ("generate_image", {"image_prompt"}),
}


class TestGeneratedClients:
    @pytest.mark.parametrize("method_dir", list(METHODS))
    def test_generated_artifacts_stamped_and_locked(self, method_dir: str):
        """Each generated client carries the codegen stamp header and a sibling codegen.lock."""
        package_dir, _ = METHODS[method_dir]
        generated_dir = PIPER_DIR / "generated" / package_dir
        models_text = (generated_dir / "models.py").read_text()
        assert models_text.startswith("# >>> pipelex-codegen-stamp >>>")
        assert "crate_fingerprint:" in models_text
        lock_text = (generated_dir / "codegen.lock").read_text()
        assert 'path = "models.py"' in lock_text

    @pytest.mark.parametrize("method_dir", list(METHODS))
    def test_bundle_declares_exactly_the_cli_inputs(self, method_dir: str):
        """The method's bundle declares exactly the inputs the CLI passes for it — an input renamed,
        added or dropped in `main.mthds` that `piper/<mode>/cli.py` does not follow fails here, offline.

        Read from the bundle itself (`.mthds` is TOML, so `tomllib` reads it), not from a generated
        artifact: the check then holds the moment the bundle is edited, with no regeneration in between.
        """
        expected_inputs = METHODS[method_dir][1]
        with (PIPER_DIR / "methods" / method_dir / "main.mthds").open("rb") as handle:
            bundle: dict[str, Any] = tomllib.load(handle)
        main_pipe: str = bundle["main_pipe"]
        declared_inputs: dict[str, str] = bundle["pipe"][main_pipe]["inputs"]
        assert set(declared_inputs) == expected_inputs

    def test_generated_models_round_trip(self):
        """Each generated model validates a wire-shaped payload and round-trips its own dump."""
        entities = ExtractedEntities(people=["Marie Curie"], orgs=["University of Paris"], dates=["1906"])
        assert ExtractedEntities.model_validate(entities.model_dump()) == entities
        summary = DocumentSummary(title="Q3 Report", doc_type="report", key_points=["Revenue grew"])
        assert DocumentSummary.model_validate(summary.model_dump()) == summary
        image = Image(url="pipelex-storage://runs/abc/image.png", public_url="https://cdn.example.com/image.png")
        assert Image.model_validate(image.model_dump()) == image
