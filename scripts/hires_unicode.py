#!/usr/bin/env python3
"""High-fidelity photo-derived Unicode text art for the GitHub profile.

This renderer NEVER draws a photograph, copies pixels into an <image> tag, or
generates another person's face. Every visible colored mark is an actual
Unicode text glyph: the top and bottom halves of "▀" and "▄".

Requires only Python stdlib and ffmpeg, already in the GitHub workflow.
The previous color_ascii.py and the other portrait modes remain untouched.
"""
from __future__ import annotations

import base64
import subprocess

COLS = 104
ROWS = 93                 # 186 independently colored vertical samples
FONT_SIZE = 5.62
LINE_HEIGHT = 5.17
LEFT = 43
TOP = 156

# Exact crop fractions for the existing public GitHub headshot. These show
# the cap, eyes, nose, mouth and upper jacket without the table/grass.
CROP_X, CROP_Y = 0.350, 0.100
CROP_W, CROP_H = 0.480, 0.670


def _decode_photo(avatar: tuple[str, str]) -> bytes:
    mime, encoded = avatar
    if mime not in ("image/jpeg", "image/png", "image/webp"):
        raise ValueError("Expected an image from the existing GitHub avatar")
    pixels = base64.b64decode(encoded, validate=True)
    process = subprocess.run(
        [
            "ffmpeg", "-hide_banner", "-loglevel", "error",
            "-i", "pipe:0", "-vf",
            "crop=iw*{w}:ih*{h}:iw*{x}:ih*{y},"
            "unsharp=5:5:0.7:3:3:0.0,"
            "scale={c}:{r}:flags=lanczos,format=rgb24".format(
                w=CROP_W, h=CROP_H, x=CROP_X, y=CROP_Y,
                c=COLS, r=ROWS * 2,
            ),
            "-frames:v", "1", "-pix_fmt", "rgb24",
            "-f", "rawvideo", "pipe:1",
        ],
        input=pixels, capture_output=True, check=True, timeout=40,
    )
    expected = COLS * ROWS * 2 * 3
    if len(process.stdout) != expected:
        raise ValueError(
            f"Photo decode returned {len(process.stdout)} bytes, expected {expected}"
        )
    return process.stdout


def _is_person(x: int, y: int) -> bool:
    """Conservative photo-specific crop mask, not a generated face.

    Unlike the previous silhouette, it does NOT shift the face or replace
    its features. Every actual face pixel comes from the existing photo.
    """
    sx = (CROP_X + (x + 0.5) / COLS * CROP_W) * 460.0
    sy = (CROP_Y + (y + 0.5) / (ROWS * 2) * CROP_H) * 460.0

    cap = ((sx - 273) / 84) ** 2 + ((sy - 103) / 58) ** 2 <= 1.0 and sy < 144
    face = ((sx - 281) / 88) ** 2 + ((sy - 181) / 99) ** 2 <= 1.0 and sy >= 109
    neck = 231 <= sx <= 328 and 245 <= sy <= 287
    shoulders = (
        sy >= 249
        and (203 - 0.60 * (sy - 249)) <= sx <= (362 + 0.46 * (sy - 249))
    )
    return cap or face or neck or shoulders


def _ink(data: bytes, x: int, y: int, mode: str) -> str | None:
    if not _is_person(x, y):
        return None

    offset = (y * COLS + x) * 3
    r, g, b = data[offset], data[offset + 1], data[offset + 2]

    # The yellow-green outdoor background is removed, but brown skin and
    # the dark blue/gray plaid jacket are intentionally retained.
    sx = (CROP_X + (x + 0.5) / COLS * CROP_W) * 460.0
    sy = (CROP_Y + (y + 0.5) / (ROWS * 2) * CROP_H) * 460.0
    on_face = 213 <= sx <= 363 and 131 <= sy <= 268
    is_outdoor_yellow_green = (
        g > 96
        and (g > r * 0.91 or r > g * 0.98)
        and g > b * 1.58
    )
    # Remove bright grass beyond the left ear while protecting the true
    # brow, nose, mouth and cheeks; no pixels are fabricated or retouched.
    if is_outdoor_yellow_green and (
        not on_face or (sx < 230 and sy < 240)
    ):
        return None

    if mode == "dark":
        # Brighten real dark details so eyes and cap remain visible on navy.
        r, g, b = (min(255, round(v * 1.04 + 14)) for v in (r, g, b))
    else:
        r, g, b = (min(238, round(v * 0.96 + 2)) for v in (r, g, b))
    return f"#{r:02x}{g:02x}{b:02x}"


def render_hires_unicode(avatar: tuple[str, str], mode: str) -> str:
    """SVG text only; two differently colored half-block glyphs per cell."""
    data = _decode_photo(avatar)
    font = "'DejaVu Sans Mono', 'Liberation Mono', Consolas, monospace"
    out = [
        '<g id="portrait-hires-unicode" font-family="{font}" '
        'font-size="{size}" font-weight="400" '
        'xml:space="preserve">'.format(font=font, size=FONT_SIZE),
        '<title>High-detail Unicode text portrait sampled from Ben&#39;s own GitHub photo</title>',
    ]
    num_glyphs = 0
    for row in range(ROWS):
        upper = []
        lower = []
        for col in range(COLS):
            top = _ink(data, col, row * 2, mode)
            bot = _ink(data, col, row * 2 + 1, mode)
            if top is None:
                upper.append("&#160;")
            else:
                upper.append(f'<tspan fill="{top}">&#9600;</tspan>')
                num_glyphs += 1
            if bot is None:
                lower.append("&#160;")
            else:
                lower.append(f'<tspan fill="{bot}">&#9604;</tspan>')
                num_glyphs += 1
        baseline = TOP + row * LINE_HEIGHT
        # Both rows occupy the identical monospace cell coordinates.
        # Upper and lower half-blocks do not overlap geometrically.
        out.append(
            f'<text x="{LEFT}" y="{baseline:.2f}">' + "".join(upper) + "</text>"
        )
        out.append(
            f'<text x="{LEFT}" y="{baseline:.2f}">' + "".join(lower) + "</text>"
        )
    out.append("</g>")
    if num_glyphs < 9000:
        raise RuntimeError(f"Portrait mask produced only {num_glyphs} text glyphs")
    return "\n".join(out)


if __name__ == "__main__":
    raise SystemExit("Use render_hires_unicode(...) from build_profile.py")
