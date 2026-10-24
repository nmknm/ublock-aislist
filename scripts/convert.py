#!/usr/bin/env python3
"""Convert the AiSList YouTube channel blocklist into a uBlock Origin filter list.

Input  : upstream aislist_blocklist.txt (one `@handle` or `UC...` channel ID per line, `!` comments)
Output : aislist_ublock.txt (uBO filters for youtube.com)

The output is deterministic: it contains no "now" timestamp, so re-running on an
unchanged upstream produces a byte-identical file (and therefore no new commit).

Performance note
----------------
An earlier version expressed "this link points to a listed channel" as ~34,000 CSS attribute
selectors inside `:has()`. The browser has to test every link on the page against every one
of those selectors, which made YouTube lag badly. This version instead packs the channels
into a handful of compact regular expressions (a prefix tree, so a test costs about as much
as the length of the link) and lets uBO's procedural engine apply them, one quick test per link.
Network filters (the "page blocked" screen) are hashed by uBO and stay cheap.

Usage:  python3 -I scripts/convert.py INPUT OUTPUT [--compatible]

--compatible writes the version for Brave, AdGuard and other blockers (see README).
"""
import random
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
    "ytm-compact-channel-renderer",
    "ytm-compact-playlist-renderer",
]

CHANNEL_ID_RE = re.compile(r"^UC[A-Za-z0-9_-]{22}$")
# Anything except whitespace and characters that could break the CSS attribute
# selector / filter syntax (handles in many scripts contain combining marks,
# so a strict \w match is too narrow).
HANDLE_RE = re.compile(r"^@[^\s\"'\\\[\]{}()<>,;:#%/?&=+*^$|`~!]{1,200}$")
LAST_MODIFIED_RE = re.compile(r"^!\s*Last Modified:\s*(\S+)", re.IGNORECASE)

NOTICE = "⚠ This channel is on the AiSList AI-content list"

# Notice drawn above the video title on desktop watch pages of listed channels. It is shown by
# switching `display` from none (default) to block through the variable --aislist-watch.
# (uBO forbids url(), backslashes and comments in :style(), so the text is plain Unicode.)
WATCH_STYLE = (
    'content: "@@NOTICE@@" !important; '
    "display: var(--aislist-watch, none) !important; width: fit-content !important; "
    "background: #b00020 !important; color: #fff !important; "
    "padding: 6px 12px !important; margin-bottom: 8px !important; "
    "border-radius: 8px !important; "
    "font: 600 14px/1.3 Roboto, Arial, sans-serif !important"
).replace("@@NOTICE@@", NOTICE)

# Same notice as a small floating label, for pages with no title to attach it to.
# Fixed to the viewport, never intercepts taps/clicks. Hidden unless a variable is "visible".
FLOATING_STYLE = (
    'content: "@@NOTICE@@" !important; '
    "position: fixed !important; top: 60px !important; left: 50% !important; "
    "transform: translateX(-50%) !important; z-index: 2147483647 !important; "
    "pointer-events: none !important; max-width: 90vw !important; "
    "box-sizing: border-box !important; text-align: center !important; "
    "background: #b00020 !important; color: #fff !important; "
    "padding: 6px 12px !important; border-radius: 8px !important; "
    "box-shadow: 0 2px 8px rgba(0,0,0,.45) !important; "
    "font: 600 14px/1.3 Roboto, Arial, sans-serif !important"
).replace("@@NOTICE@@", NOTICE)


def floating(var):
    return "%s; visibility: var(%s, hidden) !important" % (FLOATING_STYLE, var)


# Channels per regular expression. Each procedural filter carries one of these, so this trades
# the number of filters (each costs a little per page change) against the length of a filter line.
CHUNK = 1500


def spellings(entry):
    """Text after the leading slash in the page address, lower-cased, for one entry:
    '@name' (and its percent-encoded twin for non-ASCII handles), or 'channel/UC...'."""
    if entry.startswith("@"):
        out = {entry.lower()}
        encoded = quote(entry, safe="@-_.")
        out.add(encoded.lower())
        return out
    return {("channel/" + entry).lower()}


def network_path(entry):
    """Path used by the network (page blocked) filters: percent-encoded, as browsers send it."""
    if entry.startswith("@"):
        return "/" + quote(entry, safe="@-_.")
    return "/channel/" + entry


# ---- compact regular expressions ---------------------------------------------------------

def _trie(words):
    root = {}
    for w in words:
        node = root
        for ch in w:
            node = node.setdefault(ch, {})
        node[""] = True  # end of a word
    return root


def _esc(ch, fold=False):
    # Only "." can occur among the characters HANDLE_RE and the ID pattern allow.
    if ch == ".":
        return "[.]"
    # fold: spell out case-insensitivity (a -> [aA]) for blockers whose regexes cannot take flags.
    return "[%s%s]" % (ch, ch.upper()) if fold and ch.isalpha() and ch.upper() != ch else ch


def _regex(node, fold=False):
    kids = sorted(k for k in node if k != "")
    if not kids:
        return ""
    ends_here = "" in node
    alts = []
    # Collapse sibling letters that end a word into one character class, e.g. [abc].
    leaves = [k for k in kids if list(node[k].keys()) == [""]]
    if len(leaves) >= 2:
        plain = "".join(c for c in leaves if c not in ".-")
        if fold:
            plain += "".join(c.upper() for c in plain if c.isalpha() and c.upper() != c)
        alts.append("[%s%s%s]" % (plain, "." if "." in leaves else "", "-" if "-" in leaves else ""))
        kids = [k for k in kids if k not in leaves]
    alts += [_esc(k, fold) + _regex(node[k], fold) for k in kids]
    if len(alts) == 1 and not ends_here:
        return alts[0]
    # Group needed: several alternatives, or a word that may end here or continue.
    return "(%s)" % "|".join(alts) + ("?" if ends_here else "")


ASCII_KEYS = set("abcdefghijklmnopqrstuvwxyz0123456789_-.")


def partition(words, size=CHUNK):
    """Split lower-cased words (each starting '@' or 'channel/') into chunks of at most `size`
    words, grouped by their first character. Returns [(keys, words)]: `keys` is the list of
    first characters the chunk covers, or None for the "everything else" chunk (non-ASCII and
    percent-encoded handles), which has to look at all links.

    Why: each filter only needs to be handed the links whose address starts with its own first
    letters, so a link is tested by roughly one filter instead of by all of them."""
    words = sorted(words)
    if not words[0].startswith("@"):
        return [(None, words[i:i + size]) for i in range(0, len(words), size)]
    by_key, other = {}, []
    for w in words:
        if w[1:2] in ASCII_KEYS:
            by_key.setdefault(w[1], []).append(w)
        else:
            other.append(w)
    chunks, cur_keys, cur = [], [], []

    def flush():
        nonlocal cur_keys, cur
        if cur:
            chunks.append((cur_keys, cur))
        cur_keys, cur = [], []

    for key in sorted(by_key):
        group = by_key[key]
        if len(group) > size:                     # a very common first letter: slice it
            flush()
            chunks += [([key], group[i:i + size]) for i in range(0, len(group), size)]
            continue
        if len(cur) + len(group) > size:
            flush()
        cur_keys.append(key)
        cur += group
    flush()
    chunks += [(None, other[i:i + size]) for i in range(0, len(other), size)]
    return chunks


def chunk_regex(words, fold=False):
    """One compact regex body for a set of words."""
    return _regex(_trie(words), fold)


def chunk_anchor(keys, base):
    """Selector for the links a chunk must look at. `i` makes the match ASCII case-insensitive."""
    if keys is None:
        return 'a[href^="%s"]' % base
    parts = ['[href^="%s%s" i]' % (base, k) for k in keys]
    return "a" + parts[0] if len(parts) == 1 else "a:is(%s)" % ",".join(parts)


# The compatible profile writes its patterns so that every blocker's regex engine takes them:
#  - no "/" inside the literal (Brave splits the literal on every "/"): the "/" in "/@name" and
#    "/channel/UC..." becomes "." (any character), and the end of the name is checked with a
#    look-ahead instead of [/?#]. A name may continue with letters, digits, "_", ".", "-", "%".
#  - no flags (AdGuard's regexes cannot carry any): case-insensitivity is spelled out as [aA].
COMPAT_END = "(?![a-zA-Z0-9_.%-])"


def link_regex(body, compat=False):
    """Regex literal matching a page address that starts with one of the words."""
    if compat:
        return "/^.(%s)%s/" % (body.replace("/", "."), COMPAT_END)
    return "/^/(%s)([/?#]|$)/i" % body


def self_check(words_all, bodies, compat=False):
    """Fail loudly if the compact patterns do not match exactly the listed words."""
    if compat:
        res = [re.compile("^.(%s)%s" % (b.replace("/", "."), COMPAT_END)) for b in bodies]
    else:
        res = [re.compile("^/(%s)(?:[/?#]|$)" % b, re.IGNORECASE) for b in bodies]
    wordset = set(words_all)

    def matches(text):
        return any(r.match(text) for r in res)

    for w in words_all:
        for suffix in ("", "/videos", "?si=x"):
            if not matches("/" + w + suffix):
                sys.exit("self-check failed: %r is not matched" % (w + suffix))
            if compat and not (matches("/" + w.upper() + suffix) and matches("/" + w.swapcase() + suffix)):
                sys.exit("self-check failed: %r is not matched in other letter cases" % (w + suffix))
    rng = random.Random(1234)
    sample = rng.sample(words_all, min(len(words_all), 4000))
    for w in sample:
        for cand in (w + "x", w[:-1], w[:-1] + "x", w + "-"):
            if (cand in wordset) != matches("/" + cand) and cand:
                sys.exit("self-check failed: %r wrongly %s" %
                         (cand, "rejected" if cand in wordset else "matched"))
    for cand in ("", "watch?v=abc", "feed/subscriptions", "@", "@zz-not-a-listed-channel-zz"):
        if cand not in wordset and matches("/" + cand):
            sys.exit("self-check failed: %r should not match" % cand)


MARK_BOX = ("background: rgba(176,0,32,.10) !important; outline: 3px solid #b00020 !important; "
            "outline-offset: -3px !important; border-radius: 12px !important")
MARK_PAGE = "outline: 6px solid #b00020 !important; outline-offset: -6px !important"


def main(src, dst, compat=False):
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

    if compat:
        title = "AiSList - YouTube AI Slop Channels (compatible)"
        desc = ("Version of the AiSList community blocklist for Brave, AdGuard and other blockers that "
                "cannot show uBlock Origin's warning screen and text notices. Blocks the pages of, hides "
                "videos from, and marks pages of YouTube channels flagged as AI-generated content.")
    else:
        title = "AiSList - YouTube AI Slop Channels (uBlock Origin)"
        desc = ("uBlock Origin version of the AiSList community blocklist. Warns about, and hides "
                "videos from, YouTube channels flagged as AI-generated content.")
    out = [
        "[Adblock Plus 2.0]",
        "! Title: " + title,
        "! Description: " + desc,
        "! Homepage: https://aisloplist.com",
        "! Source: https://github.com/Override92/AiSList",
        "! License: CC BY-NC 4.0 https://creativecommons.org/licenses/by-nc/4.0/",
        "! Credit: channel data by the AiSList community (Override92/AiSList), used under CC BY-NC 4.0",
        "! Changes: converted from the original handle list to " + ("" if compat else "uBlock Origin ") + "page-block, warning and "
        "card-hiding filters; duplicates removed. Unofficial - not affiliated with or endorsed by the "
        "AiSList authors.",
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
        out.append("||youtube.com%s^$document" % network_path(entry))

    # Compact patterns, one group per kind of link.
    handle_words = sorted({w for h in handles for w in spellings(h)})
    id_words = sorted({w for c in ids for w in spellings(c)})
    groups = []  # (anchor selector, regex literal) for every chunk
    for words, base in ((handle_words, "/@"), (id_words, "/channel/")):
        if not words:
            continue
        first = 1 if base == "/@" else len("channel/")  # index of the first letter after the prefix
        bodies = []
        for keys, chunk in partition(words):
            if keys is not None:
                # Every word must start with one of the chunk's first letters, otherwise the
                # filter would never be handed the link for that channel.
                assert all(w[first] in keys for w in chunk), "chunk/selector mismatch"
            body = chunk_regex(chunk, fold=compat)
            bodies.append(body)
            groups.append((chunk_anchor(keys, base), link_regex(body, compat)))
        self_check(words, bodies, compat)

    def procedural(host, scope, tail):
        """One filter per chunk: <scope><links>:matches-attr(href=<regex>)<tail>."""
        for anchor, rx in groups:
            out.append('%s##%s%s:matches-attr("href"="%s")%s' % (host, scope, anchor, rx, tail))

    # 2) Hide listed channels' video/channel/playlist cards in feeds and search results.
    out.append("! --- Hide cards of listed channels ---")
    # Cards nest (a grid cell wraps a lockup; on mobile a media item sits inside a rich item), and
    # :upward() returns the nearest match. Match only a card that has no card around it, so the
    # whole outer cell is hidden and no empty gap is left in the grid.
    cards = ",".join(CONTAINERS)
    procedural("youtube.com", "", ":upward(:is(%s):not(:is(%s) *))" % (cards, cards))

    if not compat:
        # Each warning is scoped to the site it belongs to (www = desktop, m = mobile), so the filters
        # for the other site are never loaded or run. The card hiding and the page-address warning
        # apply to both.
        #
        # Warnings. A text notice can only be added by a CSS rule (::before/::after with `content`),
        # while the decision "is this a listed channel?" is made by the filters above, which can
        # only restyle an element. So each warning has two halves: a static rule that draws the
        # notice but keeps it hidden unless a CSS variable is set, and filters that set that variable
        # on a page element when the page shows a listed channel.

        # 3) Desktop video pages: notice above the title when the channel under the video is listed.
        out.append("! --- Warning above the title on video pages ---")
        out.append("www.youtube.com##ytd-watch-metadata #title::before:style(%s)" % WATCH_STYLE)
        procedural("www.youtube.com", "ytd-watch-metadata #owner ",
                   ":upward(ytd-watch-metadata):style(--aislist-watch: block !important)")

        # 4) Desktop Shorts: the channel shown on the Short.
        out.append("! --- Warning on desktop Shorts ---")
        out.append("www.youtube.com##body::after:style(%s)" % floating("--aislist-dshort"))
        # Seen on a real page: the Short's channel link (href="/@handle/shorts") is inside
        # yt-reel-channel-bar-view-model. There was no [is-active] marker among its nearest ancestors,
        # so the active Short can't be told apart: a neighbouring Short that is loaded into the page
        # can also trigger the notice.
        procedural("www.youtube.com", "yt-reel-channel-bar-view-model ",
                   ":upward(body):style(--aislist-dshort: visible !important)")

        # 5) Mobile video pages: the channel under the video.
        out.append("! --- Warning on mobile video pages ---")
        # (shares the floating label drawn for mobile Shorts below)
        # The uploader link is inside the metadata section (seen on a real page: it sits in the
        # action bar under the title); the owner renderer is kept for other layouts.
        procedural("m.youtube.com", ":is(ytm-slim-video-metadata-section-renderer,ytm-slim-owner-renderer) ",
                   ":upward(body):style(--aislist-mshort: visible !important)")

        # 6) Mobile Shorts (m.youtube.com/shorts/...). A Short's address has no channel in it and the
        #    mobile Shorts player's element names are not known, so this is deliberately generic: on
        #    a /shorts/ address, any link to a listed channel switches the notice on. The address is
        #    checked first, so the link search only runs on Shorts pages.
        out.append("! --- Warning on mobile Shorts (m.youtube.com/shorts/ pages) ---")
        out.append("m.youtube.com##body::after:style(%s)" % floating("--aislist-mshort"))
        procedural("m.youtube.com", "body:matches-path(/^[/]shorts[/]/) ",
                   ":upward(body):style(--aislist-mshort: visible !important)")

        # 7) Channel pages (e.g. after clicking Proceed on the page-block screen). A channel page has
        #    no channel link to match, so it is detected from the page address with :matches-path()
        #    (re-checked when you navigate inside YouTube).
        out.append("! --- Warning on channel pages (detected from the page address) ---")
        out.append("youtube.com##body::before:style(%s)" % floating("--aislist-channel-page"))
        for _anchor, rx in groups:
            out.append("youtube.com##body:matches-path(%s):style(--aislist-channel-page: visible !important)" % rx)
    else:
        # Compatible profile. Only features that Brave's and AdGuard's engines have: no text notices
        # (they need ::before/::after rules plus CSS variables) and no path checks on page-level
        # elements. A listed channel is instead *marked*: the element around its name on video
        # pages and Shorts gets a red tint/outline, and so does the whole page on mobile Shorts and
        # channel pages. Every filter starts at a link, because blockers such as Brave only re-check
        # elements that were just added to the page, and a link is always added when a page loads.
        out.append("! --- Mark video pages and Shorts (red frame around the channel/title block) ---")
        # One filter set for all three: desktop video page, mobile video page, desktop Short. The
        # nearest of these elements around the channel link gets the frame.
        procedural("youtube.com",
                   ":is(ytd-watch-metadata #owner,ytm-slim-video-metadata-section-renderer,"
                   "ytm-slim-owner-renderer,yt-reel-channel-bar-view-model) ",
                   ":upward(:is(ytd-watch-metadata,ytm-slim-video-metadata-section-renderer,"
                   "ytm-slim-owner-renderer,yt-reel-player-overlay-view-model)):style(%s)" % MARK_BOX)
        # Mobile Shorts: the address is checked first (it has no channel in it), then any link to a
        # listed channel on the page marks it. Generic, like the uBlock Origin version.
        procedural("m.youtube.com", "", ":matches-path(/^.shorts./):upward(body):style(%s)" % MARK_PAGE)
        out.append("! --- Mark channel pages (red frame, detected from the page address) ---")
        for _anchor, rx in groups:
            out.append("youtube.com##a:is([href^=\"/@\" i],[href^=\"/channel/\" i]):matches-path(%s)"
                       ":upward(body):style(%s)" % (rx, MARK_PAGE))

    with open(dst, "w", encoding="utf-8", newline="\n") as fh:
        fh.write("\n".join(out) + "\n")

    longest = max(len(l) for l in out)
    print("handles: %d  channel IDs: %d  duplicates dropped: %d  skipped: %d"
          % (len(handles), len(ids), dupes, len(skipped)))
    print("filter lines: %d  longest line: %d characters" % (len(out), longest))
    for s in skipped[:20]:
        print("  skipped:", s)


if __name__ == "__main__":
    args = [a for a in sys.argv[1:] if a != "--compatible"]
    if len(args) != 2:
        sys.exit(__doc__)
    main(args[0], args[1], compat="--compatible" in sys.argv)
