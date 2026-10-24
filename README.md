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
3. **Warns on Shorts and on the mobile site.** On desktop Shorts, on mobile Shorts, and on video pages
   on m.youtube.com, the same notice appears as a small floating label near the top of the screen.
4. **Warns on channel pages.** After you click **Proceed** on the "page blocked" screen, the same
   floating notice stays on the channel page, so you're reminded while you browse it. It's matched by
   the page address, so it also appears when you open a listed channel from inside YouTube.
5. **Hides their videos.** Video, channel and playlist cards from listed channels are hidden in feeds,
   search results and suggestions.

The "page blocked" screen and the channel-page notice also work on m.youtube.com.

## Performance

An earlier version made the browser compare every link on a YouTube page with about 34,000 separate
filters, which made YouTube lag badly. Channels are now packed into a few compact patterns, and each
link is tested once. On a test page of 300 video cards, in headless Chromium:

| | Old | Now |
|---|---|---|
| Load 300 cards | 28 s | 0.3 s |
| A new card appears (scrolling) | 59 ms | 8 ms |
| A page of 12 new cards appears | 500 ms | 10 ms |

The same cards are hidden as before. These are lab numbers from a simplified test page (YouTube's real
pages are heavier), but the difference is large. The conversion script checks its own patterns on every
update, and refuses to publish a list that doesn't match the channels exactly.

## Known limitations

- **The "page blocked" screen only appears on full page loads.** YouTube moves between pages without
  reloading, so clicking a channel from inside YouTube won't trigger it. The video-page notices and the
  hidden cards cover that case.
- **Needs the full uBlock Origin, up to date.** The card hiding and the notices use uBlock Origin's
  scripted ("procedural") filters, including `:matches-path`. They don't work in uBlock Origin Lite.
  If the notices never appear, update uBlock Origin. Detection by page address is reliable; the notice
  itself is a plain label that doesn't depend on YouTube's page structure.
- **Hidden cards can flash briefly.** Cards are hidden by uBlock Origin right after YouTube adds them to
  the page, not before, so a card may be visible for a moment before it disappears.
- **Shorts cards in feeds and shelves can't be hidden**, because they don't show a channel link. The
  notice appears once you open the Short.
- **Mobile Shorts (m.youtube.com/shorts/...) use a generic check.** The notice appears when you are on
  a Shorts address and the page contains a link to a listed channel. It doesn't know which Short is
  on screen, so it can appear a little early or late if a neighbouring Short from a listed channel is
  loaded in the page, or if a listed channel is linked elsewhere on the page (for example in comments).
- **Not yet confirmed on live YouTube for Shorts and mobile.** These notices rely on YouTube's page
  structure (element names), which I could only check against test pages, not the real site. If a
  notice doesn't appear, please open an issue saying which page you were on and in which browser.
- YouTube changes its page structure from time to time; the notices or the hiding may stop working
  until the list is updated.
- The list is about 3.6 MB, so loading or updating it takes a moment.
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

Changes made here: the list is converted into uBlock Origin page-block, warning and card-hiding
filters, and duplicate entries are removed. This project is not affiliated with or endorsed by the AiSList authors. As required by
the license, it may be used for non-commercial purposes only.

The conversion script (`scripts/convert.py`) is released under the MIT license.
