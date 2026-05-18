#!/usr/bin/env python3
"""Audit internal links across the repository.

Scans every Markdown and HTML file under the repo root for:
  - Markdown link targets:       [text](path)
  - Markdown image targets:      ![alt](path)
  - HTML href/src attributes:    href="path" / src="path"

For each link, resolves the target relative to the file containing it
and verifies the target exists. External (http/https), `mailto:`, and
anchor-only (`#…`) links are skipped — fragment anchors within a Markdown
file are verified against the file's own headings.

Exits non-zero if any internal link is broken, missing, or points outside
the repo. Designed to run in CI.

Usage:
    python scripts/audit_links.py              # audit the repo
    python scripts/audit_links.py --no-color   # disable ANSI colour
    python scripts/audit_links.py --strict     # also check anchors
"""
from __future__ import annotations

import argparse
import io
import re
import sys
from collections.abc import Iterator
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent

# Directories to ignore wholesale.
SKIP_DIRS = {
    ".git", ".hypothesis", ".mypy_cache", ".pytest_cache", "__pycache__",
    "node_modules", "venv", ".venv", "dist", "build",
}

# Extensions we audit.
MD_EXT = {".md"}
HTML_EXT = {".html", ".htm"}
AUDIT_EXT = MD_EXT | HTML_EXT

# Match Markdown links/images: [text](target) and ![alt](target)
RE_MD_LINK = re.compile(r"(?<!\\)!?\[[^\]]*\]\(([^)\s]+)(?:\s+\"[^\"]*\")?\)")
# Match HTML href/src attributes.
RE_HTML_ATTR = re.compile(r'(?:href|src)\s*=\s*"([^"]+)"', re.IGNORECASE)
# Match Markdown headings, for anchor resolution.
RE_MD_HEADING = re.compile(r"^(#{1,6})\s+(.+?)\s*$", re.MULTILINE)


def slugify(text: str) -> str:
    """GitHub-style heading slug."""
    s = text.lower()
    s = re.sub(r"[^\w\s\-]", "", s)
    s = re.sub(r"\s+", "-", s).strip("-")
    return s


def iter_audit_files() -> Iterator[Path]:
    for path in REPO_ROOT.rglob("*"):
        if not path.is_file() or path.suffix.lower() not in AUDIT_EXT:
            continue
        if any(part in SKIP_DIRS for part in path.parts):
            continue
        yield path


def extract_links(file: Path) -> list[tuple[int, str]]:
    """Return a list of (line, raw_target) found in the file."""
    text = file.read_text(encoding="utf-8", errors="replace")
    out: list[tuple[int, str]] = []
    pattern = RE_MD_LINK if file.suffix.lower() in MD_EXT else RE_HTML_ATTR
    for m in pattern.finditer(text):
        # locate the line number
        line = text.count("\n", 0, m.start()) + 1
        out.append((line, m.group(1)))
    return out


def heading_slugs(file: Path) -> set[str]:
    """Return GitHub-style heading slugs in a Markdown file."""
    if file.suffix.lower() not in MD_EXT:
        return set()
    text = file.read_text(encoding="utf-8", errors="replace")
    slugs: set[str] = set()
    for m in RE_MD_HEADING.finditer(text):
        slugs.add(slugify(m.group(2)))
    # GitHub also auto-anchors HTML anchors inside markdown: <a id="x">
    slugs.update(re.findall(r'(?:id|name)\s*=\s*"([^"]+)"', text))
    return slugs


def is_external(target: str) -> bool:
    t = target.strip().lower()
    return t.startswith(("http://", "https://", "mailto:", "tel:", "javascript:"))


def resolve(file: Path, target: str) -> tuple[Path | None, str | None]:
    """Resolve a target relative to file. Returns (path_or_none, fragment).

    Returns ``(None, fragment)`` for anchor-only links.
    """
    if "#" in target:
        path_part, frag = target.split("#", 1)
    else:
        path_part, frag = target, None

    if not path_part:
        return None, frag

    # strip query string
    if "?" in path_part:
        path_part = path_part.split("?", 1)[0]

    candidate = (file.parent / path_part).resolve()
    return candidate, frag


def main() -> int:
    # Force UTF-8 stdout on Windows so the ✓/✗ glyphs render.
    if hasattr(sys.stdout, "buffer"):
        sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--no-color", action="store_true",
                        help="Disable ANSI colour in output.")
    parser.add_argument("--strict", action="store_true",
                        help="Also verify Markdown heading anchors resolve.")
    args = parser.parse_args()

    def c(s: str, code: str) -> str:
        return s if args.no_color else f"\033[{code}m{s}\033[0m"

    OK = lambda s: c(s, "32")    # noqa: E731
    BAD = lambda s: c(s, "31;1") # noqa: E731
    DIM = lambda s: c(s, "2")    # noqa: E731

    errors: list[str] = []
    n_files = 0
    n_links = 0
    n_external = 0
    n_skipped = 0

    # Precompute heading slugs per markdown file (for anchor checks).
    md_slugs: dict[Path, set[str]] = {}
    if args.strict:
        for f in iter_audit_files():
            if f.suffix.lower() in MD_EXT:
                md_slugs[f] = heading_slugs(f)

    for f in iter_audit_files():
        n_files += 1
        rel = f.relative_to(REPO_ROOT).as_posix()
        for line, target in extract_links(f):
            n_links += 1

            if is_external(target):
                n_external += 1
                continue

            if target.startswith("#"):
                # Anchor-only within the same file
                if args.strict and f.suffix.lower() in MD_EXT:
                    slugs = md_slugs.get(f, set())
                    frag = target[1:]
                    if frag and frag not in slugs:
                        errors.append(
                            f"{rel}:{line}: anchor "
                            f"{BAD('#' + frag)} not found in this file"
                        )
                else:
                    n_skipped += 1
                continue

            path, frag = resolve(f, target)
            if path is None:
                continue

            try:
                rel_path = path.relative_to(REPO_ROOT).as_posix()
            except ValueError:
                errors.append(
                    f"{rel}:{line}: target "
                    f"{BAD(target)} resolves outside the repo"
                )
                continue

            if not path.exists():
                errors.append(
                    f"{rel}:{line}: missing target "
                    f"{BAD(target)} → {DIM(rel_path)}"
                )
                continue

            if args.strict and frag and path.suffix.lower() in MD_EXT:
                slugs = md_slugs.get(path) or heading_slugs(path)
                md_slugs[path] = slugs
                if frag not in slugs:
                    errors.append(
                        f"{rel}:{line}: target "
                        f"{BAD(target)} → file ok, anchor #{frag} missing"
                    )

    print()
    print(f"  audited {OK(str(n_files))} files, {OK(str(n_links))} links")
    print(f"  {DIM(str(n_external))} external, {DIM(str(n_skipped))} anchors skipped")
    print()

    if errors:
        for e in errors:
            print(f"  {BAD('✗')} {e}")
        print()
        print(BAD(f"  {len(errors)} broken link(s)."))
        return 1

    print(OK("  all internal links resolve. ✓"))
    return 0


if __name__ == "__main__":
    sys.exit(main())
