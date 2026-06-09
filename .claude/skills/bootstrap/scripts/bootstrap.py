#!/usr/bin/env python3
"""Rename the pipelex-starter-python template placeholders to a real project.

This is the deterministic engine behind the `/bootstrap` skill. It does the
mechanical, error-prone part — renaming the package directory, the e2e test
file, and substituting four different spellings of the project name across the
code, config, docs, and license — so the skill (and the human) can focus on
collecting good inputs and verifying the result.

Why a script instead of a pile of Edit calls: the same name appears in four
forms (dash / underscore / Title Case / CamelCase) scattered across many files,
plus two filesystem renames. Doing that by hand once is fine; doing it reliably
every time someone clones the template is exactly what a script is for. It is
also safe to run with --dry-run, which is what makes it testable.

The script only transforms files. It does NOT touch git, run `uv lock`, run the
checks, or remove the bootstrap skill — the SKILL.md orchestrates those so each
step stays reviewable and the script stays a pure, idempotent transform.
"""

from __future__ import annotations

import argparse
import datetime
import keyword
import os
import re
import shutil
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path

# The template's placeholders, in their four spellings. Everything the script
# does is ultimately "turn these into the user's chosen name".
TEMPLATE_DIST = "my-project"  # distribution name (pyproject [project].name, PyPI-style)
TEMPLATE_PACKAGE = "my_project"  # importable package / directory name
TEMPLATE_TITLE = "My Project"  # human-facing display name (README H1)
TEMPLATE_CAMEL = "MyProject"  # only ever seen inside the test class TestMyProject

PACKAGE_RE = re.compile(r"^[a-z][a-z0-9_]*$")
# PEP 503/508 distribution name: alphanumerics separated by single '.', '-' or
# '_', starting and ending with an alphanumeric. uv/packaging reject anything
# else (e.g. a name with spaces), so we validate before writing [project].name.
DIST_RE = re.compile(r"^[A-Za-z0-9](?:[A-Za-z0-9._-]*[A-Za-z0-9])?$")


@dataclass(frozen=True)
class Names:
    """The four spellings of the new project name, derived from one another."""

    dist: str  # e.g. "invoice-extractor"
    package: str  # e.g. "invoice_extractor"
    title: str  # e.g. "Invoice Extractor"
    camel: str  # e.g. "InvoiceExtractor"


def camel_from_package(package: str) -> str:
    return "".join(part.capitalize() for part in package.split("_") if part)


def title_from_package(package: str) -> str:
    return " ".join(part.capitalize() for part in package.split("_") if part)


def validate_package(package: str) -> None:
    """A package name has to be a real importable identifier, or nothing downstream works."""
    if not PACKAGE_RE.match(package):
        sys.exit(
            f"Invalid package name {package!r}: use lowercase letters, digits and underscores, starting with a letter (e.g. 'invoice_extractor')."
        )
    if keyword.iskeyword(package):
        sys.exit(f"Invalid package name {package!r}: it is a Python keyword.")


def validate_dist(dist: str) -> None:
    """The distribution name lands in [project].name, which uv/packaging validate.

    --package is validated separately, and the default dist (package with
    underscores swapped for dashes) is always valid — but --dist is an explicit
    override that would otherwise reach pyproject.toml unchecked, so an input
    like 'bad dist name' must be rejected here rather than failing `uv lock` on
    the generated project.
    """
    if not DIST_RE.match(dist):
        sys.exit(
            f"Invalid distribution name {dist!r}: use letters, digits, '.', '-' or '_', "
            "starting and ending with a letter or digit, no spaces (e.g. 'invoice-extractor')."
        )


# --------------------------------------------------------------------------- #
# License handling
# --------------------------------------------------------------------------- #

PROPRIETARY_LICENSE = """Copyright (c) {year} {holder}

All rights reserved.

This software and its associated documentation (the "Software") are the
proprietary and confidential property of {holder}. Unauthorized copying,
distribution, modification, public display, or use of the Software, in whole or
in part, via any medium, is strictly prohibited without the express prior
written permission of {holder}.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY, FITNESS
FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT.
"""

OTHER_LICENSE = """Copyright (c) {year} {holder}

This project is licensed under the {spdx} license.

Replace this file with the full text of the {spdx} license — you can obtain it
from https://spdx.org/licenses/{spdx}.html
"""


@dataclass(frozen=True)
class License:
    """The chosen license, in the forms the three call-sites need.

    `kind` drives the LICENSE body, `spdx` is the value for pyproject's
    `license = "..."` field (which `uv lock --locked` validates, so a proprietary
    project needs a `LicenseRef-` expression rather than free text), and
    `holder`/`year` fill the copyright notice.
    """

    kind: str  # "mit" | "proprietary" | "other"
    spdx: str
    holder: str | None
    year: int


def resolve_license(value: str, holder: str | None, year: int) -> License:
    norm = value.strip().lower()
    if norm in ("", "mit"):
        return License(kind="mit", spdx="MIT", holder=holder, year=year)
    if norm in ("proprietary", "all-rights-reserved", "all rights reserved", "licenseref-proprietary"):
        return License(kind="proprietary", spdx="LicenseRef-Proprietary", holder=holder, year=year)
    # Anything else is treated as a raw SPDX id (e.g. Apache-2.0). We set the
    # field and write a stub, but can't author arbitrary license text for them.
    return License(kind="other", spdx=value.strip(), holder=holder, year=year)


# --------------------------------------------------------------------------- #
# File transforms
# --------------------------------------------------------------------------- #


def toml_str(value: str) -> str:
    """Render value as a TOML basic string: surrounding quotes plus escaping.

    User-supplied fields (description, author name/email, license, repo URL) are
    written straight into pyproject.toml, so a value containing a double-quote or
    backslash — e.g. `Use "AI" agents` — would otherwise produce invalid TOML and
    break `uv lock`/checks on the generated project. We escape backslash first
    (so it doesn't double-escape the sequences added afterwards), then the quote
    and the control characters TOML basic strings forbid bare.
    """
    escaped = value.replace("\\", "\\\\").replace('"', '\\"').replace("\n", "\\n").replace("\r", "\\r").replace("\t", "\\t")
    return f'"{escaped}"'


def apply_name_tokens(text: str, names: Names) -> str:
    """Substitute every spelling of the template name with the new one.

    The four tokens are mutually non-overlapping (no token is a substring of
    another — "MyProject" only ever appears inside "TestMyProject", which we
    handle as its own token), so the order of replacement does not matter.
    """
    text = text.replace(f"Test{TEMPLATE_CAMEL}", f"Test{names.camel}")
    text = text.replace(TEMPLATE_TITLE, names.title)
    text = text.replace(TEMPLATE_PACKAGE, names.package)
    text = text.replace(TEMPLATE_DIST, names.dist)
    return text


def transform_pyproject(text: str, names: Names, opts: "Options") -> str:
    # Description: a real one-liner beats "Replace this with your project description".
    text = text.replace(
        'description = "Replace this with your project description"',
        f"description = {toml_str(opts.description)}",
    )

    # License field: uv validates this against SPDX on `uv lock --locked`, so a
    # proprietary project needs a `LicenseRef-` expression, not free text.
    if opts.lic.spdx != "MIT":
        text = text.replace('license = "MIT"', f"license = {toml_str(opts.lic.spdx)}")

    # Author: the line ships commented out. Fill in whatever we were given
    # (name, email, or both) and uncomment it; otherwise leave the template comment.
    author_inner = None
    if opts.author_name and opts.author_email:
        author_inner = f"{{ name = {toml_str(opts.author_name)}, email = {toml_str(opts.author_email)} }}"
    elif opts.author_name:
        author_inner = f"{{ name = {toml_str(opts.author_name)} }}"
    elif opts.author_email:
        author_inner = f"{{ email = {toml_str(opts.author_email)} }}"
    if author_inner:
        text = text.replace(
            '# authors = [{ name = "Your Name", email = "your.email@example.com" }]',
            f"authors = [{author_inner}]",
        )

    # Repository URL: if given, drop in the real URL and remove the reminder
    # comment. If not, the token pass below rewrites my-project -> dist and we
    # leave the `yourusername` placeholder + reminder comment in place on purpose.
    if opts.repo_url:
        # Double backslashes so re.sub's replacement mini-language treats any
        # backslash from toml_str() as literal rather than a group reference.
        repository_line = f"Repository = {toml_str(opts.repo_url)}".replace("\\", "\\\\")
        text = re.sub(
            r'Repository = "[^"]*"(?:\s*#.*)?',
            repository_line,
            text,
        )

    return apply_name_tokens(text, names)


def strip_template_block(text: str) -> str:
    """Remove the README's template-only preamble (the 'Use this template' block).

    The block runs from the `*Replace "My Project" ...*` italic line down to the
    `---` rule that closes it, just before `## Getting Started`. We anchor on
    those two markers rather than line numbers so edits to the prose above don't
    break us.
    """
    lines = text.splitlines()
    start = next((i for i, ln in enumerate(lines) if ln.startswith('*Replace "')), None)
    if start is None:
        return text  # already stripped (e.g. re-run) — nothing to do
    end = next((j for j in range(start + 1, len(lines)) if lines[j].strip() == "---"), None)
    if end is None:
        return text
    del lines[start : end + 1]
    out = "\n".join(lines)
    if text.endswith("\n"):
        out += "\n"
    # Collapse the blank-line gap left behind so the H1 sits right above "## Getting Started".
    return re.sub(r"\n{3,}", "\n\n", out)


def transform_readme(text: str, names: Names, opts: "Options") -> str:
    if opts.clean:
        text = strip_template_block(text)

    # Clone instructions: point them at the real repo if we have one. A common
    # GitHub URL already ends in `.git`, so strip it before re-appending (no
    # `.git.git`) and before deriving the directory name (`cd repo`, not `cd repo.git`).
    if opts.repo_url:
        bare_url = opts.repo_url.removesuffix(".git")
        repo_name = bare_url.rsplit("/", 1)[-1]
        text = text.replace(
            "git clone https://github.com/yourusername/your-repo-name.git",
            f"git clone {bare_url}.git",
        )
        text = text.replace("cd your-repo-name", f"cd {repo_name}")
    else:
        text = text.replace("your-repo-name", names.dist)

    # License line: reflect the chosen license in the README's License section.
    if opts.lic.kind == "proprietary":
        text = text.replace(
            "This project is licensed under the [MIT license](LICENSE).",
            "This project is proprietary — all rights reserved. See the [LICENSE](LICENSE) file.",
        )
    elif opts.lic.spdx != "MIT":
        text = text.replace("[MIT license](LICENSE)", f"[{opts.lic.spdx} license](LICENSE)")

    return apply_name_tokens(text, names)


def transform_license(text: str, opts: "Options") -> str:
    lic = opts.lic
    if lic.kind == "mit":
        # Keep the MIT text; only refresh the copyright line when we have a
        # holder to put there (don't silently bump the template holder's year).
        if lic.holder:
            text = re.sub(
                r"Copyright \(c\) \d{4} .*",
                f"Copyright (c) {lic.year} {lic.holder}",
                text,
                count=1,
            )
        return text
    holder = lic.holder or "<COPYRIGHT HOLDER>"
    if not lic.holder:
        print("warning: no --license-holder given; wrote a placeholder into LICENSE.", file=sys.stderr)
    if lic.kind == "proprietary":
        return PROPRIETARY_LICENSE.format(year=lic.year, holder=holder)
    print(
        f"warning: wrote a LICENSE stub for '{lic.spdx}'. Replace it with the full {lic.spdx} license text.",
        file=sys.stderr,
    )
    return OTHER_LICENSE.format(year=lic.year, holder=holder, spdx=lic.spdx)


def transform_generic(text: str, names: Names) -> str:
    return apply_name_tokens(text, names)


# --------------------------------------------------------------------------- #
# Filesystem renames
# --------------------------------------------------------------------------- #


def git_available(root: Path) -> bool:
    return (root / ".git").exists() and shutil.which("git") is not None


def move(root: Path, src: Path, dst: Path, opts: "Options") -> None:
    """Rename src -> dst, using `git mv` when possible so history follows the file."""
    rel_src = src.relative_to(root)
    rel_dst = dst.relative_to(root)
    if opts.dry_run:
        print(f"  rename  {rel_src}  ->  {rel_dst}")
        return
    if opts.use_git:
        result = subprocess.run(
            ["git", "-C", str(root), "mv", str(rel_src), str(rel_dst)],
            capture_output=True,
            text=True,
        )
        if result.returncode == 0:
            print(f"  renamed (git) {rel_src} -> {rel_dst}")
            return
        print(f"  git mv failed ({result.stderr.strip()}); falling back to plain rename")
    os.rename(src, dst)
    print(f"  renamed {rel_src} -> {rel_dst}")


# --------------------------------------------------------------------------- #
# Orchestration
# --------------------------------------------------------------------------- #


@dataclass(frozen=True)
class Options:
    description: str
    author_name: str | None
    author_email: str | None
    repo_url: str | None
    lic: License
    clean: bool
    dry_run: bool
    use_git: bool


def gather_target_files(root: Path, names: Names) -> list[Path]:
    """The explicit set of files that may contain the name. Kept narrow on
    purpose: we never sweep .venv, uv.lock, .git, .github or .pipelex traces."""
    candidates: list[Path] = [
        root / "pyproject.toml",
        root / "README.md",
        root / "CLAUDE.md",
        root / "LICENSE",
    ]
    pkg_dir = root / names.package
    candidates += sorted(pkg_dir.rglob("*.py"))
    candidates += sorted(pkg_dir.rglob("*.mthds"))
    candidates += sorted((root / "tests").rglob("*.py"))
    seen: set[Path] = set()
    files: list[Path] = []
    for path in candidates:
        if path.exists() and path.is_file() and path not in seen:
            seen.add(path)
            files.append(path)
    return files


def write_file(path: Path, root: Path, original: str, updated: str, opts: Options) -> bool:
    if original == updated:
        return False
    rel = path.relative_to(root)
    if opts.dry_run:
        print(f"  edit    {rel}")
    else:
        path.write_text(updated, encoding="utf-8")
        print(f"  edited  {rel}")
    return True


def transform_for(path: Path, text: str, names: Names, opts: Options) -> str:
    name = path.name
    if name == "pyproject.toml":
        return transform_pyproject(text, names, opts)
    if name == "README.md":
        return transform_readme(text, names, opts)
    if name == "LICENSE":
        return transform_license(text, opts)
    return transform_generic(text, names)


def run(root: Path, names: Names, opts: Options) -> None:
    # Guard: confirm this actually is the unbootstrapped template before we
    # start renaming things. Cheap check, saves a confusing half-applied state.
    pyproject = root / "pyproject.toml"
    if not pyproject.exists():
        sys.exit(f"No pyproject.toml found in {root} — run this from the project root.")
    pyproject_text = pyproject.read_text(encoding="utf-8")
    if f'name = "{TEMPLATE_DIST}"' not in pyproject_text:
        print(
            f'warning: pyproject.toml does not contain name = "{TEMPLATE_DIST}". This repo may already be bootstrapped; proceeding anyway.',
            file=sys.stderr,
        )

    print(f"Bootstrapping template -> {names.title!r}")
    print(f"  dist={names.dist}  package={names.package}  camel={names.camel}")
    if opts.dry_run:
        print("  (dry run — no files will be modified)")
    print()

    # 1. Renames first, so the file transforms below see the final paths.
    print("Renames:")
    old_pkg = root / TEMPLATE_PACKAGE
    new_pkg = root / names.package
    if names.package != TEMPLATE_PACKAGE and old_pkg.is_dir():
        move(root, old_pkg, new_pkg, opts)
    old_test = root / "tests" / "e2e" / f"test_{TEMPLATE_PACKAGE}.py"
    new_test = root / "tests" / "e2e" / f"test_{names.package}.py"
    if names.package != TEMPLATE_PACKAGE and old_test.exists():
        move(root, old_test, new_test, opts)
    if opts.use_git and not opts.dry_run and names.package != TEMPLATE_PACKAGE:
        print("  note: git mv stages the renames; the content edits below are left unstaged.")
    print()

    # During a dry run the renames did not actually happen, so read the file
    # list from the original paths to still show a meaningful plan.
    scan_names = names if not opts.dry_run else Names(names.dist, TEMPLATE_PACKAGE, names.title, names.camel)

    # 2. Content edits.
    print("Edits:")
    changed = 0
    for path in gather_target_files(root, scan_names):
        original = path.read_text(encoding="utf-8")
        updated = transform_for(path, original, names, opts)
        if write_file(path, root, original, updated, opts):
            changed += 1
    if changed == 0:
        print("  (no content changes)")
    print()
    print(f"Done. {changed} file(s) {'would be ' if opts.dry_run else ''}edited.")
    if not opts.dry_run:
        print("\nNext: regenerate the lock file (uv.lock pins the project name) and run the checks:")
        print("  make li && make agent-check && make agent-test")
        print("Then review with `git status` and `git diff` before committing.")


def parse_args(argv: list[str]) -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Replace pipelex-starter-python template placeholders.")
    p.add_argument("--package", required=True, help="Importable package name, underscores (e.g. invoice_extractor)")
    p.add_argument("--title", help="Display title (default: derived from --package, e.g. 'Invoice Extractor')")
    p.add_argument("--dist", help="Distribution name, dashes (default: derived from --package)")
    p.add_argument("--description", required=True, help="One-line project description for pyproject.toml")
    p.add_argument("--author-name", help="Author name for pyproject.toml authors field")
    p.add_argument("--author-email", help="Author email for pyproject.toml authors field")
    p.add_argument("--repo-url", help="GitHub repository URL, e.g. https://github.com/acme/invoice-extractor")
    p.add_argument("--license", help="License: 'mit' (default), 'proprietary', or an SPDX id like 'Apache-2.0'")
    p.add_argument("--license-holder", help="Copyright holder for the LICENSE notice")
    p.add_argument("--license-year", type=int, help="Copyright year for the LICENSE notice (default: current year)")
    p.add_argument("--clean", action="store_true", help="Strip the README template-only block")
    p.add_argument("--dry-run", action="store_true", help="Print the plan without modifying anything")
    p.add_argument("--root", default=".", help="Project root (default: current directory)")
    return p.parse_args(argv)


def main(argv: list[str]) -> None:
    args = parse_args(argv)
    package = args.package.strip()
    validate_package(package)
    dist = (args.dist or package.replace("_", "-")).strip()
    validate_dist(dist)
    title = (args.title or title_from_package(package)).strip()
    names = Names(dist=dist, package=package, title=title, camel=camel_from_package(package))

    root = Path(args.root).resolve()
    license_year = args.license_year or datetime.date.today().year
    lic = resolve_license(
        args.license or "mit",
        (args.license_holder or "").strip() or None,
        license_year,
    )
    opts = Options(
        description=args.description.strip(),
        author_name=(args.author_name or "").strip() or None,
        author_email=(args.author_email or "").strip() or None,
        repo_url=(args.repo_url or "").strip().rstrip("/") or None,
        lic=lic,
        clean=args.clean,
        dry_run=args.dry_run,
        use_git=git_available(root),
    )
    run(root, names, opts)


if __name__ == "__main__":
    main(sys.argv[1:])
