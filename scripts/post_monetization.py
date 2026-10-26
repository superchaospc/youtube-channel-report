#!/usr/bin/env python3
"""Revenue counted only after the channel was monetized, plus a 12-month projection.

Default income view for every channel report (user requirement, 2026-10-26): money starts when the
channel joined the Partner Program, not at the first upload, and the report also projects the next
12 months from how the channel is doing right now.

  python3 post_monetization.py data/<handle> data_later/<handle> --monetized 2026-07-01 --rpm 4 \
      --numbers out/numbers.json --titles titles_zh.json \
      --out out/post_monetization.json --md out/post_monetization.md --slides out/money_slides.json

Two fetch_channel.py snapshots of the same channel taken some hours apart (8+ hours is enough) give
every video's current daily views. From those:

1. Views after monetization.
   - Videos published on or after the monetization date: every view counts.
   - Older videos: only views gained since then. Not public, so estimated from today's daily views.
     If a viral video came out after monetization (default: the most-viewed video, when it is at least
     3x the runner-up), it lifts the whole catalog, so today's rates are inflated: the days since the viral
     video count at today's rate, the earlier days at --pre-factor (0.25) of it. Without a viral video
     every day counts at today's rate. Each video is capped at --cap (50%) of its current views.
2. Next 12 months, at the same RPM.
   - Viral video + videos younger than 30 days: today's daily views, halving every --hl-fast (45) days.
   - The rest of the catalog: today's daily views, halving every --hl-slow (120) days.
   - New videos: --per-month uploads (default: long videos in the last 60 days / 2) x the average views
     of post-monetization videos (viral one excluded) x --in-window (0.85, late uploads earn partly
     after the window). No new viral hit is assumed.

Shorts are left out (their revenue is tiny). Run it on the main channel; a sub-channel gets its own run.
"""
import argparse, datetime as dt, json, math, os, statistics as st

p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
p.add_argument("earlier", help="fetch_channel.py channel folder (first snapshot)")
p.add_argument("later", help="same channel fetched again some hours later")
p.add_argument("--monetized", required=True, help="YYYY-MM-DD the channel started earning (see rpm-and-income.md)")
p.add_argument("--rpm", type=float, required=True)
p.add_argument("--fx", type=float, help="USD->CNY; default: fx in --numbers")
p.add_argument("--numbers", help="out/numbers.json from compute_report.py (for fx and as_of)")
p.add_argument("--as-of", help="YYYY-MM-DD, default: date of the earlier snapshot")
p.add_argument("--titles", help="titles_zh.json")
p.add_argument("--viral", help="video id of the hit that lifted the catalog; 'none' to disable")
p.add_argument("--pre-factor", type=float, default=0.25)
p.add_argument("--cap", type=float, default=0.5)
p.add_argument("--hl-fast", type=float, default=45)
p.add_argument("--hl-slow", type=float, default=120)
p.add_argument("--per-month", type=float)
p.add_argument("--in-window", type=float, default=0.85)
p.add_argument("--out", required=True)
p.add_argument("--md")
p.add_argument("--slides")
a = p.parse_args()

J = lambda f: json.load(open(f))
numbers = J(a.numbers) if a.numbers else {}
FX = a.fx or numbers.get("fx")
if not FX:
    p.error("give --fx or --numbers")
RPM = a.rpm
first, later = os.path.join(a.earlier, "long.json"), os.path.join(a.later, "long.json")
t0, t1 = os.path.getmtime(first), os.path.getmtime(later)
HRS = (t1 - t0) / 3600
if HRS < 4:
    p.error(f"snapshots only {HRS:.1f} h apart; fetch again later (8+ hours) for usable daily views")
A = {v["id"]: v for v in J(first)}
B = {v["id"]: v for v in J(later)}
AS_OF = dt.date.fromisoformat(a.as_of or numbers.get("as_of") or dt.date.fromtimestamp(t0).isoformat())
M = dt.date.fromisoformat(a.monetized)
tz = J(a.titles) if a.titles else {}
title = lambda i: tz.get(i) or A[i]["title"]
pub = lambda i: dt.date.fromisoformat(A[i]["date"])
age = lambda i: (AS_OF - pub(i)).days
rate = {i: max(B.get(i, A[i])["views"] - A[i]["views"], 0) * 24 / HRS for i in A}

ranked = sorted(A, key=lambda i: -A[i]["views"])
if a.viral:
    viral = None if a.viral == "none" else a.viral
else:
    viral = ranked[0] if len(ranked) > 1 and A[ranked[0]]["views"] >= 3 * A[ranked[1]]["views"] else None
halo = pub(viral) if viral and pub(viral) > M else None

# 1) views after monetization
days_since = max((AS_OF - M).days, 0)
rows = []
for i in sorted(A, key=pub):
    v = A[i]["views"]
    if pub(i) >= M:
        after, how = v, "全部计入"
    else:
        if halo:
            eff = (AS_OF - halo).days + a.pre_factor * (halo - M).days
        else:
            eff = days_since
        after, how = min(rate[i] * eff, a.cap * v), "开通后新增（估算）"
    rows.append({"id": i, "date": A[i]["date"], "title_zh": title(i), "views": v, "after": round(after), "how": how,
                 "usd": after * RPM / 1000, "cny": after * RPM / 1000 * FX, "daily": round(rate[i])})
post = [r for r in rows if r["how"] == "全部计入"]
pre = [r for r in rows if r["how"] != "全部计入"]
v_post, v_pre = sum(r["after"] for r in post), sum(r["after"] for r in pre)
usd = (v_post + v_pre) * RPM / 1000
months = max(days_since / 30.44, 0.01)

# 2) next 12 months
def avg_factor(half_life, days=365):
    k = math.log(2) / half_life
    return (1 - math.exp(-k * days)) / (k * days)
fast_ids = {i for i in A if age(i) < 30} | ({viral} if viral else set())
fast = sum(rate[i] for i in fast_ids)
slow = sum(rate.values()) - fast
cat_fast = fast * 365 * avg_factor(a.hl_fast)
cat_slow = slow * 365 * avg_factor(a.hl_slow)
base = [r["views"] for r in post if r["id"] != viral] or [r["views"] for r in rows if r["id"] != viral]
per_new = st.mean(base)
per_month = a.per_month if a.per_month is not None else sum(1 for i in A if age(i) < 60) / 2
new_views = per_month * 12 * per_new * a.in_window
nx_views = cat_fast + cat_slow + new_views
nx_usd = nx_views * RPM / 1000

top = max(post, key=lambda r: r["cny"]) if post else None
out = {"rpm": RPM, "fx": FX, "monetized_from": M.isoformat(), "as_of": AS_OF.isoformat(), "months": round(months, 2),
       "snapshot_hours": round(HRS, 1), "viral": viral, "halo_from": halo.isoformat() if halo else None,
       "post_videos": len(post), "post_views": v_post, "pre_videos": len(pre), "pre_after_views": v_pre,
       "views_after": v_post + v_pre, "usd": usd, "cny": usd * FX, "monthly_usd": usd / months, "monthly_cny": usd * FX / months,
       "post_avg_cny": st.mean(r["cny"] for r in post) if post else 0,
       "post_median_cny": st.median(r["cny"] for r in post) if post else 0,
       "post_median_views": st.median(r["views"] for r in post) if post else 0,
       "top_cny": top["cny"] if top else 0, "top_id": top["id"] if top else None,
       "daily_now": sum(rate.values()), "daily_fast": fast, "daily_slow": slow, "fast_videos": len(fast_ids),
       "next": {"window": f"{(AS_OF.replace(day=1) + dt.timedelta(days=32)).replace(day=1):%Y-%m} 起 12 个月",
                "catalog_fast_views": cat_fast, "catalog_slow_views": cat_slow, "per_month": per_month,
                "new_videos": round(per_month * 12), "per_new_views": per_new, "new_views": new_views, "views": nx_views,
                "usd": nx_usd, "cny": nx_usd * FX, "monthly_usd": nx_usd / 12, "monthly_cny": nx_usd * FX / 12},
       "params": {k: getattr(a, k) for k in ("pre_factor", "cap", "hl_fast", "hl_slow", "in_window")},
       "rows": rows}
json.dump(out, open(a.out, "w"), ensure_ascii=False, indent=1)

f = lambda x: f"{x:,.0f}"
cny = lambda x: f"¥{x:,.0f}"
usd_ = lambda x: f"${x:,.0f}"
w1 = lambda x: f"{x / 1e4:.1f} 万"
wan_cny = lambda x: f"¥{x / 1e4:.1f} 万"
NX = out["next"]
part = lambda v: v * RPM / 1000 * FX
print(f"monetized from {M} ({months:.1f} months): {f(v_post + v_pre)} views -> {usd_(usd)} ({cny(usd * FX)}), "
      f"monthly {cny(usd * FX / months)}; next 12 months {f(nx_views)} views -> {cny(nx_usd * FX)}, monthly {cny(nx_usd * FX / 12)}")

if a.md:
    md = [f"# 开通收益后的收益估算 + 明年预估（RPM ${RPM:g}，汇率 {FX:.4f}）", "",
          f"开通收益按 {M} 算。只算 {M} 到 {AS_OF} 的播放，共 {months:.1f} 个月。两次抓数间隔 {HRS:.1f} 小时，用来算每条视频现在每天涨多少。", "",
          "| 部分 | 播放 | 美元 | 人民币 |", "|---|---|---|---|",
          f"| 开通后发布的 {len(post)} 条（全部播放） | {f(v_post)} | {usd_(v_post * RPM / 1000)} | {cny(part(v_post))} |",
          f"| 开通前发布的 {len(pre)} 条（开通后新增，估算） | {f(v_pre)} | {usd_(v_pre * RPM / 1000)} | {cny(part(v_pre))} |",
          f"| **合计** | **{f(v_post + v_pre)}** | **{usd_(usd)}** | **{cny(usd * FX)}** |", "",
          f"- 开通后平均每月：{usd_(usd / months)}（{cny(usd * FX / months)}）",
          f"- 开通后发布的视频平均每条 {cny(out['post_avg_cny'])}，中位数 {cny(out['post_median_cny'])}",
          f"- 带火全频道的爆款：{title(viral) if viral else '无'}" + (f"（{halo} 起按现在的速度，之前按 {a.pre_factor:g} 倍）" if halo else ""), "",
          f"## 明年预估（{NX['window']}）", "",
          f"- 现在每天新增约 {f(out['daily_now'])} 次播放",
          f"- 爆款和 30 天内的新视频（{len(fast_ids)} 条）每天 {f(fast)} 次，每 {a.hl_fast:g} 天减半：{f(cat_fast)} 次",
          f"- 其余老视频每天 {f(slow)} 次，每 {a.hl_slow:g} 天减半：{f(cat_slow)} 次",
          f"- 新视频：每月 {per_month:g} 条 × 每条 {f(per_new)} 次 × {a.in_window:.0%}：{f(new_views)} 次",
          f"- 合计 {f(nx_views)} 次 × ${RPM:g} = {usd_(nx_usd)}（{cny(nx_usd * FX)}），平均每月 {cny(nx_usd * FX / 12)}",
          "- 没有假设再出一条爆款。", "",
          "## 逐条", "", "| 发布 | 视频 | 当前播放 | 每天 | 开通后播放 | 口径 | 人民币 |", "|---|---|---|---|---|---|---|"]
    md += [f"| {r['date']} | {r['title_zh']} | {f(r['views'])} | {f(r['daily'])} | {f(r['after'])} | {r['how']} | {cny(r['cny'])} |" for r in rows]
    open(a.md, "w").write("\n".join(md) + "\n")

if a.slides:
    S = []
    S.append({"type": "table", "eyebrow": "收入情况", "title": f"开通收益后的收益估算约 {wan_cny(usd * FX)}（{usd_(usd)}）",
              "bar": [{"label": "开通后发布的视频", "value": v_post, "color": "accent"},
                      {"label": "开通前的老视频（开通后新增）", "value": v_pre, "color": "accentLight"}],
              "columns": [{"label": "部分", "align": "left", "width": 0.34}, {"label": "开通后播放", "align": "right", "width": 0.18},
                          {"label": "美元", "align": "right", "width": 0.15}, {"label": "人民币", "align": "right", "width": 0.18},
                          {"label": "占比", "align": "right", "width": 0.15}],
              "rows": [[f"开通后发布的 {len(post)} 条", w1(v_post), usd_(v_post * RPM / 1000), cny(part(v_post)), f"{v_post / max(v_post + v_pre, 1):.0%}"],
                       [f"开通前发布的 {len(pre)} 条（估算）", w1(v_pre), usd_(v_pre * RPM / 1000), cny(part(v_pre)), f"{v_pre / max(v_post + v_pre, 1):.0%}"],
                       ["合计", w1(v_post + v_pre), usd_(usd), cny(usd * FX), "100%"]],
              "note": f"只算 {M} 开通收益之后的播放。老视频开通后的新增按每条现在每天的播放推算，是估算。短视频和站外打赏未计入。",
              "portrait": {"columns": [{"label": "部分", "align": "left", "width": 0.4}, {"label": "开通后播放", "align": "right", "width": 0.3},
                                       {"label": "人民币", "align": "right", "width": 0.3}],
                           "rows": [["开通后发布", w1(v_post), cny(part(v_post))], ["老视频新增", w1(v_pre), cny(part(v_pre))],
                                    ["合计", w1(v_post + v_pre), cny(usd * FX)]], "bold_col": 2}})
    S[-1]["video"] = S[-1]["portrait"]
    S.append({"type": "monthly", "eyebrow": "收入情况", "title": f"开通后平均每月约 {wan_cny(usd * FX / months)}", "bg": "alt",
              "total": {"label": "开通后 · 平均每月", "value": cny(usd * FX / months), "sub": f"{usd_(usd / months)} / 月",
                        "caption": f"{cny(usd * FX)} ÷ {months:.1f} 个月"},
              "items": [{"label": "开通后发布的视频", "value": f"{cny(part(v_post) / months)} / 月", "share": v_post / max(v_post + v_pre, 1), "color": "accent"},
                        {"label": "开通前的老视频", "value": f"{cny(part(v_pre) / months)} / 月", "share": v_pre / max(v_post + v_pre, 1), "color": "accentLight"}],
              "note": f"按 {M}（开通收益）到 {AS_OF} 共 {months:.1f} 个月平摊。"})
    if post:
        lo = min(post, key=lambda r: r["cny"])
        S.append({"type": "stats4", "eyebrow": "收入情况", "title": f"开通后发的视频，平均每条约 {cny(out['post_avg_cny'])}",
                  "tiles": [{"label": "平均", "value": cny(out["post_avg_cny"]), "sub": f"{len(post)} 条", "dark": True},
                            {"label": "中位数", "value": cny(out["post_median_cny"]), "sub": f"{w1(out['post_median_views'])}播放"},
                            {"label": "最高", "value": cny(top["cny"]), "sub": f"{w1(top['views'])}播放"},
                            {"label": "最低", "value": cny(lo["cny"]), "sub": f"{w1(lo['views'])}播放"}],
                  "bullets": [f"只算开通后发布的 {len(post)} 条；一半视频不到 {cny(out['post_median_cny'])}。"],
                  "video": {"bullets": [f"一半视频不到 {cny(out['post_median_cny'])}"]}})
    top10 = sorted(rows, key=lambda r: -r["after"])[:10]
    S.append({"type": "table", "eyebrow": "收入情况", "title": "开通后收益最高的 10 条",
              "columns": [{"label": "#", "align": "left", "width": 0.045}, {"label": "视频标题（中译）", "align": "left", "width": 0.465},
                          {"label": "发布", "align": "left", "width": 0.115}, {"label": "开通后播放", "align": "right", "width": 0.13},
                          {"label": "收益（美元）", "align": "right", "width": 0.11}, {"label": "收益（人民币）", "align": "right", "width": 0.135}],
              "rows": [[str(k), r["title_zh"] + ("（估算）" if r["how"] != "全部计入" else ""), r["date"], f"{r['after']:,}", usd_(r["usd"]), cny(r["cny"])]
                       for k, r in enumerate(top10, 1)],
              "bold_col": 5, "font_size": 12, "row_h": 0.38,
              "note": f"按 RPM ${RPM:g}、汇率 {FX:.4f}。标“估算”的是开通前发布的视频，只算开通后新增的播放。",
              "portrait": {"columns": [{"label": "视频", "align": "left", "width": 0.6}, {"label": "开通后播放", "align": "right", "width": 0.2},
                                       {"label": "收益", "align": "right", "width": 0.2}],
                           "rows": [[r["title_zh"], w1(r["after"]), cny(r["cny"])] for r in top10], "bold_col": 2},
              "video": {"columns": [{"label": "视频", "align": "left", "width": 0.6}, {"label": "收益", "align": "right", "width": 0.4}],
                        "rows": [["（短名）", cny(r["cny"])] for r in top10[:5]], "bold_col": 1}})
    S.append({"type": "stats4", "eyebrow": "收入情况", "title": f"明年预估：约 {wan_cny(NX['cny'])}，每月约 {wan_cny(NX['monthly_cny'])}",
              "tiles": [{"label": "明年平均每月", "value": wan_cny(NX["monthly_cny"]), "sub": f"{usd_(NX['monthly_usd'])} / 月", "dark": True},
                        {"label": "明年合计", "value": wan_cny(NX["cny"]), "sub": usd_(NX["usd"])},
                        {"label": "明年播放", "value": f"{nx_views / 1e4:.0f} 万", "sub": f"RPM ${RPM:g}"},
                        {"label": "现在每天播放", "value": w1(out["daily_now"]), "sub": "两次抓数实测"}],
              "bullets": ["（结论：比开通后月均高还是低，为什么）", "没有假设再出一条爆款"],
              "video": {"bullets": ["（关键词）", "（关键词）"]},
              "note": f"明年指 {NX['window']}。按现在的播放和更新节奏推算，是预估，不构成收益承诺。"})
    S.append({"type": "table", "eyebrow": "收入情况", "title": "明年的播放从哪来", "bg": "alt",
              "columns": [{"label": "来源", "align": "left", "width": 0.3}, {"label": "怎么算", "align": "left", "width": 0.38},
                          {"label": "明年播放", "align": "right", "width": 0.14}, {"label": "人民币", "align": "right", "width": 0.18}],
              "rows": [[f"爆款 + 新视频（{len(fast_ids)} 条）", f"每天 {w1(fast)}，每 {a.hl_fast:g} 天减半", w1(cat_fast), cny(part(cat_fast))],
                       [f"其余 {len(A) - len(fast_ids)} 条老视频", f"每天 {w1(slow)}，每 {a.hl_slow:g} 天减半", w1(cat_slow), cny(part(cat_slow))],
                       [f"新视频 {NX['new_videos']} 条", f"每月 {per_month:g} 条 × 每条约 {w1(per_new)}", w1(new_views), cny(part(new_views))],
                       ["合计", "", w1(nx_views), cny(NX["cny"])]],
              "total_row": True, "font_size": 14, "row_h": 0.56,
              "note": f"每条约 {w1(per_new)} = 开通后发布的视频去掉爆款的平均播放；年底发的视频只有一部分播放落在明年，按 {a.in_window:.0%} 算。",
              "portrait": {"columns": [{"label": "来源", "align": "left", "width": 0.45}, {"label": "明年播放", "align": "right", "width": 0.25},
                                       {"label": "人民币", "align": "right", "width": 0.3}],
                           "rows": [["爆款 + 新视频", w1(cat_fast), cny(part(cat_fast))], ["其余老视频", w1(cat_slow), cny(part(cat_slow))],
                                    [f"新视频 {NX['new_videos']} 条", w1(new_views), cny(part(new_views))], ["合计", w1(nx_views), cny(NX["cny"])]], "bold_col": 2},
              "video": {"columns": [{"label": "来源", "align": "left", "width": 0.55}, {"label": "人民币", "align": "right", "width": 0.45}],
                        "rows": [["爆款 + 新视频", cny(part(cat_fast))], ["其余老视频", cny(part(cat_slow))],
                                 [f"新视频 {NX['new_videos']} 条", cny(part(new_views))], ["合计", cny(NX["cny"])]], "bold_col": 1}})
    json.dump(S, open(a.slides, "w"), ensure_ascii=False, indent=1)
    print(f"wrote {len(S)} slides to {a.slides} — fill the （…） placeholders and the video short names, then replace the 收入情况 pages")
