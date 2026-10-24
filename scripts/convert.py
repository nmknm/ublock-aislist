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
    "ytm-media-item",
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

# Notice drawn above the video title on watch pages of listed channels.
# (uBO forbids url(), backslashes and comments in :style(), so the text is plain Unicode.)
WARNING_STYLE = (
    'content: "⚠ This channel is on the AiSList AI-content list" !important; '
    "display: block !important; width: fit-content !important; "
    "background: #b00020 !important; color: #fff !important; "
    "padding: 6px 12px !important; margin-bottom: 8px !important; "
    "border-radius: 8px !important; "
    "font: 600 14px/1.3 Roboto, Arial, sans-serif !important"
)

# Same notice as a small floating label, for pages with no title to attach it to
# (Shorts) and for the mobile site. Fixed to the viewport, never intercepts taps/clicks.
FLOATING_STYLE = (
    'content: "⚠ This channel is on the AiSList AI-content list" !important; '
    "position: fixed !important; top: 60px !important; left: 50% !important; "
    "transform: translateX(-50%) !important; z-index: 2147483647 !important; "
    "pointer-events: none !important; max-width: 90vw !important; "
    "box-sizing: border-box !important; text-align: center !important; "
    "background: #b00020 !important; color: #fff !important; "
    "padding: 6px 12px !important; border-radius: 8px !important; "
    "box-shadow: 0 2px 8px rgba(0,0,0,.45) !important; "
    "font: 600 14px/1.3 Roboto, Arial, sans-serif !important"
)

# Channels per address-matching regex (these are evaluated by uBO's script, so keep them modest).
PATH_CHUNK = 200

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
        "Warns about, and hides videos from, YouTube channels flagged as AI-generated content.",
        "! Homepage: https://aisloplist.com",
        "! Source: https://github.com/Override92/AiSList",
        "! License: CC BY-NC 4.0 https://creativecommons.org/licenses/by-nc/4.0/",
        "! Credit: channel data by the AiSList community (Override92/AiSList), used under CC BY-NC 4.0",
        "! Changes: converted from the original handle list to uBlock Origin page-block, warning and cosmetic filters; "
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

    # 3) Warning on video pages. When the channel shown under the video is listed, a red
    #    notice is drawn above the title. It is injected with a ::before pseudo-element
    #    (CSS `content`), so it needs no script and also works when YouTube changes pages
    #    without reloading.
    out.append("! --- Warning above the title on video pages ---")
    for i in range(0, len(sels), CHUNK):
        out.append("youtube.com##ytd-watch-metadata:has(#owner :is(%s)) #title::before:style(%s)"
                   % (",".join(sels[i:i + CHUNK]), WARNING_STYLE))

    # 4) Warning on desktop Shorts (the active Short's channel) and on mobile video pages
    #    (m.youtube.com, the channel under the video). One floating label for both; the
    #    subjects (ytd-shorts / ytm-app) only exist on the matching site, and ytd-shorts is
    #    hidden when you are not on Shorts, so the label does not linger on other pages.
    out.append("! --- Warning on Shorts and on the mobile site ---")
    for i in range(0, len(sels), CHUNK):
        out.append(
            "youtube.com##:is(ytd-shorts,ytm-app):has("
            ":is(ytd-reel-video-renderer[is-active],ytm-slim-owner-renderer) :is(%s))"
            "::before:style(%s)" % (",".join(sels[i:i + CHUNK]), FLOATING_STYLE))

    # 5) Warning on channel pages (e.g. after clicking Proceed on the page-block screen).
    #    A channel page has no channel link to match, so it is detected from the page address
    #    instead, using uBO's :matches-path() (re-checked when you navigate inside YouTube).
    #    That filter can only restyle an existing element, not add text, so it works as a
    #    switch: a static rule draws the notice on body::before but keeps it hidden unless the
    #    CSS variable --aislist-channel-page is "visible"; the address filters set that variable.
    out.append("! --- Warning on channel pages (detected from the page address) ---")
    out.append("youtube.com##body::before:style(%s; "
               "visibility: var(--aislist-channel-page, hidden) !important)" % FLOATING_STYLE)
    paths = [selectors_for(e)[-1][1:].replace(".", "[.]") for e in handles + ids]
    for i in range(0, len(paths), PATH_CHUNK):
        out.append("youtube.com##body:matches-path(/^/(%s)([/?]|$)/i)"
                   ":style(--aislist-channel-page: visible !important)"
                   % "|".join(paths[i:i + PATH_CHUNK]))

    # 6) Warning on mobile Shorts (m.youtube.com/shorts/...). A Short's address has no channel
    #    in it, and the mobile Shorts player's element names are not known, so this is
    #    deliberately generic: on a /shorts/ address, if the page contains a link to a listed
    #    channel, switch the notice on. The address is checked first, so the (expensive) link
    #    search only runs on Shorts pages. Uses ::after because ytm-app::before is already used
    #    by the mobile video-page warning above.
    out.append("! --- Warning on mobile Shorts (m.youtube.com/shorts/ pages) ---")
    out.append("m.youtube.com##ytm-app::after:style(%s; "
               "visibility: var(--aislist-short, hidden) !important)" % FLOATING_STYLE)
    for i in range(0, len(sels), CHUNK):
        out.append("m.youtube.com##ytm-app:matches-path(/^[/]shorts[/]/):has(:is(%s))"
                   ":style(--aislist-short: visible !important)" % ",".join(sels[i:i + CHUNK]))

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
