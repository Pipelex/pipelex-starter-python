"""Smoke tests for the generated typed clients (`piper/generated/`).

Everything here runs offline: the generated models must import, carry the codegen stamp + lock,
round-trip their own serialization, and stay aligned with the input templates the CLI ships.
The cryptographic drift check is `make codegen-check` (offline, against each `codegen.lock`);
these tests are the CI-runnable floor that needs no pipelex CLI at all.
"""

import json
from pathlib import Path

import pytest

from piper.generated.extract_entities.models import ExtractedEntities
from piper.generated.generate_image.models import Image
from piper.generated.summarize_pdf.models import DocumentSummary

PIPER_DIR = Path(__file__).parent.parent.parent / "piper"

# method dir -> (generated package dir, the input names piper/cli.py dispatches for that method)
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
    def test_input_template_matches_cli_dispatch(self, method_dir: str):
        """The committed inputs template names exactly the inputs the CLI passes for the method —
        a regenerated template that drifted from `piper/cli.py`'s dispatch fails here, offline.
        """
        expected_inputs = METHODS[method_dir][1]
        template_path = PIPER_DIR / "methods" / method_dir / "inputs.template.json"
        template = json.loads(template_path.read_text())
        assert set(template.keys()) == expected_inputs

    def test_generated_models_round_trip(self):
        """Each generated model validates a wire-shaped payload and round-trips its own dump."""
        entities = ExtractedEntities(people=["Marie Curie"], orgs=["University of Paris"], dates=["1906"])
        assert ExtractedEntities.model_validate(entities.model_dump()) == entities
        summary = DocumentSummary(title="Q3 Report", doc_type="report", key_points=["Revenue grew"])
        assert DocumentSummary.model_validate(summary.model_dump()) == summary
        image = Image(url="pipelex-storage://runs/abc/image.png", public_url="https://cdn.example.com/image.png")
        assert Image.model_validate(image.model_dump()) == image
