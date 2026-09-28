#!/usr/bin/env python
"""
Generate the Virgil character-width table the whiteboard text sizing reads.

The whiteboard service lays text out server-side, where no browser exists to
measure with: the editor's canvas is the only true measure, and the next best
thing is the font's own advance widths — which is what the canvas itself sums.
Virgil (Excalidraw's default hand-drawn face) carries no kerning, so the sum
of advances IS the canvas measurement, once the font has loaded.

Run when @excalidraw/excalidraw bumps its bundled font:

    python scripts/generate_font_metrics.py /path/to/excalidraw/dist/prod/fonts/Virgil/Virgil-Regular.woff2

Writes src/lys/apps/ai_whiteboard/modules/whiteboard/font_metrics.py.
"""
import sys
from pathlib import Path

from fontTools.ttLib import TTFont

# The widths are expressed per unit of font size: advance / unitsPerEm, so
# any font size reads them by simple multiplication, the way the canvas does.
OUTPUT = Path(__file__).parent.parent / "src/lys/apps/ai_whiteboard/modules/whiteboard/font_metrics.py"


def main() -> None:
    if len(sys.argv) != 2:
        sys.exit(f"usage: {sys.argv[0]} <Virgil-Regular.woff2>")
    font = TTFont(sys.argv[1])
    upem = font["head"].unitsPerEm
    cmap = font.getBestCmap()
    hmtx = font["hmtx"]

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
        "Virgil character widths, per unit of font size — GENERATED, do not edit.",
        "",
        "Produced by scripts/generate_font_metrics.py from the Virgil-Regular.woff2",
        "that @excalidraw/excalidraw bundles (the face the editor measures text",
        "with once its fonts are loaded). Virgil carries no kerning, so the sum",
        "of these advances is the canvas measurement itself.",
        "",
        "Regenerate when the excalidraw package bumps its font.",
        '"""',
        "",
        "VIRGIL_CHAR_WIDTHS = {",
    ]
    for char in sorted(widths):
        lines.append(f"    {char!r}: {widths[char]},")
    lines.append("}")
    lines.append("")

    OUTPUT.write_text("\n".join(lines), encoding="utf-8")
    print(f"wrote {OUTPUT} ({len(widths)} characters)")


if __name__ == "__main__":
    main()
