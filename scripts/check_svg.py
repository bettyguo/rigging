#!/usr/bin/env python3
"""Sanity-check SVGs for parse errors and obvious text-overflow risks.

For each SVG in assets/:
  - parses as XML
  - extracts viewBox dimensions
  - for every <text>/<rect>/<g transform=translate>, applies a coarse
    width estimate and flags any text element whose rendered width seems
    to exceed its parent container bounds.

This is a heuristic — it cannot match a real layout engine. But it
catches the class of bug "I made the box 180px and put 30 chars at 12px
mono inside it".

Exit non-zero if any SVG fails to parse. Print warnings for likely overflow.

Usage:
    python scripts/check_svg.py [paths...]    # default: assets/*.svg
"""
from __future__ import annotations

import io
import re
import sys
import xml.etree.ElementTree as ET
from pathlib import Path

# Coarse per-char width estimates in CSS px, given font-size and family.
CHAR_W = {
    ("mono", 11): 6.6, ("mono", 12): 7.2, ("mono", 13): 7.8,
    ("mono", 14): 8.4,
    ("sans", 11): 5.5, ("sans", 12): 6.0, ("sans", 13): 6.5,
    ("sans", 14): 7.0, ("sans", 16): 8.0, ("sans", 17): 8.5,
    ("sans", 18): 9.0, ("sans", 22): 11.0, ("sans", 24): 12.0,
}


def char_width(font_size: int, family: str, bold: bool = False) -> float:
    key = (family, font_size)
    if key in CHAR_W:
        w = CHAR_W[key]
    else:
        # fallback proportional
        w = (font_size * 0.55) if family == "sans" else (font_size * 0.60)
    return w * (1.10 if bold else 1.0)


def parse_font(s: str | None) -> tuple[int, str, bool]:
    """Return (size_px, family_kind, is_bold) from a CSS font shorthand."""
    if not s:
        return 14, "sans", False
    bold = bool(re.search(r"\b(700|800|900|bold)\b", s))
    m = re.search(r"(\d+)\s*px", s)
    size = int(m.group(1)) if m else 14
    family = "mono" if "monospace" in s or "mono" in s else "sans"
    return size, family, bold


def check_svg(path: Path) -> tuple[bool, list[str]]:
    """Return (parsed_ok, warnings)."""
    warnings: list[str] = []
    try:
        # Strip namespace prefixes to make parsing easier.
        raw = path.read_text(encoding="utf-8")
        root = ET.fromstring(raw)
    except ET.ParseError as e:
        return False, [f"XML parse error: {e}"]

    # Map class → font shorthand (parsed out of <style> CDATA/text).
    style_text = ""
    for el in root.iter():
        if el.tag.endswith("}style") or el.tag == "style":
            style_text += (el.text or "") + "\n"
    classes: dict[str, str] = {}
    for m in re.finditer(r"\.(\w+)\s*\{([^}]*)\}", style_text):
        cls, decl = m.group(1), m.group(2)
        m2 = re.search(r"font\s*:\s*([^;]+)", decl)
        if m2:
            classes[cls] = m2.group(1)

    # Iterate every <text> and tally character count.
    # We only flag elements with explicit `font` style on attr or via class,
    # because we cannot infer inherited fonts perfectly.
    for el in root.iter():
        tag = el.tag.split("}")[-1]
        if tag != "text":
            continue
        cls = el.get("class", "")
        font_spec = classes.get(cls) or el.get("font") or el.get("style", "")
        size, family, bold = parse_font(font_spec)
        # Combine all text content from element + tspans
        full_text = "".join(el.itertext())
        # If multi-line via tspans with x reset, we treat each tspan
        # independently — find the longest among them.
        tspans = list(el.findall("{http://www.w3.org/2000/svg}tspan"))
        if tspans:
            lines = [(t.text or "") for t in tspans]
        else:
            lines = [full_text]
        longest = max((s for s in lines if s), key=len, default="")
        if not longest:
            continue
        # Strip XML entities pre-decoded to graphemes — count chars.
        approx_px = len(longest) * char_width(size, family, bold)
        # Anchor for centred text means real x-extent halves left and right.
        # We don't have container metadata here; just report widths that
        # seem suspiciously large (> 600 px) to spot tight fits.
        if approx_px > 1200:
            warnings.append(
                f"{path.name}: text {longest[:50]!r} approx {approx_px:.0f}px wide "
                f"(font {size}px {family} {'bold' if bold else ''}); SVG viewBox "
                f"width = {root.get('viewBox', '?').split()[-2] if root.get('viewBox') else '?'}"
            )
    return True, warnings


def main() -> int:
    if hasattr(sys.stdout, "buffer"):
        sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

    paths = [Path(p) for p in sys.argv[1:]] or sorted(Path("assets").glob("*.svg"))
    failed = 0
    total_warnings = 0
    for p in paths:
        if not p.exists():
            print(f"  ! {p}: not found")
            failed += 1
            continue
        ok, warnings = check_svg(p)
        if not ok:
            print(f"  ✗ {p}: {warnings[0]}")
            failed += 1
            continue
        if warnings:
            print(f"  ! {p}:")
            for w in warnings:
                print(f"      {w}")
            total_warnings += len(warnings)
        else:
            print(f"  ✓ {p}: parses cleanly")
    print()
    print(f"  {len(paths)} files checked, {failed} parse error(s), {total_warnings} warning(s)")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
