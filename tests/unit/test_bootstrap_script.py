from __future__ import annotations

import importlib.util
import sys
from importlib.machinery import SourceFileLoader
from pathlib import Path
from typing import Any

import pytest

ROOT = Path(__file__).resolve().parents[2]
BOOTSTRAP_SCRIPT = ROOT / ".claude" / "skills" / "bootstrap" / "scripts" / "bootstrap.py"


def load_bootstrap() -> Any:
    spec = importlib.util.spec_from_file_location("bootstrap_script_under_test", BOOTSTRAP_SCRIPT)
    assert spec is not None
    loader = spec.loader
    assert isinstance(loader, SourceFileLoader)
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    loader.exec_module(module)
    return module


def write_template(root: Path, *, extra_pyproject: str = "") -> None:
    (root / "piper").mkdir()
    (root / "piper" / "blocking").mkdir()
    (root / "tests").mkdir()
    (root / "pyproject.toml").write_text(
        f"""[project]
name = "piper"
description = "Replace this with your project description"
# authors = [{{ name = "Your Name", email = "your.email@example.com" }}]
license = "MIT"

[project.scripts]
piper = "piper.cli:app"

[tool.setuptools]
# piper/methods/*, this packages/package-data block, and the Makefile codegen targets.
packages = [
  "piper",
  "piper.blocking",
  "piper.generated",
  "piper.generated.extract_entities",
]

[tool.setuptools.package-data]
piper = ["py.typed", "methods/*/main.mthds"]
"piper.generated.extract_entities" = ["codegen.lock"]

[tool.ruff]
extend-exclude = [
  "piper/generated",
]

[project.urls]
Repository = "https://github.com/yourusername/piper" # Replace with your repository URL

[tool.mypy]
packages = ["piper"]

[tool.pyright]
include = ["piper", "tests"]
{extra_pyproject}""",
        encoding="utf-8",
    )
    (root / "README.md").write_text("# Piper\n\nRun `piper extract-entities`.\n", encoding="utf-8")
    (root / "CLAUDE.md").write_text("The `piper` CLI lives in `piper/cli.py`.\n", encoding="utf-8")
    (root / "LICENSE").write_text("MIT License\n\nCopyright (c) 2025 Example\n", encoding="utf-8")
    (root / "piper" / "cli.py").write_text('"""The piper CLI."""\n', encoding="utf-8")
    # A mode sub-package: nested dir, and an import of a sibling module to rewrite.
    (root / "piper" / "blocking" / "cli.py").write_text("from piper.inputs import read_text_input\n", encoding="utf-8")
    (root / "tests" / "test_cli.py").write_text("from piper.cli import app\n", encoding="utf-8")


def test_survivor_check_allows_requested_values_containing_piper(tmp_path: Path) -> None:
    bootstrap = load_bootstrap()
    write_template(tmp_path)

    names = bootstrap.Names(dist="piper-tools", package="piper_tools", title="Piper Tools")
    opts = bootstrap.Options(
        description="Build Piper workflows",
        author_name="Piper Team",
        author_email=None,
        repo_url="https://github.com/acme/piper-tools",
        lic=bootstrap.License(kind="mit", spdx="MIT", holder="Piper Team", year=2026),
        clean=False,
        dry_run=True,
        use_git=False,
    )

    bootstrap.run(tmp_path, names, opts)


def test_survivor_check_still_rejects_unhandled_template_tokens(tmp_path: Path) -> None:
    bootstrap = load_bootstrap()
    # A bare `piper` word inside prose (not quoted-exact, not in package position)
    # is a shape the pyproject transform refuses to guess at — it must survive
    # the substitution pass and abort the bootstrap.
    write_template(tmp_path, extra_pyproject='custom = "run piper somewhere"\n')

    names = bootstrap.Names(dist="invoice-extractor", package="invoice_extractor", title="Invoice Extractor")
    opts = bootstrap.Options(
        description="Extract invoice fields",
        author_name=None,
        author_email=None,
        repo_url=None,
        lic=bootstrap.License(kind="mit", spdx="MIT", holder=None, year=2026),
        clean=False,
        dry_run=True,
        use_git=False,
    )

    with pytest.raises(SystemExit) as exc_info:
        bootstrap.run(tmp_path, names, opts)

    assert 'custom = "run piper somewhere"' in str(exc_info.value)
