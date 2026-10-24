# AiSList for uBlock Origin

An auto-updating, **unofficial** uBlock Origin version of the community
[AiSList](https://github.com/Override92/AiSList) blocklist of AI-generated YouTube channels.

A GitHub Action checks upstream every 6 hours, converts the list with `scripts/convert.py`, and
commits `aislist_ublock.txt` only when something changed. uBlock Origin refreshes the list on its
own (it asks for a 1-day refresh).

## Install

**One click:** [Subscribe in uBlock Origin](https://subscribe.adblockplus.org/?location=https%3A%2F%2Fraw.githubusercontent.com%2Fnmknm%2Fublock-aislist%2Fmain%2Faislist_ublock.txt&title=AiSList%20for%20uBlock%20Origin)

**Manual:** uBlock Origin → Dashboard → **Filter lists** → **Import…** → paste

```
https://raw.githubusercontent.com/nmknm/ublock-aislist/main/aislist_ublock.txt
```

then click **Apply changes**.

## What it does

For about 34,000 listed channels, it does three things:

1. **Warns before opening a channel page.** If you open a listed channel's page (for example from a
   link on another site, a bookmark, or a typed URL), uBlock Origin shows its "page blocked" screen,
   naming this list, with a **Proceed** button.
2. **Warns on video pages.** When you watch a video from a listed channel, a red notice appears above
   the video title: "This channel is on the AiSList AI-content list". This also works when you click
   through from inside YouTube.
3. **Warns on Shorts and on the mobile site.** On desktop Shorts, and on video pages on
   m.youtube.com, the same notice appears as a small floating label near the top of the screen.
4. **Hides their videos.** Video, channel and playlist cards from listed channels are hidden in feeds,
   search results and suggestions.

The "page blocked" screen also works on m.youtube.com.

## Known limitations

- **The "page blocked" screen only appears on full page loads.** YouTube moves between pages without
  reloading, so clicking a channel from inside YouTube won't trigger it. The video-page notices and the
  hidden cards cover that case.
- **Shorts cards in feeds and shelves can't be hidden**, because they don't show a channel link. The
  notice appears once you open the Short.
- **Shorts on the mobile site are not covered yet.**
- **Not yet confirmed on live YouTube for Shorts and mobile.** These notices rely on YouTube's page
  structure (element names), which I could only check against test pages, not the real site. If a
  notice doesn't appear, please open an issue saying which page you were on and in which browser.
- YouTube changes its page structure from time to time; the notices or the hiding may stop working
  until the list is updated.
- The list is large (about 5 MB), so loading or updating it can take a moment.
- On the warning screen, choose plain **Proceed**. The "don't warn again" options apply to the whole
  site, not to one channel.

## Wrong channel on the list?

Channel data comes from upstream, so report false positives or additions there:
<https://github.com/Override92/AiSList/issues>. Fixes arrive here automatically after the next sync.
Use this repo's issues only for problems with the uBlock Origin conversion.

## Credit and license

All channel data comes from **AiSList** by Override92 and its contributors
(<https://github.com/Override92/AiSList>, <https://aisloplist.com>), licensed
[CC BY-NC 4.0](https://creativecommons.org/licenses/by-nc/4.0/).

Changes made here: the list is converted into uBlock Origin cosmetic filters and duplicate entries
are removed. This project is not affiliated with or endorsed by the AiSList authors. As required by
the license, it may be used for non-commercial purposes only.

The conversion script (`scripts/convert.py`) is released under the MIT license.
