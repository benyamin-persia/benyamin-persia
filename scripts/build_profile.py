#!/usr/bin/env python3
"""Generate dark/light, self-contained SVG GitHub profile cards.

Standard library only. Run with GITHUB_TOKEN to refresh public GitHub statistics.
Personal text lives in config.json; ASCII artwork lives in portrait.txt.
"""
from __future__ import annotations

import base64
import html
import json
import os
import pathlib
import sys
import urllib.error
import urllib.request

from color_ascii import render_colored_ascii

ROOT = pathlib.Path(__file__).resolve().parent.parent
CONFIG = ROOT / "config.json"
GRAPHQL_URL = "https://api.github.com/graphql"
WIDTH, HEIGHT = 1200, 685

PALETTES = {
    "dark": {
        "outer": "#0b101b", "panel": "#101927", "header": "#152238",
        "border": "#344761", "text": "#eef6ff", "muted": "#9bacc5",
        "accent": "#67e8d3", "secondary": "#91b6ff", "lines": "#53657c",
        "portrait": "#72e6d4", "stats": "#f3c879",
    },
    "light": {
        "outer": "#edf3fb", "panel": "#ffffff", "header": "#e7edf7",
        "border": "#becde1", "text": "#263349", "muted": "#566b83",
        "accent": "#087f84", "secondary": "#2959a5", "lines": "#9aaac0",
        "portrait": "#177985", "stats": "#a15d13",
    },
}

QUERY = """
query($login: String!, $after: String) {
  user(login: $login) {
    followers { totalCount }
    contributionsCollection { totalCommitContributions }
    repositories(
      first: 100, after: $after,
      ownerAffiliations: OWNER, privacy: PUBLIC
    ) {
      totalCount
      pageInfo { hasNextPage endCursor }
      nodes { stargazerCount }
    }
  }
}
"""


def xml(value: object) -> str:
    return html.escape(str(value), quote=True)


def github_stats(login: str, token: str) -> dict[str, int]:
    """Retrieve public owned repo counts/stars and rolling-year commit contributions."""
    cursor = None
    stars = 0
    user = None
    repos = 0
    followers = 0
    commits = 0

    while True:
        payload = json.dumps({
            "query": QUERY,
            "variables": {"login": login, "after": cursor},
        }).encode("utf-8")
        request = urllib.request.Request(
            GRAPHQL_URL, data=payload, method="POST",
            headers={
                "Authorization": "Bearer " + token,
                "Accept": "application/vnd.github+json",
                "Content-Type": "application/json",
                "User-Agent": "github-profile-svg-updater",
                "X-GitHub-Api-Version": "2022-11-28",
            },
        )
        with urllib.request.urlopen(request, timeout=25) as response:
            data = json.load(response)
        if data.get("errors"):
            raise RuntimeError("GitHub GraphQL error: " + str(data["errors"])[:800])
        user = (data.get("data") or {}).get("user")
        if not user:
            raise RuntimeError("GitHub account not found: " + login)
        repos_page = user["repositories"]
        repos = repos_page["totalCount"]
        followers = user["followers"]["totalCount"]
        commits = user["contributionsCollection"]["totalCommitContributions"]
        stars += sum(node["stargazerCount"] for node in repos_page["nodes"])
        if not repos_page["pageInfo"]["hasNextPage"]:
            break
        cursor = repos_page["pageInfo"]["endCursor"]
        if not cursor:
            raise RuntimeError("Missing GitHub pagination cursor")

    return {"repos": repos, "stars": stars, "commits": commits, "followers": followers}


def avatar_photo_data(config: dict) -> tuple[str, str] | None:
    """Load the user's exact public GitHub avatar, not a generated approximation."""
    url = config.get("avatar_url")
    if not url:
        return None
    request = urllib.request.Request(
        url,
        headers={"User-Agent": "benyamin-persia-profile-card"},
    )
    with urllib.request.urlopen(request, timeout=30) as response:
        mime = response.headers.get_content_type()
        if mime not in ("image/png", "image/jpeg", "image/webp"):
            raise RuntimeError(f"Unexpected GitHub avatar content type: {mime}")
        raw = response.read(2_000_001)
    if not 100 < len(raw) <= 2_000_000:
        raise RuntimeError("Public avatar is empty or unexpectedly large")
    return (mime, base64.b64encode(raw).decode("ascii"))


def render(config: dict, portrait: list[str], stats: dict, mode: str, avatar: tuple[str, str] | None = None) -> str:
    p = PALETTES[mode]
    font = "ui-monospace, SFMono-Regular, Menlo, Consolas, 'Liberation Mono', monospace"
    out = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{WIDTH}" height="{HEIGHT}" '
        f'viewBox="0 0 {WIDTH} {HEIGHT}" role="img" aria-label="GitHub terminal profile for {xml(config["display_name"])}">',
        f'<title>{xml(config["display_name"])} | GitHub terminal profile ({mode})</title>',
        '<desc>ASCII-style portrait and live public repositories, stars, commits from the last 12 months, and followers.</desc>',
        f'<rect width="{WIDTH}" height="{HEIGHT}" fill="{p["outer"]}"/>',
        f'<rect x="13" y="13" width="1174" height="659" rx="19" fill="{p["panel"]}" stroke="{p["border"]}" stroke-width="2"/>',
        f'<path d="M32 13 H1168 Q1187 13 1187 32 V77 H13 V32 Q13 13 32 13 Z" fill="{p["header"]}"/>',
    ]
    for x, color in ((40, "#ff6b72"), (65, "#ffd166"), (90, "#4fd18b")):
        out.append(f'<circle cx="{x}" cy="45" r="7" fill="{color}"/>')
    out.extend([
        f'<text x="125" y="51" fill="{p["muted"]}" font-family="{font}" font-size="17">{xml(config["title"])}</text>',
        f'<text x="1154" y="51" text-anchor="end" fill="{p["muted"]}" font-family="{font}" font-size="15">PROFILE // {mode.upper()}</text>',
        f'<line x1="414" y1="105" x2="414" y2="641" stroke="{p["border"]}" stroke-width="2"/>',
        f'<text x="49" y="121" fill="{p["secondary"]}" font-family="{font}" font-size="16">~/avatar.asc</text>',
        f'<text x="444" y="138" fill="{p["text"]}" font-family="{font}" font-weight="700" font-size="32">{xml(config["display_name"])}</text>',
        f'<text x="446" y="165" fill="{p["accent"]}" font-family="{font}" font-size="17">@{xml(config["username"])}</text>',
        f'<line x1="446" y1="178" x2="1147" y2="178" stroke="{p["border"]}"/>',
    ])

    # Keep the original ASCII portrait option, but default to an exact photo.
    # The previously generated grayscale ASCII approximation did not retain
    # enough facial detail to be recognizable.
    if config.get("portrait_style") == "color_ascii" and avatar:
        out.append(render_colored_ascii(avatar, mode))
    elif config.get("portrait_style", "photo") == "photo" and avatar:
        mime, encoded = avatar
        out.extend([
            '<defs><clipPath id="photo-clip"><rect x="45" y="166" width="345" height="367" rx="19"/></clipPath></defs>',
            f'<rect x="40" y="161" width="355" height="377" rx="23" fill="{p["header"]}" stroke="{p["accent"]}" stroke-width="2"/>',
            f'<image x="45" y="166" width="345" height="367" clip-path="url(#photo-clip)" preserveAspectRatio="xMidYMid slice" href="data:{mime};base64,{encoded}"/>',
            f'<rect x="45" y="490" width="345" height="43" fill="{p["header"]}" opacity="0.93" clip-path="url(#photo-clip)"/>',
            f'<text x="61" y="516" fill="{p["accent"]}" font-family="{font}" font-size="16">GITHUB // ORIGINAL PHOTO</text>',
            f'<text x="50" y="566" fill="{p["muted"]}" font-family="{font}" font-size="14">Photo from @{xml(config["username"])}</text>',
            f'<path d="M52 587 H385" stroke="{p["border"]}" stroke-width="1"/>',
            f'<text x="50" y="615" fill="{p["secondary"]}" font-family="{font}" font-size="15">\u003e profile --authentic</text>',
        ])
    else:
        # Preserved original text-based avatar rendering, for ASCII mode.
        for i, line in enumerate(portrait[:39]):
            out.append(
                f'<text xml:space="preserve" x="45" y="{150 + i * 12.15:.2f}" '
                f'fill="{p["portrait"]}" font-family="{font}" font-size="10.2">{xml(line)}</text>'
            )

    values = [
        ("Role", config["role"]),
        ("Uptime", config["uptime"]),
        ("Host", config["host"]),
        ("Base", config["base"]),
        ("Focus", config["focus"]),
        ("Stack", config["stack"]),
        ("Languages", config["languages"]),
        ("Contact", config["contact"]),
    ]
    for i, (key, value) in enumerate(values):
        y = 215 + i * 41
        label = str(key).upper()
        value = str(value)
        size = min(16.5, max(12.0, 490.0 / max(1, len(value) * 0.60)))
        estimated_width = len(value) * size * 0.60
        line_end = max(597, 1147 - estimated_width - 16)
        out.extend([
            f'<text x="446" y="{y}" fill="{p["secondary"]}" font-family="{font}" font-weight="700" font-size="16">{xml(label)}</text>',
            f'<line x1="578" y1="{y-5}" x2="{line_end:.1f}" y2="{y-5}" stroke="{p["lines"]}" stroke-width="2" stroke-dasharray="2 7"/>',
            f'<text x="1148" y="{y}" text-anchor="end" fill="{p["text"]}" font-family="{font}" font-size="{size:.1f}">{xml(value)}</text>',
        ])

    out.extend([
        f'<line x1="446" y1="530" x2="1147" y2="530" stroke="{p["border"]}"/>',
        f'<text x="446" y="557" fill="{p["accent"]}" font-family="{font}" font-weight="700" font-size="19">{xml(config["github_stats_title"])}</text>',
    ])
    stat_items = [
        ("REPOS", stats["repos"], 446, 586),
        ("STARS RECEIVED", stats["stars"], 790, 586),
        ("COMMITS (12MO)", stats["commits"], 446, 617),
        ("FOLLOWERS", stats["followers"], 790, 617),
    ]
    for key, val, x, y in stat_items:
        value = f"{val:,}" if isinstance(val, int) else str(val)
        out.extend([
            f'<text x="{x}" y="{y}" fill="{p["muted"]}" font-family="{font}" font-size="14">{xml(key)}</text>',
            f'<text x="{x+329}" y="{y}" text-anchor="end" fill="{p["stats"]}" font-family="{font}" font-weight="700" font-size="21">{xml(value)}</text>',
        ])
    out.extend([
        f'<line x1="446" y1="639" x2="1147" y2="639" stroke="{p["border"]}"/>',
        f'<text x="446" y="659" fill="{p["muted"]}" font-family="{font}" font-size="13">{xml(config["footer"])}</text>',
        '</svg>',
    ])
    return "\n".join(out) + "\n"


def main() -> None:
    config = json.loads(CONFIG.read_text(encoding="utf-8"))
    portrait_path = ROOT / config.get("portrait_file", "portrait.txt")
    portrait = portrait_path.read_text(encoding="utf-8").splitlines()
    avatar = (
        avatar_photo_data(config)
        if config.get("portrait_style", "photo") in ("photo", "color_ascii")
        else None
    )
    token = os.environ.get("GITHUB_TOKEN", "").strip()
    if token:
        stats = github_stats(config["username"], token)
    else:
        # No invented numbers for local previews. GitHub Actions supplies GITHUB_TOKEN.
        stats = {"repos": "syncing", "stars": "syncing", "commits": "syncing", "followers": "syncing"}
        print("GITHUB_TOKEN not set: creating preview cards with placeholder stats.", file=sys.stderr)

    assets = ROOT / "assets"
    assets.mkdir(parents=True, exist_ok=True)
    for mode in ("dark", "light"):
        destination = assets / (mode + "_mode.svg")
        destination.write_text(render(config, portrait, stats, mode, avatar), encoding="utf-8")
        print("Updated", destination.relative_to(ROOT))
    print("Stats:", stats)


if __name__ == "__main__":
    main()
