#!/usr/bin/env python3
"""Convert the account's existing public GitHub avatar into masked ASCII art.

Uses Python's standard library and the ffmpeg binary on GitHub-hosted runners.
No private photos, face recognition, AI services, or PyPI dependencies.
"""
from __future__ import annotations

import json
import pathlib
import shutil
import subprocess
import urllib.parse
import urllib.request

ROOT = pathlib.Path(__file__).resolve().parent.parent
W, H = 52, 39
RAMP = "@%#*+=-:. "


def is_subject(x: int, y: int) -> bool:
    # Photo-specific silhouette: baseball cap -> face -> jacket and shoulders.
    cap = ((x - 27) / 16.1) ** 2 + ((y - 9) / 8.3) ** 2 < 1 and y <= 13
    face = ((x - 26) / 12.6) ** 2 + ((y - 19.0) / 13.0) ** 2 < 1 and 12 <= y <= 30
    shoulders = ((x - 26) / 27.0) ** 2 + ((y - 44) / 18.5) ** 2 < 1 and y >= 25
    return cap or face or shoulders


def main() -> None:
    config = json.loads((ROOT / "config.json").read_text(encoding="utf-8"))
    username = urllib.parse.quote(config["username"], safe="")
    url = config.get("avatar_url") or f"https://github.com/{username}.png?size=460"
    req = urllib.request.Request(url, headers={"User-Agent": "github-profile-ascii"})
    with urllib.request.urlopen(req, timeout=30) as response:
        avatar = response.read()
    if not avatar or len(avatar) > 5_000_000:
        raise RuntimeError("Avatar download was empty or unexpectedly large")
    ffmpeg = shutil.which("ffmpeg")
    if not ffmpeg:
        raise RuntimeError("ffmpeg is required to decode the profile picture")
    cmd = [
        ffmpeg, "-hide_banner", "-loglevel", "error",
        "-i", "pipe:0",
        "-vf", f"scale={W}:{H}:flags=area,format=gray",
        "-frames:v", "1", "-pix_fmt", "gray",
        "-f", "rawvideo", "pipe:1",
    ]
    proc = subprocess.run(cmd, input=avatar, capture_output=True, check=True, timeout=30)
    pixels = proc.stdout
    if len(pixels) != W * H:
        raise RuntimeError(f"Unexpected decoded image size: {len(pixels)}")
    lines = []
    for y in range(H):
        line = []
        for x in range(W):
            if not is_subject(x, y):
                line.append(" ")
                continue
            tone = pixels[y * W + x] / 255.0
            # Slight contrast boost for better facial detail on GitHub's small card.
            tone = min(1.0, max(0.0, (tone - 0.08) / 0.86))
            level = min(len(RAMP) - 1, int(tone * (len(RAMP) - 1)))
            line.append(RAMP[level])
        lines.append("".join(line).rstrip())
    art = "\n".join(lines) + "\n"
    (ROOT / config.get("portrait_file", "portrait.txt")).write_text(art, encoding="utf-8")
    print(f"Generated {W} x {H} character portrait using the public GitHub avatar.")


if __name__ == "__main__":
    main()
