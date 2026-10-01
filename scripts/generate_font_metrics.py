#!/usr/bin/env python
"""
Generate the character-width table the whiteboard text sizing reads.

The whiteboard service lays text out server-side, where no browser exists to
measure with: the editor's canvas is the only true measure, and the next best
thing is the font's own advance widths — which is what the canvas itself sums.

The face is the one the whiteboard writes with (``FONT_FAMILY`` in the
whiteboard's consts): Liberation Sans, the sans-serif Excalidraw bundles and
serves itself, so every viewer sees the same glyphs whatever fonts their
system has. It is metric-compatible with Arial. Unlike a hand-drawn face it
carries kerning pairs, which the canvas applies and a sum of advances cannot:
the table therefore reads a hair wide on a few pairs — the safe side, a box
slightly too roomy is invisible where a clipped word is not.

Run when @excalidraw/excalidraw bumps its bundled font, or when the
whiteboard changes face:

    python scripts/generate_font_metrics.py \
        /path/to/excalidraw/dist/prod/fonts/Liberation/LiberationSans-Regular.woff2

Writes src/lys/apps/ai_whiteboard/modules/whiteboard/font_metrics.py.
"""
import sys
from pathlib import Path

from fontTools.ttLib import TTFont

# The widths are expressed per unit of font size: advance / unitsPerEm, so
# any font size reads them by simple multiplication, the way the canvas does.
OUTPUT = Path(__file__).parent.parent / "src/lys/apps/ai_whiteboard/modules/whiteboard/font_metrics.py"

# Name table record holding the face's full name ("Liberation Sans").
FULL_NAME_ID = 4


def main() -> None:
    if len(sys.argv) != 2:
        sys.exit(f"usage: {sys.argv[0]} <font file (.woff2, .ttf)>")
    source = Path(sys.argv[1])
    font = TTFont(source)
    upem = font["head"].unitsPerEm
    cmap = font.getBestCmap()
    hmtx = font["hmtx"]
    face = font["name"].getDebugName(FULL_NAME_ID) or source.stem

    widths = {}
    for codepoint, glyph_name in cmap.items():
        if not glyph_name or glyph_name.startswith("."):  # no zero-width internals
            continue
        width_units = hmtx[glyph_name][0]
        if width_units <= 0:
            continue
        widths[chr(codepoint)] = round(width_units / upem, 6)

    lines = [
        '"""',
        f"{face} character widths, per unit of font size — GENERATED, do not edit.",
        "",
        f"Produced by scripts/generate_font_metrics.py from the {source.name}",
        "that @excalidraw/excalidraw bundles (the face the whiteboard writes",
        "with). The sum of these advances is the canvas measurement, kerning",
        "aside: see the script for what that leaves out.",
        "",
        "Regenerate when the excalidraw package bumps its font, or when the",
        "whiteboard changes face.",
        '"""',
        "",
        "CHAR_WIDTHS = {",
    ]
    for char in sorted(widths):
        lines.append(f"    {char!r}: {widths[char]},")
    lines.append("}")
    lines.append("")

    OUTPUT.write_text("\n".join(lines), encoding="utf-8")
    print(f"wrote {OUTPUT} ({len(widths)} characters, face: {face})")


if __name__ == "__main__":
    main()
