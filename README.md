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

Hides video, channel and playlist cards on youtube.com that link to a listed channel
(about 34,000 channels).

## Known limitations

- Shorts and other cards that don't expose a channel link may not be hidden.
- The list is large, so YouTube pages may load a little slower.
- YouTube changes its page structure from time to time; if cards stop being hidden, open an issue.

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
