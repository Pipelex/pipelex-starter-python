"""Offline gates for the generated typed clients (`piper/generated/`).

Everything here runs with no `pipelex` install, no API key and no network, so `tests-check.yml`
runs all of it: the generated models must import, still match their `codegen.lock` byte for byte,
round-trip their own serialization, and stay aligned with the inputs their bundles declare.

The drift gate is `pipelex_sdk.codegen_check.run_codegen_check` — the SDK's mirror of what
`pipelex codegen check` does, over the same bytes and the same lock format, reached through the
dependency this starter already has. It compares each artifact's whole body against the hash its
`codegen.lock` records, so a regenerated model whose field types, defaults or docstrings moved
fails here even when every name it exports stayed the same.
"""

import tomllib
from pathlib import Path
from typing import Any

import pytest
from pipelex_sdk.codegen_check import run_codegen_check
from pipelex_sdk.codegen_lock import CODEGEN_LOCK_FILENAME, load_lock

from piper.generated.extract_entities.models import ExtractedEntities
from piper.generated.generate_image.models import Image
from piper.generated.summarize_pdf.models import DocumentSummary

REPO_ROOT = Path(__file__).parent.parent.parent
# One string per path, the package name followed by a slash: the `/bootstrap` skill rewrites
# `piper/` to the project's package name, and only a slash-followed occurrence is read as the
# package form. Split into `"piper" / "methods"` it would be read as the distribution name.
METHODS_DIR = REPO_ROOT / "piper/methods"
GENERATED_ROOT = REPO_ROOT / "piper/generated"


def discover_method_dirs() -> list[str]:
    """The methods, read off the filesystem exactly as `scripts/codegen.py` discovers them.

    Derived rather than listed, so a method added under `piper/methods/` is gated by the next test
    run instead of waiting for somebody to remember a second list.
    """
    return sorted(path.name for path in METHODS_DIR.iterdir() if path.is_dir() and any(path.rglob("*.mthds")))


def generated_dir_for(method_dir: str) -> Path:
    """The generated package a method projects into — the same dash-to-underscore mapping codegen applies."""
    return GENERATED_ROOT / method_dir.replace("-", "_")


# method dir -> the input names every mode CLI passes for that method (the three modes are
# symmetric on inputs, which `test_mode_symmetry.py` guards). Written by hand on purpose: this is
# the CLI's half of the contract, and deriving it from the bundle would leave the bundle compared
# against itself. It cannot go stale silently — `test_every_method_declares_its_cli_inputs` holds
# it against the methods actually on disk.
CLI_INPUTS: dict[str, set[str]] = {
    "extract-entities": {"text"},
    "summarize-pdf": {"document"},
    "generate-image": {"image_prompt"},
}


class TestGeneratedClients:
    @pytest.mark.parametrize("method_dir", discover_method_dirs())
    def test_generated_tree_matches_its_lock(self, method_dir: str):
        """Each generated tree still matches its `codegen.lock`, artifact body by artifact body.

        This is the gate a key-name comparison cannot be: the lock records a SHA-256 of every
        artifact's body below its stamp, so a stale tree, a hand edit, a deleted artifact or a
        stale one left behind is a failure here, offline and in CI.

        What it deliberately does not prove is that the tree matches what the *method* resolves to
        today — answering that needs the engine, which is why `make codegen` (write-if-changed,
        then a clean `git diff`) stays the guard for a bundle edited and never regenerated.
        """
        report = run_codegen_check(root=generated_dir_for(method_dir))
        assert report.lock_found, f"{method_dir}: no {CODEGEN_LOCK_FILENAME} — run `make codegen`"
        drifts = "\n".join(f"  {drift.path}: {drift.category} — {drift.detail}" for drift in report.drifts)
        assert report.is_current, f"{method_dir}: the generated tree has drifted from its lock — run `make codegen`\n{drifts}"

    @pytest.mark.parametrize("method_dir", discover_method_dirs())
    def test_generated_artifacts_stamped_and_locked(self, method_dir: str):
        """Each generated client carries the codegen stamp header, and its lock tracks the module.

        The drift check above verifies whatever the lock tracks; this one says the lock tracks the
        module at all, so an empty artifact set cannot pass as a tree in sync with itself.
        """
        generated_dir = generated_dir_for(method_dir)
        models_text = (generated_dir / "models.py").read_text()
        assert models_text.startswith("# >>> pipelex-codegen-stamp >>>")
        lock = load_lock(generated_dir / CODEGEN_LOCK_FILENAME)
        assert lock is not None
        assert "models.py" in lock.paths()

    def test_every_method_declares_its_cli_inputs(self):
        """Every method on disk has a `CLI_INPUTS` entry, and every entry names a method that exists."""
        assert set(CLI_INPUTS) == set(discover_method_dirs())

    @pytest.mark.parametrize("method_dir", list(CLI_INPUTS))
    def test_bundle_declares_exactly_the_cli_inputs(self, method_dir: str):
        """The method's bundle declares exactly the inputs the CLI passes for it — an input renamed,
        added or dropped in `main.mthds` that `piper/<mode>/cli.py` does not follow fails here, offline.

        Read from the bundle itself (`.mthds` is TOML, so `tomllib` reads it), not from a generated
        artifact: the check then holds the moment the bundle is edited, with no regeneration in between.
        """
        expected_inputs = CLI_INPUTS[method_dir]
        with (METHODS_DIR / method_dir / "main.mthds").open("rb") as handle:
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
