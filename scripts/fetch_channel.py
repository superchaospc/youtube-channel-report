#!/usr/bin/env python3
"""Fetch one YouTube channel: header stats, every long video and every Short,
each with its exact view count and publish date.

    python3 fetch_channel.py @zazainchina --out WORK/data

Writes WORK/data/<handle>/{about,long,shorts}.json and prints a completeness
check (long + Shorts views should come close to the channel's total views).
"""
import argparse
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import yt  # noqa: E402


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("channel", help="@handle, UC… channel id, or channel URL")
    ap.add_argument("--out", required=True, help="data directory; a sub-folder per channel is created")
    ap.add_argument("--workers", type=int, default=6)
    a = ap.parse_args()

    info = yt.about(a.channel)
    if not info.get("channel_id"):
        sys.exit(f"Could not resolve channel {a.channel!r} (check the handle, or YouTube is blocking this IP).")
    slug = (info.get("handle") or info["channel_id"]).lstrip("@")
    d = os.path.join(os.path.expanduser(a.out), slug)
    os.makedirs(d, exist_ok=True)

    result = {}
    for tab, name in (("videos", "long"), ("shorts", "shorts")):
        items = yt.list_tab(info["channel_id"], tab)
        det = {x["id"]: x for x in yt.details([i["id"] for i in items], a.workers)}
        for it in items:
            x = det.get(it["id"], {})
            it.update(views=x.get("views"), date=x.get("date"), date_text=x.get("date_text"))
            if "error" in x:
                it["error"] = x["error"]
        items.sort(key=lambda v: -(v.get("views") or 0))
        result[name] = items
        with open(os.path.join(d, f"{name}.json"), "w") as f:
            json.dump(items, f, ensure_ascii=False, indent=1)
    with open(os.path.join(d, "about.json"), "w") as f:
        json.dump(info, f, ensure_ascii=False, indent=1)

    lv = sum(v.get("views") or 0 for v in result["long"])
    sv = sum(v.get("views") or 0 for v in result["shorts"])
    bad = [v["id"] for k in result for v in result[k] if v.get("views") is None or not v.get("date")]
    print(f"{info['title']} ({info.get('handle')}, {info['channel_id']})")
    print(f"  subscribers {info['subscribers_text']}, channel views {info['views']:,}, videos {info['video_count']}, joined {info['joined']}")
    print(f"  long   {len(result['long']):4d} videos  {lv:>14,} views")
    print(f"  shorts {len(result['shorts']):4d} videos  {sv:>14,} views")
    if info["views"]:
        print(f"  long+shorts = {(lv + sv) / info['views']:.1%} of channel views (live streams, deleted videos and timing explain small gaps)")
        if not 0.9 <= (lv + sv) / info["views"] <= 1.1:
            print("  WARNING: far from the channel total. Wrong channel resolved (check the id above against the handle),"
                  " a big live-stream archive, or members-only videos. Investigate before computing revenue.")
    if info["video_count"] and len(result["long"]) + len(result["shorts"]) != info["video_count"]:
        print(f"  note: {len(result['long']) + len(result['shorts'])} listed vs {info['video_count']} on the header (members-only or live tab videos?)")
    if bad:
        print(f"  WARNING: {len(bad)} videos without views/date, re-run or check: {bad[:8]}")
    for l in info["links"]:
        print(f"  link: {l['title']} -> {l['url']}")
    print(f"  saved to {d}")


if __name__ == "__main__":
    main()
