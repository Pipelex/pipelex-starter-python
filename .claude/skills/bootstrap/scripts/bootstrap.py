#!/usr/bin/env python3
"""Rename the pipelex-starter-python template placeholders to a real project.

This is the deterministic engine behind the `/bootstrap` skill. It does the
mechanical, error-prone part — renaming the package directory and substituting
the project name (in its dist, package, and title forms) across the code,
config, docs, and license — so the skill (and the human) can focus on collecting
good inputs and verifying the result.

Why a script instead of a pile of Edit calls: the placeholder `piper` is a
single token that must become two different targets depending on context — the
dash-form distribution / CLI name in command positions, the underscore-form
package name in imports and paths — plus the `Piper` title and one filesystem
rename. Getting that split right by hand every time someone clones the template
is exactly what a script is for. It is also safe to run with --dry-run, which is
what makes it testable, and it hard-fails if any placeholder token survives the
substitution.

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

# The template's placeholder is a single token — `piper` (title-cased `Piper`).
# Everything the script does is ultimately "turn this into the user's name".
# It is deliberately one word so the dist name, package dir, and CLI command are
# all the same token in the template; the split into forms happens at rename time.
TEMPLATE_NAME = "piper"  # dist name, package dir, and CLI command (all one token in the template)
TEMPLATE_TITLE = "Piper"  # human-facing display name (README H1)

PACKAGE_RE = re.compile(r"^[a-z][a-z0-9_]*$")
# PEP 503/508 distribution name: alphanumerics separated by single '.', '-' or
# '_', starting and ending with an alphanumeric. uv/packaging reject anything
# else (e.g. a name with spaces), so we validate before writing [project].name.
DIST_RE = re.compile(r"^[A-Za-z0-9](?:[A-Za-z0-9._-]*[A-Za-z0-9])?$")

# The single placeholder token maps to two targets by context. We disambiguate
# on the character that immediately follows it: a `.`, `_`, or `/` means it is a
# dotted module path, an identifier, or a filesystem path (package form); any
# other boundary means it is the bare CLI command / distribution name (dist form).
PIPER_TITLE_RE = re.compile(r"\bPiper\b")
PIPER_PACKAGE_RE = re.compile(r"\bpiper(?=[._/])")
PIPER_DIST_RE = re.compile(r"\bpiper\b")
# Post-substitution safety net: no placeholder token may survive a transform.
# `\b...\b` avoids false positives on a user name that embeds it (e.g. "sandpiper").
SURVIVING_NAME_RE = re.compile(r"\b[Pp]iper\b")


@dataclass(frozen=True)
class Names:
    """The three forms of the new project name, derived from one another."""

    dist: str  # e.g. "invoice-extractor"
    package: str  # e.g. "invoice_extractor"
    title: str  # e.g. "Invoice Extractor"


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
    """Substitute the template name, resolving each occurrence by context.

    The placeholder is a single token — `piper` / `Piper` — that must become one
    of three targets depending on where it sits:
      * `Piper`                       -> the title
      * `piper` before `.`, `_`, `/`  -> the package form (imports, dotted module
                                          paths, filesystem paths, identifiers)
      * any other `piper`             -> the dist form (the CLI command name and
                                          the distribution name)

    Order matters: title first, then the package rule (which consumes the
    dotted / path occurrences), then the dist rule mops up what is left. This is
    the generic pass for .py / .md / .mthds files. pyproject.toml is handled by
    targeted per-key edits in transform_pyproject() instead, because its package
    arrays (`packages = ["piper"]`) put the package form in a bare-string
    position this character-after heuristic would misread as a command.
    """
    text = PIPER_TITLE_RE.sub(names.title, text)
    text = PIPER_PACKAGE_RE.sub(names.package, text)
    text = PIPER_DIST_RE.sub(names.dist, text)
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

    # Repository URL: with --repo-url, drop in the real URL and remove the
    # reminder comment. Without it, rewrite only the `yourusername/piper` slug to
    # the dist name and leave the `yourusername` placeholder + reminder in place.
    if opts.repo_url:
        # Double backslashes so re.sub's replacement mini-language treats any
        # backslash from toml_str() as literal rather than a group reference.
        repository_line = f"Repository = {toml_str(opts.repo_url)}".replace("\\", "\\\\")
        text = re.sub(
            r'Repository = "[^"]*"(?:\s*#.*)?',
            repository_line,
            text,
        )
    else:
        text = text.replace(f"yourusername/{TEMPLATE_NAME}", f"yourusername/{names.dist}")

    # Name tokens: targeted per-key edits rather than the character-after pass,
    # because a package name sitting bare in a TOML array (`packages = ["piper"]`)
    # or as a bare table key looks like a command position to the generic
    # heuristic. Each occurrence is edited by its key; the post-run assertion in
    # run() is the backstop that catches any key not handled here.
    key_edits = {
        # [project].name -> distribution name
        f'name = "{TEMPLATE_NAME}"': f"name = {toml_str(names.dist)}",
        # [project.scripts]: <dist-command> = "<package>.cli:app"
        f'{TEMPLATE_NAME} = "{TEMPLATE_NAME}.cli:app"': f'{names.dist} = "{names.package}.cli:app"',
        # [tool.setuptools] packages (import names)
        f'packages = ["{TEMPLATE_NAME}", "{TEMPLATE_NAME}.examples"]': f'packages = ["{names.package}", "{names.package}.examples"]',
        # [tool.setuptools.package-data] table key (import name)
        f'{TEMPLATE_NAME} = ["py.typed"': f'{names.package} = ["py.typed"',
        # [tool.mypy] packages (import name)
        f'packages = ["{TEMPLATE_NAME}"]': f'packages = ["{names.package}"]',
        # [tool.pyright] include (import name)
        f'include = ["{TEMPLATE_NAME}", "tests"]': f'include = ["{names.package}", "tests"]',
    }
    for old_text, new_text in key_edits.items():
        text = text.replace(old_text, new_text)
    return text


def strip_template_block(text: str) -> str:
    """Remove the README's template-only scaffolding.

    Two independent regions are template-only: the `*Replace "Piper" ...*`
    reminder line right under the H1, and the whole `### Use this template`
    subsection (with real project prose sitting *between* them). We anchor on the
    heading text and the next H2 boundary rather than a `---` rule or line
    numbers, so edits to the surrounding prose — and the absence of a closing
    `---` — don't break us. Each lookup is a safe no-op when its marker is
    already gone (e.g. a re-run), so the whole function is idempotent.
    """
    lines = text.splitlines()

    # 1. The `### Use this template` subsection: from that heading up to (not
    #    including) the next H2, or end-of-file if there is none.
    use_start = next((i for i, ln in enumerate(lines) if ln.strip() == "### Use this template"), None)
    if use_start is not None:
        use_end = next((j for j in range(use_start + 1, len(lines)) if lines[j].startswith("## ")), len(lines))
        del lines[use_start:use_end]

    # 2. The standalone `*Replace "Piper" ...*` reminder line.
    replace_idx = next((i for i, ln in enumerate(lines) if ln.startswith('*Replace "')), None)
    if replace_idx is not None:
        del lines[replace_idx]

    out = "\n".join(lines)
    if text.endswith("\n"):
        out += "\n"
    # Collapse the blank-line gaps left behind by the deletions.
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
    # main() rejects any non-MIT license without a holder before we get here, so
    # a proprietary/SPDX notice can never ship with a placeholder copyright line.
    holder = lic.holder
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
    if f'name = "{TEMPLATE_NAME}"' not in pyproject_text:
        print(
            f'warning: pyproject.toml does not contain name = "{TEMPLATE_NAME}". This repo may already be bootstrapped; proceeding anyway.',
            file=sys.stderr,
        )

    print(f"Bootstrapping template -> {names.title!r}")
    print(f"  dist={names.dist}  package={names.package}  title={names.title}")
    if opts.dry_run:
        print("  (dry run — no files will be modified)")
    print()

    # 1. Rename the package directory first, so the file transforms below see the
    #    final paths. (The e2e test file is named after its demo, not the project,
    #    so nothing in tests/ needs renaming — only content edits.)
    print("Renames:")
    old_pkg = root / TEMPLATE_NAME
    new_pkg = root / names.package
    if names.package != TEMPLATE_NAME and old_pkg.is_dir():
        move(root, old_pkg, new_pkg, opts)
    if opts.use_git and not opts.dry_run and names.package != TEMPLATE_NAME:
        print("  note: git mv stages the rename; the content edits below are left unstaged.")
    print()

    # During a dry run the rename did not actually happen, so read the file list
    # from the original path to still show a meaningful plan.
    scan_names = names if not opts.dry_run else Names(names.dist, TEMPLATE_NAME, names.title)

    # 2. Content edits. Transform everything in memory first and assert no
    #    placeholder token survives before writing a single file — a leftover
    #    token means a transform rule missed a context, and we would rather abort
    #    with the locations than ship a half-renamed project.
    print("Edits:")
    planned: list[tuple[Path, str, str]] = []
    survivors: list[str] = []
    for path in gather_target_files(root, scan_names):
        original = path.read_text(encoding="utf-8")
        updated = transform_for(path, original, names, opts)
        for line_number, line in enumerate(updated.splitlines(), start=1):
            if SURVIVING_NAME_RE.search(line):
                survivors.append(f"{path.relative_to(root)}:{line_number}: {line.strip()}")
        planned.append((path, original, updated))

    if survivors:
        joined = "\n  ".join(survivors)
        sys.exit(f"error: placeholder name token still present after substitution in {len(survivors)} location(s):\n  {joined}")

    changed = 0
    for path, original, updated in planned:
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
    names = Names(dist=dist, package=package, title=title)

    root = Path(args.root).resolve()
    license_year = args.license_year or datetime.date.today().year
    lic = resolve_license(
        args.license or "mit",
        (args.license_holder or "").strip() or None,
        license_year,
    )
    # A proprietary / SPDX license notice is meaningless without a named holder,
    # so refuse up front rather than writing a placeholder into LICENSE. MIT is
    # exempt: it keeps the template body when no holder is given.
    if lic.kind != "mit" and not lic.holder:
        sys.exit(f"--license {lic.spdx!r} requires --license-holder: a {lic.kind} license notice needs a copyright holder.")
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
