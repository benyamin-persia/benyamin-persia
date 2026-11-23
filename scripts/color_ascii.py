#!/usr/bin/env python3
"""True, colored ASCII portrait drawn entirely with SVG text glyphs.

The source is the account's OWN public GitHub avatar. This generates NO
<image> element. The default terminal card can therefore display a recognizable
portrait without hiding an ordinary raster photograph behind the text art.

Only Python standard library + ffmpeg (already installed in the workflow).
"""
from __future__ import annotations

import base64
import html
import math
import subprocess

COLS = 104
ROWS = 90
RAMP = "@%#8&*+=-:."  # Deliberately no blank highlights: keep facial detail.


def _rgb_matrix(avatar: tuple[str, str]) -> bytes:
    _mime, encoded = avatar
    source = base64.b64decode(encoded)
    # Center on the person's face and shoulders rather than on the table/grass.
    # Crop values are fractions, so the same public avatar at different
    # resolutions yields a similar result.
    command = [
        "ffmpeg", "-hide_banner", "-loglevel", "error", "-i", "pipe:0",
        "-vf",
        f"crop=iw*0.69:ih*0.88:iw*0.15:ih*0.055,"
        f"scale={COLS}:{ROWS}:flags=lanczos,format=rgb24",
        "-frames:v", "1", "-pix_fmt", "rgb24",
        "-f", "rawvideo", "pipe:1",
    ]
    result = subprocess.run(
        command, input=source, capture_output=True, check=True, timeout=35
    )
    expected = COLS * ROWS * 3
    if len(result.stdout) != expected:
        raise RuntimeError(
            f"ffmpeg returned {len(result.stdout)} RGB bytes, expected {expected}"
        )
    return result.stdout


def _subject(x: int, y: int) -> bool:
    """Keep cap, face and shoulders; remove scenery and the table.

    Coordinates are relative to the normalized 104x90 portrait crop. The
    contours are tailored to the actual public profile photo, *not* a
    fabricated face. Keeping the color detail in the eyes, nose, mouth and
    jacket is what makes the ASCII rendering recognizable.
    """
    # Approximate point in the underlying 460x460 public avatar.
    sx = (0.15 + (x + 0.5) / COLS * 0.69) * 460
    sy = (0.055 + (y + 0.5) / ROWS * 0.88) * 460

    cap = ((sx - 235) / 89) ** 2 + ((sy - 111) / 62) ** 2 <= 1.0 and sy <= 144
    head = ((sx - 234) / 84) ** 2 + ((sy - 175) / 91) ** 2 <= 1.0 and sy >= 120
    neck = 205 <= sx <= 279 and 242 <= sy <= 285

    if sy >= 235:
        # Coat/shoulders widen into the bottom of the composition.
        progress = min(1.0, max(0.0, (sy - 238) / 105))
        left = 150 - 95 * progress
        right = 321 + 90 * progress
        torso = left <= sx <= right
    else:
        torso = False
    return cap or head or neck or torso


def render_colored_ascii(avatar: tuple[str, str], mode: str) -> str:
    """An SVG fragment whose portrait is only <text>/<tspan> elements."""
    pixels = _rgb_matrix(avatar)
    font = "ui-monospace, SFMono-Regular, Menlo, Consolas, 'Liberation Mono', monospace"
    out = [
        f'<g id="portrait-ascii" font-family="{font}" font-size="5.65" '
        'font-weight="650" xml:space="preserve">',
        f'<title>ASCII portrait created from the actual public GitHub photo</title>',
    ]
    for y in range(ROWS):
        glyphs = []
        for x in range(COLS):
            if not _subject(x, y):
                glyphs.append(" ")
                continue
            p = (y * COLS + x) * 3
            r, g, b = pixels[p], pixels[p + 1], pixels[p + 2]
            # Luma determines actual text character; image RGB supplies the ink.
            luma = 0.2126 * r + 0.7152 * g + 0.0722 * b
            idx = min(len(RAMP) - 1, int(luma / 255 * len(RAMP)))
            char = RAMP[idx]
            if mode == "dark":
                # Restore a readable lower bound for jacket and hair on navy.
                r, g, b = (min(255, int(v * 0.94 + 34)) for v in (r, g, b))
            else:
                r, g, b = (min(238, int(v * 0.94 + 5)) for v in (r, g, b))
            # 32 intensity bands per channel = stable, readable colored ink.
            r, g, b = ((v // 8) * 8 for v in (r, g, b))
            ink = f"#{r:02x}{g:02x}{b:02x}"
            glyphs.append(f'<tspan fill="{ink}">{html.escape(char)}</tspan>')
        out.append(
            f'<text x="44" y="{154 + y * 5.31:.2f}">' + "".join(glyphs) + "</text>"
        )
    out.append("</g>")
    return "\n".join(out)


if __name__ == "__main__":
    raise SystemExit("Use render_colored_ascii(...) from build_profile.py")
