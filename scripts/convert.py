#!/usr/bin/env python3
"""Convert the AiSList YouTube channel blocklist into a uBlock Origin filter list.

Input  : upstream aislist_blocklist.txt (one `@handle` or `UC...` channel ID per line, `!` comments)
Output : aislist_ublock.txt (uBO cosmetic filters for youtube.com)

The output is deterministic: it contains no "now" timestamp, so re-running on an
unchanged upstream produces a byte-identical file (and therefore no new commit).

Usage:  python3 -I scripts/convert.py INPUT OUTPUT
"""
import re
import sys
from urllib.parse import quote, unquote

# Elements that represent one "card" for a video / channel / playlist on YouTube.
# A card is hidden when it contains a link to a blocked channel.
CONTAINERS = [
    # desktop
    "ytd-rich-item-renderer",
    "ytd-video-renderer",
    "ytd-compact-video-renderer",
    "ytd-grid-video-renderer",
    "ytd-channel-renderer",
    "ytd-playlist-renderer",
    "yt-lockup-view-model",
    # mobile (m.youtube.com)
    "ytm-rich-item-renderer",
    "ytm-video-with-context-renderer",
    "ytm-compact-video-renderer",
]
PREFIX = "youtube.com##:is(%s):has(" % ",".join(CONTAINERS)

CHANNEL_ID_RE = re.compile(r"^UC[A-Za-z0-9_-]{22}$")
# Anything except whitespace and characters that could break the CSS attribute
# selector / filter syntax (handles in many scripts contain combining marks,
# so a strict \w match is too narrow).
HANDLE_RE = re.compile(r"^@[^\s\"'\\\[\]{}()<>,;:#%/?&=+*^$|`~!]{1,200}$")
LAST_MODIFIED_RE = re.compile(r"^!\s*Last Modified:\s*(\S+)", re.IGNORECASE)

# Entries per generated filter line: keeps the file small and quick for uBO to parse.
CHUNK = 100


def selectors_for(entry):
    """Href values to match for one blocklist entry."""
    if entry.startswith("@"):
        # YouTube serves non-ASCII handles percent-encoded in href attributes;
        # match both spellings.
        encoded = quote(entry, safe="@-_.")
        hrefs = ["/" + entry]
        if encoded != entry:
            hrefs.append("/" + encoded)
        return hrefs
    return ["/channel/" + entry]


def main(src, dst):
    handles, ids = [], []
    seen_handles, seen_ids = set(), set()
    skipped, dupes = [], 0
    upstream_modified = "unknown"

    with open(src, encoding="utf-8") as fh:
        for raw in fh:
            line = raw.strip()
            if not line:
                continue
            if line.startswith("!"):
                m = LAST_MODIFIED_RE.match(line)
                if m:
                    upstream_modified = m.group(1)
                continue
            if line.startswith("@") and "%" in line:
                line = unquote(line)  # some upstream entries are already percent-encoded
            if CHANNEL_ID_RE.match(line):
                if line in seen_ids:
                    dupes += 1
                    continue
                seen_ids.add(line)
                ids.append(line)
            elif HANDLE_RE.match(line):
                key = line.lower()  # handles are case-insensitive
                if key in seen_handles:
                    dupes += 1
                    continue
                seen_handles.add(key)
                handles.append(line)
            else:
                skipped.append(line)

    if not handles and not ids:
        sys.exit("No entries parsed from %s - refusing to write an empty list." % src)

    out = [
        "[Adblock Plus 2.0]",
        "! Title: AiSList - YouTube AI Slop Channels (uBlock Origin)",
        "! Description: uBlock Origin version of the AiSList community blocklist. "
        "Warns before opening, and hides videos from, YouTube channels flagged as AI-generated content.",
        "! Homepage: https://aisloplist.com",
        "! Source: https://github.com/Override92/AiSList",
        "! License: CC BY-NC 4.0 https://creativecommons.org/licenses/by-nc/4.0/",
        "! Credit: channel data by the AiSList community (Override92/AiSList), used under CC BY-NC 4.0",
        "! Changes: converted from the original handle list to uBlock Origin page-block and cosmetic filters; "
        "duplicates removed. Unofficial - not affiliated with or endorsed by the AiSList authors.",
        "! Version: %s" % upstream_modified.replace("-", "."),
        "! Upstream last modified: %s" % upstream_modified,
        "! Expires: 1 day",
        "! Entries: %d handles, %d channel IDs" % (len(handles), len(ids)),
        "!",
    ]
    # 1) Page block: opening a listed channel's page shows uBO's "page blocked" screen
    #    (with the list name and a Proceed button). Network filters match the URL as the
    #    browser sends it, i.e. percent-encoded, and are case-insensitive by default.
    #    `^` is a separator, so /@name does not also match /@name2.
    out.append("! --- Page warning: opening a listed channel page ---")
    for entry in handles + ids:
        path = selectors_for(entry)[-1]  # percent-encoded spelling when it differs
        out.append("||youtube.com%s^$document" % path)

    # 2) Hide listed channels' video/channel/playlist cards in feeds and search results.
    out.append("! --- Hide cards of listed channels ---")
    # `i` = case-insensitive match (YouTube handles are case-insensitive).
    sels = ['a[href="%s" i]' % href for h in handles for href in selectors_for(h)]
    sels += ['a[href="%s"]' % href for c in ids for href in selectors_for(c)]
    for i in range(0, len(sels), CHUNK):
        out.append(PREFIX + ",".join(sels[i:i + CHUNK]) + ")")

    with open(dst, "w", encoding="utf-8", newline="\n") as fh:
        fh.write("\n".join(out) + "\n")

    print("handles: %d  channel IDs: %d  duplicates dropped: %d  skipped: %d"
          % (len(handles), len(ids), dupes, len(skipped)))
    for s in skipped[:20]:
        print("  skipped:", s)


if __name__ == "__main__":
    if len(sys.argv) != 3:
        sys.exit(__doc__)
    main(sys.argv[1], sys.argv[2])
