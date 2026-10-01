"""Swap the EP post's listen-on chips over to the real album links.

Reads the label's smart link (vyd.co) and rewrites the .listen-icons row
inside #epReleasePost in index.html. Services the label hasn't filled in
yet keep pointing at the smart link. Prints "changed" or "unchanged".
"""

import json
import os
import re
import sys
import urllib.parse
import urllib.request

SLUG = os.environ.get("EP_SLUG", "HeldUnderAnIncandescentSky")
SMART_LINK = "https://vyd.co/HeldUnderAnIncandescentSky"
INDEX = os.environ.get("EP_INDEX", "index.html")

# the six the label's page shows; these always get a chip
CORE = ["Apple Music", "Spotify", "Amazon Music", "Tidal", "SoundCloud", "Deezer"]
SKIP = {"TikTok"}
ICONS = {
    "Apple Music": '<i class="fab fa-apple"></i>',
    "Spotify": '<i class="fab fa-spotify"></i>',
    "Amazon Music": '<i class="fab fa-amazon"></i>',
    "SoundCloud": '<i class="fab fa-soundcloud"></i>',
    "Deezer": '<i class="fab fa-deezer"></i>',
    "YouTube Music": '<i class="fab fa-youtube"></i>',
    "Audiomack": '<i class="fas fa-headphones"></i>',
    "Boomplay": '<i class="fas fa-compact-disc"></i>',
}


def fetch_partners():
    req = urllib.request.Request(
        "https://vyd.co/" + SLUG, headers={"User-Agent": "Mozilla/5.0"}
    )
    html = urllib.request.urlopen(req, timeout=30).read().decode("utf-8")
    m = re.search(r'<script id="__NEXT_DATA__"[^>]*>(.*?)</script>', html, re.S)
    album = json.loads(m.group(1))["props"]["pageProps"]["album"]
    return album["partners"]


def clean(url):
    url = re.sub(r"^http://", "https://", url)
    parts = urllib.parse.urlsplit(url)
    query = [
        (k, v)
        for k, v in urllib.parse.parse_qsl(parts.query, keep_blank_values=True)
        if not k.startswith("utm_")
    ]
    return urllib.parse.urlunsplit(parts._replace(query=urllib.parse.urlencode(query)))


def pick_links(partners):
    """[(name, url)] in the label page's order."""
    links, seen = [], set()
    for p in partners:
        name = p["network"]["name"]
        if p["link_action"] != "PLAY" or name in SKIP or name in seen:
            continue
        url = p.get("partner_url") or ""
        live = url and not p["hide_release_link"]
        if live:
            links.append((name, clean(url)))
        elif name in CORE:
            links.append((name, SMART_LINK))
        else:
            continue
        seen.add(name)
    for name in CORE:  # never lose one of the six
        if name not in seen:
            links.append((name, SMART_LINK))
    return links


def render(links, tidal_icon):
    t = "\t" * 8
    out = ['<div class="listen-icons">']
    for name, url in links:
        icon = tidal_icon if name == "Tidal" else ICONS.get(name, '<i class="fas fa-music"></i>')
        out.append(
            f'{t}<a\n{t}\thref="{url}"\n{t}\ttarget="_blank"\n'
            f'{t}\trel="noopener noreferrer"\n{t}\taria-label="Listen on {name}"\n'
            f"{t}\t>{icon}<span>{name}</span></a\n{t}>"
        )
    out.append("\t" * 7 + "</div>")
    return "\n".join(out)


def main():
    links = pick_links(fetch_partners())
    for name, url in links:
        print(f"  {name:14} {url}")

    src = open(INDEX, encoding="utf-8").read()
    post = src.index('id="epReleasePost"')
    start = src.index('<div class="listen-icons">', post)
    end = src.index("</div>", start) + len("</div>")
    row = src[start:end]
    tidal = re.search(r'<svg class="listen-svg".*?</svg>', row, re.S).group(0)

    new = src[:start] + render(links, tidal) + src[end:]
    if new == src:
        print("unchanged")
        return
    open(INDEX, "w", encoding="utf-8").write(new)
    print("changed")


if __name__ == "__main__":
    sys.exit(main())
