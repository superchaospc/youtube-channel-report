#!/usr/bin/env python3
"""视频时长 section: duration bands vs views, month-by-month average length.

    python3 duration_stats.py DATA/<handle> --out OUT/duration.json --slides OUT/duration_slides.json \
        [--from 2026-03-01]   # leave out an early phase that is a different kind of video

Reads long.json from fetch_channel.py. --slides writes three ready deck.json slides (stats4 + two
tables, with "portrait" and keyword "video" overrides) to splice into the deck under section
"视频时长". Duration and views both drift with time (early videos are short *and* the channel was
small), so the table note says the bands are a correlation, not a cause.
"""
import argparse, json, os, statistics as st

ap = argparse.ArgumentParser()
ap.add_argument("data")
ap.add_argument("--out", required=True)
ap.add_argument("--slides")
ap.add_argument("--from", dest="since", default="", help="only count videos published on/after this date (YYYY-MM-DD)")
a = ap.parse_args()

def minutes(t):
    s = 0
    for x in str(t).split(":"): s = s * 60 + int(x)
    return s / 60
L = sorted(json.load(open(os.path.join(a.data, "long.json"))), key=lambda v: v["date"])
L = [dict(v, m=minutes(v["duration"])) for v in L if v.get("duration")]
L2 = [v for v in L if v["date"] >= a.since]
wan = lambda x: f"{x / 1e4:.1f} 万"
BANDS = [(0, 10, "10 分钟以内"), (10, 15, "10–15 分钟"), (15, 20, "15–20 分钟"), (20, 30, "20–30 分钟"), (30, 999, "30 分钟以上")]
bands = []
for lo, hi, label in BANDS:
    vs = [v for v in L2 if lo <= v["m"] < hi]
    if vs:
        bands.append({"band": label, "n": len(vs), "avg_views": st.mean(v["views"] for v in vs), "median_views": st.median(v["views"] for v in vs)})
months = {}
for v in L: months.setdefault(v["date"][:7], []).append(v["m"])
top10 = sorted(L, key=lambda v: -v["views"])[:10]
res = {"n": len(L), "mean": st.mean(v["m"] for v in L), "median": st.median(v["m"] for v in L),
       "top10_mean": st.mean(v["m"] for v in top10), "over8_share": sum(v["m"] >= 8 for v in L2) / max(len(L2), 1),
       "since": a.since, "bands": bands,
       "months": [{"month": k, "n": len(x), "mean": st.mean(x)} for k, x in sorted(months.items())]}
json.dump(res, open(a.out, "w"), ensure_ascii=False, indent=1)
print(f"{res['n']} long videos: mean {res['mean']:.1f} min, median {res['median']:.1f}, top-10 mean {res['top10_mean']:.1f}, ≥8 min {res['over8_share']:.0%}")
for b in bands: print(f"  {b['band']:<10} {b['n']:>3} 条  平均 {wan(b['avg_views'])}  中位 {wan(b['median_views'])}")
for m in res["months"]: print(f"  {m['month']}  {m['n']:>2} 条  {m['mean']:.1f} 分钟")

if a.slides:
    best = max(bands, key=lambda b: b["avg_views"])
    worst = min(bands, key=lambda b: b["avg_views"])
    cols = lambda *s: [dict(label=l, align=al, width=w) for l, al, w in s]
    rows = [[b["band"], str(b["n"]), wan(b["avg_views"]), wan(b["median_views"])] for b in bands]
    ms = [m for m in res["months"] if m["month"] >= (a.since[:7] or "0")]
    first, last = ms[0], ms[-1]
    mrows = [[f"{int(m['month'][5:])} 月", str(m["n"]), f"{m['mean']:.1f} 分钟"] for m in ms]
    trend = "越拍越长" if last["mean"] > first["mean"] * 1.2 else "越拍越短" if last["mean"] < first["mean"] * 0.8 else "时长一直差不多"
    slides = [
        {"type": "stats4", "eyebrow": "视频时长", "section": "视频时长",
         "title": f"平均 {res['mean']:.1f} 分钟，{best['band']}平均播放更高",
         "tiles": [{"label": "平均时长", "value": f"{res['mean']:.1f} 分钟", "sub": f"{res['n']} 条长视频", "dark": True},
                   {"label": "中位数", "value": f"{res['median']:.1f} 分钟", "sub": "一半视频比这短"},
                   {"label": "播放前 10 条", "value": f"{res['top10_mean']:.1f} 分钟", "sub": "平均时长"},
                   {"label": "8 分钟以上", "value": f"{res['over8_share'] * 100:.0f}%", "sub": "能插中间广告"}],
         "bullets": [f"{best['band']} {best['n']} 条，平均 {wan(best['avg_views'])} 播放",
                     f"{worst['band']} {worst['n']} 条，平均只有 {wan(worst['avg_views'])}"],
         "video": {"bullets": [f"{best['band']}播放更高", f"{worst['band']}偏低"]}},
        {"type": "table", "eyebrow": "视频时长", "title": f"时长分段：{best['band']}平均 {wan(best['avg_views'])}",
         "columns": cols(("时长", "left", 0.34), ("条数", "right", 0.18), ("平均播放", "right", 0.24), ("中位播放", "right", 0.24)),
         "rows": rows, "bold_col": 2, "font_size": 15, "row_h": 0.5,
         "note": "时长和发布时间有关：早期视频往往短、频道也小，不全是时长的作用。" + (f"只算 {a.since} 以后发布的视频。" if a.since else ""),
         "portrait": {"columns": cols(("时长", "left", 0.4), ("条数", "right", 0.2), ("平均播放", "right", 0.4)), "rows": [r[:3] for r in rows], "bold_col": 2},
         "video": {"columns": cols(("时长", "left", 0.55), ("平均播放", "right", 0.45)), "rows": [[r[0], r[2]] for r in rows], "bold_col": 1}},
        {"type": "table", "eyebrow": "视频时长",
         "title": f"{trend}：{int(first['month'][5:])} 月平均 {first['mean']:.1f} 分钟，{int(last['month'][5:])} 月 {last['mean']:.1f} 分钟",
         "columns": cols(("月份", "left", 0.34), ("发了几条", "right", 0.3), ("平均时长", "right", 0.36)),
         "rows": mrows[-8:], "bold_col": 2, "font_size": 15, "row_h": 0.46,
         "note": "按发布月份统计长视频的平均时长。",
         "video": {"columns": cols(("月份", "left", 0.5), ("平均时长", "right", 0.5)), "rows": [[r[0], r[2]] for r in mrows[-7:]], "bold_col": 1}},
    ]
    json.dump(slides, open(a.slides, "w"), ensure_ascii=False, indent=1)
    print(f"wrote {len(slides)} slides to {a.slides} — check the titles, then splice them in under 视频时长")
