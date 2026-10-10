#!/usr/bin/env python3
"""Minimal YouTube innertube client (WEB client, public key). Standard library only.

Used by fetch_channel.py. Everything here reads public pages/endpoints that work
without login; the /player endpoint is deliberately avoided because it is the
first thing YouTube's bot check blocks.
"""
import datetime as dt
import json
import re
import time
import urllib.request
from concurrent.futures import ThreadPoolExecutor

KEY = "AIzaSyAO_FJ2SlqU8Q4STEHLGCilw_Y9_11qcW8"
CTX = {"client": {"clientName": "WEB", "clientVersion": "2.20260901.00.00", "hl": "en", "gl": "US"}}
UA = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/140.0 Safari/537.36"
TAB_PARAMS = {"videos": "EgZ2aWRlb3PyBgQKAjoA", "shorts": "EgZzaG9ydHPyBgUKA5oBAA%3D%3D"}


def call(endpoint, body, retries=3):
    body = dict(body, context=CTX)
    req = urllib.request.Request(
        f"https://www.youtube.com/youtubei/v1/{endpoint}?key={KEY}&prettyPrint=false",
        data=json.dumps(body).encode(),
        headers={"Content-Type": "application/json", "User-Agent": UA, "Accept-Language": "en-US"},
    )
    for attempt in range(retries):
        try:
            return json.load(urllib.request.urlopen(req, timeout=30))
        except Exception:
            if attempt == retries - 1:
                raise
            time.sleep(1.5 * (attempt + 1))


def get_html(url):
    req = urllib.request.Request(url, headers={"User-Agent": UA, "Accept-Language": "en-US"})
    return urllib.request.urlopen(req, timeout=30).read().decode("utf-8", "ignore")


def walk(o, key):
    if isinstance(o, dict):
        for k, v in o.items():
            if k == key:
                yield v
            yield from walk(v, key)
    elif isinstance(o, list):
        for x in o:
            yield from walk(x, key)


def parse_count(s):
    """'1.2M views' / '292K subscribers' / '42,782,282 views' -> int (approximate for K/M)."""
    if not s:
        return 0
    m = re.search(r"([\d.,]+)\s*([KMB]?)", s)
    if not m:
        return 0
    n = float(m.group(1).replace(",", ""))
    return int(n * {"": 1, "K": 1e3, "M": 1e6, "B": 1e9}[m.group(2)])


# ---------------------------------------------------------------- channel

def about(ref):
    """Channel header stats from the /about page. ref = @handle, UC… id or a channel URL."""
    ref = ref.strip()
    m = re.search(r"(UC[\w-]{22})", ref) or None
    if m:
        url = f"https://www.youtube.com/channel/{m.group(1)}/about"
    else:
        h = re.search(r"@([\w.\-]+)", ref)
        handle = h.group(1) if h else ref.lstrip("@")
        url = f"https://www.youtube.com/@{handle}/about"
    s = get_html(url)

    def grab(pat):
        x = re.search(pat, s)
        return x.group(1) if x else None

    links = [
        {"title": t, "url": u}
        for t, u in re.findall(r'"channelExternalLinkViewModel":\{"title":\{"content":"([^"]+)"\},"link":\{"content":"([^"]+)"', s)
    ]
    return {
        # The page also carries other channels' ids (featured/linked channels), so take the
        # channel's own metadata fields first and the first "channelId" only as a last resort.
        "channel_id": grab(r'"externalId":"(UC[\w-]{22})"') or grab(r'<link rel="canonical" href="https://www.youtube.com/channel/(UC[\w-]{22})"')
        or (m.group(1) if m else None) or grab(r'"channelId":"(UC[\w-]{22})"'),
        "handle": grab(r'"vanityChannelUrl":"https?://www.youtube.com/(@[^"]+)"') or grab(r'"canonicalBaseUrl":"/(@[^"]+)"'),
        "title": grab(r'<meta property="og:title" content="([^"]*)"'),
        "subscribers_text": grab(r'"subscriberCountText":"([^"]+)"'),
        "subscribers": parse_count(grab(r'"subscriberCountText":"([^"]+)"')),
        "views": parse_count(grab(r'"viewCountText":"([^"]+)"')),
        "video_count": parse_count(grab(r'"videoCountText":"([^"]+)"')),
        "joined": grab(r'"joinedDateText":\{"content":"Joined ([^"]+)"'),
        "country": grab(r'"country":"([^"]+)"'),
        "links": links,
        "fetched": dt.date.today().isoformat(),
    }


def _conts(r):
    return [c["continuationCommand"]["token"] for c in walk(r, "continuationEndpoint") if isinstance(c, dict) and c.get("continuationCommand")]


def _long_items(r):
    out = []
    for l in walk(r, "lockupViewModel"):
        meta = l.get("metadata", {}).get("lockupMetadataViewModel", {})
        parts = [p.get("text", {}).get("content", "") for row in walk(meta, "metadataParts") for p in row]
        dur = next((b.get("text") for b in walk(l, "thumbnailBadgeViewModel")), None)
        out.append({
            "id": l.get("contentId"),
            "title": meta.get("title", {}).get("content"),
            "views_approx": parse_count(next((p for p in parts if "view" in p), "")),
            "age_text": next((p for p in parts if "ago" in p), ""),
            "duration": dur,
        })
    return out


def _short_items(r):
    out = []
    for l in walk(r, "shortsLockupViewModel"):
        om = l.get("overlayMetadata", {})
        out.append({
            "id": next((e.get("videoId") for e in walk(l, "reelWatchEndpoint")), None),
            "title": om.get("primaryText", {}).get("content"),
            "views_approx": parse_count(om.get("secondaryText", {}).get("content", "")),
        })
    return out


def list_tab(channel_id, tab, max_pages=80):
    """All items on the Videos or Shorts tab. Continuation tokens are de-duplicated:
    on a short channel the only tokens left are sort chips, which loop forever."""
    extract = _long_items if tab == "videos" else _short_items
    r = call("browse", {"browseId": channel_id, "params": TAB_PARAMS[tab]})
    items, seen, pages = extract(r), set(), 0
    toks = _conts(r)
    while toks and pages < max_pages:
        tok = toks[0]
        if tok in seen:
            break
        seen.add(tok)
        pages += 1
        r = call("browse", {"continuation": tok})
        new = extract(r)
        if not new:
            break
        items += new
        toks = _conts(r)
    uniq = {}
    for it in items:
        if it["id"] and it["id"] not in uniq:
            uniq[it["id"]] = it
    return list(uniq.values())


# ---------------------------------------------------------------- per video

_REL = re.compile(r"(\d+)\s+(second|minute|hour|day|week|month|year)s?\s+ago")


def parse_date(text, today=None):
    """'Dec 1, 2025' / 'Premiered Dec 1, 2025' / 'Streamed live on …' / '18 hours ago' -> ISO date."""
    if not text:
        return None
    t = re.sub(r"^(Premiered|Streamed live on|Started streaming on|Published on)\s+", "", text.strip())
    for fmt in ("%b %d, %Y", "%d %b %Y"):
        try:
            return dt.datetime.strptime(t, fmt).date().isoformat()
        except ValueError:
            pass
    m = _REL.search(t)
    if m:
        n, unit = int(m.group(1)), m.group(2)
        days = {"second": 0, "minute": 0, "hour": n / 24, "day": n, "week": 7 * n, "month": 30 * n, "year": 365 * n}[unit]
        return ((today or dt.date.today()) - dt.timedelta(days=days)).isoformat()
    return None


def video_detail(vid):
    """Exact view count + publish date from the /next endpoint (works when /player is bot-blocked).
    originalViewCount is often the string "0" now, so fall back to the full 'N views' text."""
    last = None
    for _ in range(3):
        try:
            r = call("next", {"videoId": vid})
            vc = next((x for x in walk(r, "videoViewCountRenderer") if isinstance(x, dict)), {})
            orig = vc.get("originalViewCount")
            text = (vc.get("viewCount") or {}).get("simpleText") or "".join(
                x.get("text", "") for x in (vc.get("viewCount") or {}).get("runs", []))
            views = int(orig) if orig and orig != "0" else int(re.sub(r"\D", "", text) or 0)
            date_text = next((d.get("simpleText") for d in walk(r, "dateText") if isinstance(d, dict) and d.get("simpleText")), None)
            return {"id": vid, "views": views, "date": parse_date(date_text), "date_text": date_text}
        except Exception as e:  # noqa: BLE001 - network flakiness, retry
            last = repr(e)
            time.sleep(1)
    return {"id": vid, "error": last}


def details(ids, workers=6):
    with ThreadPoolExecutor(workers) as ex:
        return list(ex.map(video_detail, ids))
