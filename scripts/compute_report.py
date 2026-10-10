#!/usr/bin/env python3
"""Turn fetched channel data + a small config into numbers, CSVs, a Markdown
summary and a draft deck.json for build_deck.js.

    python3 compute_report.py WORK/config.json

See references/config.md for every config key. Paths in the config are
relative to the config file. Output goes to config["out"] (default: the
config's folder): numbers.json, <channel>_long.csv, report.md, deck.json.
"""
import csv
import datetime as dt
import json
import os
import statistics
import sys
import urllib.request
from collections import Counter

SHORTS_RPM_DEFAULT = 0.10


# ---------------------------------------------------------------- helpers

def wan(n, d=None):
    """Chinese 万 units: 2,305 万 / 29.2 万 / 3.09 万."""
    if d is None:
        d = 0 if n >= 1e7 else 1
    return f"{n / 1e4:,.{d}f} 万"


def views_text(n):
    """Views in 万 when large, plain digits when under 10,000 (0.1 万 reads badly)."""
    return wan(n) if n >= 1e4 else f"{round(n):,} 次"


def fmt(n):
    return f"{round(n):,}"


def usd(n):
    return "$" + fmt(n)


def months_between(a, b):
    return max((b - a).days, 1) / 30.4375


def fx_rate(cfg):
    fx = cfg.get("fx", "auto")
    if isinstance(fx, (int, float)):
        return float(fx), "config"
    try:
        req = urllib.request.Request("https://open.er-api.com/v6/latest/USD", headers={"User-Agent": "Mozilla/5.0"})
        d = json.load(urllib.request.urlopen(req, timeout=20))
        return float(d["rates"]["CNY"]), "open.er-api.com " + d.get("time_last_update_utc", "")[:16]
    except Exception as e:  # noqa: BLE001
        sys.exit(f"Could not fetch the USD/CNY rate ({e!r}); set \"fx\": <number> in the config.")


def load_json(base, p, default=None):
    if not p:
        return default
    with open(os.path.join(base, p)) as f:
        return json.load(f)


def d(s):
    return dt.date.fromisoformat(s)


def short_title(t, units=30):
    """Drop emoji/flags and cap the visual width (CJK = 1, other = 0.55) so one table row stays one line."""
    t = "".join(ch for ch in t if ord(ch) < 0x1F000 and not 0x2600 <= ord(ch) < 0x27C0 and ch not in "\ufe0f")
    t = " ".join(t.split())
    w, out = 0.0, []
    for ch in t:
        w += 1 if "\u3000" <= ch <= "\u9fff" or "\uff00" <= ch <= "\uffef" else 0.55
        if w > units:
            return "".join(out).rstrip(" |,-—") + "…"
        out.append(ch)
    return t


# ---------------------------------------------------------------- main

def main():
    if len(sys.argv) != 2:
        sys.exit(__doc__)
    cfg_path = os.path.abspath(os.path.expanduser(sys.argv[1]))
    base = os.path.dirname(cfg_path)
    cfg = json.load(open(cfg_path))
    out = os.path.join(base, cfg.get("out", "."))
    os.makedirs(out, exist_ok=True)
    as_of = d(cfg.get("as_of") or dt.date.today().isoformat())
    rate, rate_src = fx_rate(cfg)
    cny = lambda x: "¥" + fmt(x * rate)
    cnyw = lambda x, k=1: "¥" + wan(x * rate, k) if x * rate >= 1e4 else "¥" + fmt(x * rate)

    titles_zh = load_json(base, cfg.get("titles_zh"), {}) or {}
    topics_raw = load_json(base, cfg.get("topics"), None)

    # --- channels
    chans = []
    for i, c in enumerate(cfg["channels"]):
        dd = os.path.join(base, c["data"])
        ch = dict(c)
        ch["about"] = json.load(open(os.path.join(dd, "about.json")))
        ch["long"] = [v for v in json.load(open(os.path.join(dd, "long.json"))) if v.get("date")]
        ch["shorts"] = [v for v in json.load(open(os.path.join(dd, "shorts.json"))) if v.get("date")]
        ch["main"] = i == 0
        ch["label"] = c.get("label") or ("主频道" if i == 0 else f"频道 {i + 1}")
        ch["name"] = c.get("name") or short_title(ch["about"].get("title") or "", 14)
        ch["shorts_rpm"] = c.get("shorts_rpm", SHORTS_RPM_DEFAULT)
        ch["long_views"] = sum(v["views"] for v in ch["long"])
        ch["shorts_views"] = sum(v["views"] for v in ch["shorts"])
        chans.append(ch)
    main = chans[0]

    # --- disclosure back-calculation (main channel)
    disc = cfg.get("disclosure")
    back = None
    if disc:
        snap = disc.get("snapshot") or {}
        lv = snap.get("long_views") or main["long_views"]
        sv = snap.get("shorts_views") if snap.get("shorts_views") is not None else main["shorts_views"]
        shorts_usd = sv / 1000 * main["shorts_rpm"]
        long_usd = disc["amount_usd"] - shorts_usd - disc.get("other_usd", 0)
        back = {"amount_usd": disc["amount_usd"], "shorts_views": sv, "shorts_usd": shorts_usd, "long_usd": long_usd,
                "long_views": lv, "snapshot_date": snap.get("date") or as_of.isoformat(), "rpm": long_usd / lv * 1000}
        if main.get("rpm") in (None, "backcalc"):
            main["rpm"] = round(back["rpm"], 1)
    for ch in chans:
        if not isinstance(ch.get("rpm"), (int, float)):
            sys.exit(f"Channel {ch['label']} has no numeric rpm (set it, or give a disclosure for the main channel).")
        ch["long_usd"] = ch["long_views"] / 1000 * ch["rpm"]
        ch["shorts_usd"] = ch["shorts_views"] / 1000 * ch["shorts_rpm"]
        ch["usd"] = ch["long_usd"] + ch["shorts_usd"]
        ch["first_long"] = min((v["date"] for v in ch["long"]), default=None)
        ch["first_short"] = min((v["date"] for v in ch["shorts"]), default=None)

    # --- tips (e.g. Buy Me a Coffee)
    tips = cfg.get("tips")
    tip = None
    if tips:
        avg = sum(a * p for a, p in tips["tiers"])
        gross = tips["supporters"] * avg
        fee_plat = gross * tips.get("platform_fee", 0.05)
        fee_pay = gross * tips.get("payment_pct", 0.029) + tips.get("payment_fixed", 0.30) * tips["supporters"]
        tip = {"platform": tips.get("platform", "Buy Me a Coffee"), "supporters": tips["supporters"], "avg": avg, "gross": gross,
               "fee_platform": fee_plat, "fee_payment": fee_pay, "net": gross - fee_plat - fee_pay, "tiers": tips["tiers"],
               "platform_fee": tips.get("platform_fee", 0.05), "payment_pct": tips.get("payment_pct", 0.029),
               "payment_fixed": tips.get("payment_fixed", 0.30)}

    total = sum(ch["usd"] for ch in chans) + (tip["net"] if tip else 0)
    start = d(cfg.get("period_start") or main["first_long"])
    months = months_between(start, as_of)

    # --- main channel videos
    vids = sorted(main["long"], key=lambda v: -v["views"])
    rev = lambda v, ch=main: v["views"] / 1000 * ch["rpm"]
    per_video = main["long_usd"] / len(vids)
    median_v = vids[len(vids) // 2]["views"] if len(vids) % 2 else statistics.median(v["views"] for v in vids)
    top10_share = sum(v["views"] for v in vids[:10]) / main["long_views"]
    zh = lambda v: titles_zh.get(v["id"]) or short_title(v["title"])

    # --- topics
    topics = None
    if topics_raw:
        if all(isinstance(x, list) for x in topics_raw.values()):
            id2t = {i: t for t, ids in topics_raw.items() for i in ids}
        else:
            id2t = dict(topics_raw)
        byid = {v["id"]: v for v in vids}
        missing = [i for i in byid if i not in id2t]
        if missing:
            print(f"note: {len(missing)} long videos have no topic -> '其他': {missing[:6]}")
        groups = {}
        for i, v in byid.items():
            groups.setdefault(id2t.get(i, "其他"), []).append(v)
        topics = []
        for t, L in groups.items():
            best = max(L, key=lambda v: v["views"])
            tot = sum(v["views"] for v in L)
            topics.append({"topic": t, "n": len(L), "total": tot, "avg": tot / len(L), "best": zh(best), "best_views": best["views"]})
        topics.sort(key=lambda x: -x["avg"])

    # --- upload frequency
    series = []
    for ch in chans:
        series.append((f"{ch['label']}长视频", Counter(v["date"][:7] for v in ch["long"])))
        if ch["shorts"]:
            series.append((f"{ch['label']} Shorts", Counter(v["date"][:7] for v in ch["shorts"])))
    all_months = sorted(set().union(*[set(c) for _, c in series]))
    freq = {"series": [s for s, _ in series], "months": all_months, "values": [[c.get(m, 0) for _, c in series] for m in all_months]}

    def cadence(ch):
        r = {"long_n": len(ch["long"]), "shorts_n": len(ch["shorts"])}
        if ch["first_long"]:
            r["long_per_month"] = len(ch["long"]) / months_between(d(ch["first_long"]), as_of)
            recent = [v for v in ch["long"] if d(v["date"]) > as_of - dt.timedelta(days=90)]
            r["long_recent_per_month"] = len(recent) / months_between(as_of - dt.timedelta(days=90), as_of)
        if ch["first_short"]:
            r["shorts_per_month"] = len(ch["shorts"]) / months_between(d(ch["first_short"]), as_of)
            first_m = ch["first_short"][:7]
            r["shorts_first_month"] = (first_m, sum(1 for v in ch["shorts"] if v["date"].startswith(first_m)))
        return r
    for ch in chans:
        ch["cadence"] = cadence(ch)
    all_long = sum(len(ch["long"]) for ch in chans)
    all_items = sum(len(ch["long"]) + len(ch["shorts"]) for ch in chans)
    first_any = min(x for ch in chans for x in (ch["first_long"], ch["first_short"]) if x)
    combined = {"long_per_month": all_long / months, "all_per_month": all_items / months_between(d(first_any), as_of)}

    # --- accounts
    accounts = []
    for ch in chans:
        a = ch["about"]
        accounts.append({"platform": f"YouTube {ch['label']}", "name": a.get("title") or a.get("handle"), "value": wan(a["subscribers"], 1 if a["subscribers"] >= 1e5 else 2),
                         "unit": "订阅", "detail": f"{wan(a['views'], 0)}播放\n{len(ch['long']) + len(ch['shorts'])} 条视频（{len(ch['long'])} 长 + {len(ch['shorts'])} Shorts）",
                         "followers": a["subscribers"], "highlight": ch["main"]})
    for a in cfg.get("accounts", []):
        acc = dict(a)
        if "value" not in acc and acc.get("followers") is not None:
            acc["value"] = wan(acc["followers"])
        accounts.append(acc)
    if tip and not any(tip["platform"].lower() in str(a.get("platform", "")).lower() for a in accounts):
        accounts.append({"platform": tip["platform"], "name": cfg.get("tips", {}).get("handle", ""), "value": fmt(tip["supporters"]), "unit": "位支持者", "detail": "站外打赏"})
    fans = sum(a.get("followers") or 0 for a in accounts)

    # ---------------------------------------------------------------- outputs
    numbers = {
        "as_of": as_of.isoformat(), "fx": rate, "fx_source": rate_src, "period_start": start.isoformat(), "months": months,
        "channels": [{k: ch[k] for k in ("label", "rpm", "shorts_rpm", "long_views", "shorts_views", "long_usd", "shorts_usd", "usd", "first_long", "first_short", "cadence")}
                     | {"long_n": len(ch["long"]), "shorts_n": len(ch["shorts"]), "about": ch["about"]} for ch in chans],
        "backcalc": back, "tips": tip, "total_usd": total, "monthly_usd": total / months,
        "main_per_video_usd": per_video, "main_median_views": median_v, "top10_share": top10_share,
        "topics": topics, "frequency": freq, "combined_cadence": combined, "followers_total": fans,
        "top10": [{"rank": i + 1, "id": v["id"], "title": v["title"], "title_zh": zh(v), "date": v["date"], "views": v["views"], "usd": rev(v)} for i, v in enumerate(vids[:10])],
    }
    json.dump(numbers, open(os.path.join(out, "numbers.json"), "w"), ensure_ascii=False, indent=1)

    for ch in chans:
        slug = (ch["about"].get("handle") or ch["label"]).lstrip("@")
        with open(os.path.join(out, f"{slug}_long.csv"), "w", newline="", encoding="utf-8-sig") as f:
            w = csv.writer(f)
            w.writerow(["rank", "video_id", "publish_date", "duration", "views", "title_zh", "title", "topic", f"usd_rpm{ch['rpm']}", f"cny_rpm{ch['rpm']}", "url"])
            id2t = {}
            if ch["main"] and topics_raw:
                id2t = {i: t for t, ids in topics_raw.items() for i in ids} if all(isinstance(x, list) for x in topics_raw.values()) else topics_raw
            for i, v in enumerate(sorted(ch["long"], key=lambda v: -v["views"]), 1):
                r = rev(v, ch)
                w.writerow([i, v["id"], v["date"], v.get("duration"), v["views"], titles_zh.get(v["id"], ""), v["title"], id2t.get(v["id"], ""),
                            round(r), round(r * rate), "https://www.youtube.com/watch?v=" + v["id"]])

    # --- report.md
    L = [f"# {cfg.get('title', main['about'].get('title'))}（数据截至 {as_of}）", "",
         f"汇率 1 USD = {rate:.4f} CNY（{rate_src}）。月均按 {start} 到 {as_of} 共 {months:.1f} 个月计算。", "",
         "| 收入来源 | 估算方法 | 美元 | 人民币 |", "|---|---|---|---|"]
    for ch in chans:
        L.append(f"| {ch['label']}长视频 | {wan(ch['long_views'])}播放 × ${ch['rpm']} | {usd(ch['long_usd'])} | {cny(ch['long_usd'])} |")
        if ch["shorts"]:
            L.append(f"| {ch['label']} Shorts | {wan(ch['shorts_views'])}播放 × ${ch['shorts_rpm']} | {usd(ch['shorts_usd'])} | {cny(ch['shorts_usd'])} |")
    if tip:
        L.append(f"| {tip['platform']}（到手） | {tip['supporters']:,} 人 × ${tip['avg']:.2f} − 手续费 | {usd(tip['net'])} | {cny(tip['net'])} |")
    L += [f"| **合计** | | **{usd(total)}** | **{cny(total)}** |", "",
          f"- 平均每月：{usd(total / months)}（{cny(total / months)}）",
          f"- {main['label']}平均每条长视频：{usd(per_video)}（{cny(per_video)}），中位数那条约 {cny(median_v / 1000 * main['rpm'])}",
          f"- 播放前 10 条占{main['label']}长视频播放的 {top10_share:.1%}"]
    if back:
        L.append(f"- 反推 RPM：({usd(back['amount_usd'])} − Shorts {usd(back['shorts_usd'])}) ÷ {wan(back['long_views'])}长视频播放 = ${back['rpm']:.2f}")
    L += ["", "## 播放最高的 10 条", "", "| # | 标题 | 发布 | 播放 | 美元 | 人民币 |", "|---|---|---|---|---|---|"]
    for t in numbers["top10"]:
        L.append(f"| {t['rank']} | {t['title_zh']} | {t['date']} | {t['views']:,} | {usd(t['usd'])} | {cny(t['usd'])} |")
    if topics:
        L += ["", "## 题材", "", "| 题材 | 条数 | 平均播放 | 代表作 |", "|---|---|---|---|"]
        L += [f"| {t['topic']} | {t['n']} | {wan(t['avg'])} | {t['best']} |" for t in topics]
    L += ["", "## 每月发布条数", "", "| 月份 | " + " | ".join(freq["series"]) + " |", "|---" * (len(freq["series"]) + 1) + "|"]
    L += [f"| {m} | " + " | ".join(str(x) for x in row) + " |" for m, row in zip(freq["months"], freq["values"])]
    open(os.path.join(out, "report.md"), "w").write("\n".join(L) + "\n")

    # ---------------------------------------------------------------- deck.json
    title = cfg.get("title") or f"{main['about'].get('title')} 频道分析"
    handles = " · ".join(ch["about"].get("handle") or "" for ch in chans)
    S = []
    S.append({"type": "cover", "section": "概览", "eyebrow": "YouTube 频道拆解", "title": title,
              "subtitle": "账号矩阵、收入估算、爆款视频、题材和更新频率" if len(accounts) > 1 else "收入估算、爆款视频、题材和更新频率",
              "kpi": {"label": "收入估算 · 平均每月", "value": cnyw(total / months), "sub": f"累计约 {cnyw(total, 0)}"},
              "meta": f"{handles} · 数据截至 {as_of}"})
    if len(chans) > 1 or tip:
        f0 = {"title": f"钱主要来自{main['label']}", "text": f"{main['label']}占全部收入的 {main['usd'] / total:.0%}，长视频是收入大头。"}
    else:
        f0 = {"title": "长视频是收入大头", "text": f"长视频 {len(main['long'])} 条贡献了 {main['long_usd'] / total:.0%} 的收入；"
              + (f"{len(main['shorts'])} 条 Shorts 有 {wan(main['shorts_views'])}播放，只值 {usd(main['shorts_usd'])}。" if main["shorts"] else "频道没有 Shorts。")}
    findings = [f0,
                {"title": "收入集中在少数爆款", "text": f"播放前 10 条占{main['label']}长视频播放的 {top10_share:.0%}；一半视频的收入不到 {cnyw(median_v / 1000 * main['rpm'])}。"}]
    if topics:
        bt = topics[0]
        findings.append({"title": f"最受欢迎：{bt['topic']}", "text": f"平均每条 {wan(bt['avg'])}播放，代表作「{bt['best']}」。"})
    S.append({"type": "kpis", "eyebrow": "一页看懂", "title": f"累计约 {cnyw(total, 0)}，平均每月约 {cnyw(total / months)}",
              "tiles": [{"value": wan(fans) if fans else wan(main['about']['subscribers']), "label": "全平台粉丝" if len(accounts) > 1 else "订阅", "desc": "所有账号粉丝相加" if len(accounts) > 1 else main["about"].get("title"), "dark": True},
                        {"value": f"${main['rpm']}", "label": f"{main['label']}长视频 RPM", "desc": "用公开收入反推" if back else "估算值"},
                        {"value": cnyw(per_video), "label": "每条长视频", "desc": f"{len(vids)} 条长视频平均"},
                        {"value": f"{combined['long_per_month'] / 4.345:.1f} 条", "label": "每周长视频", "desc": "所有频道合计" if len(chans) > 1 else "平均更新频率"}],
              "findings": findings})
    if len(accounts) > 1:
        S.append({"type": "accounts", "eyebrow": "账号矩阵", "title": f"{len(accounts)} 个账号，全平台约 {wan(fans)}粉丝", "bg": "alt",
                  "accounts": [{k: a.get(k, "") for k in ("platform", "name", "value", "unit", "detail", "highlight")} for a in accounts[:5]],
                  "note": f"数据为 {as_of} 各平台公开页面显示的数值。"})
    if back:
        S.append({"type": "disclosure", "section": "收入估算", "eyebrow": "公开数据", "title": f"截至 {disc.get('date', '')}，{main['label']}累计收入 {usd(back['amount_usd'])}",
                  "amount": usd(back["amount_usd"]), "amount_sub": f"约 {cnyw(back['amount_usd'])}元", "caption": f"截至 {disc.get('date', '')} · 公开披露",
                  "parts_title": "包含以下几部分", "parts": disc.get("includes", ["YouTube 长视频广告分成", "YouTube Shorts 分成", "YouTube 频道会员", "YouTube 打赏（Super Thanks）"]),
                  "parts_note": disc.get("note", "")})
        S.append({"type": "backcalc", "eyebrow": "反推 RPM", "title": f"{main['label']}长视频的平均 RPM 约 ${back['rpm']:.1f}", "bg": "alt",
                  "steps": [{"label": "累计收入", "value": usd(back["amount_usd"]), "desc": f"截至 {disc.get('date', '')} 披露"},
                            {"label": "减去 Shorts 收入", "value": "−" + usd(back["shorts_usd"]), "desc": f"{wan(back['shorts_views'])}播放 × ${main['shorts_rpm']}/千次"},
                            {"label": "长视频收入", "value": usd(back["long_usd"]), "desc": "会员和打赏占比不高，不另扣"},
                            {"label": "除以长视频播放", "value": "÷ " + wan(back["long_views"]), "desc": f"{back['snapshot_date']} 的播放快照"}],
                  "result": {"label": "≈ RPM", "value": f"${back['rpm']:.1f}", "sub": "每千次长视频播放"},
                  "note": f"{usd(back['long_usd'])} ÷ {fmt(back['long_views'])} × 1,000 = ${back['rpm']:.2f}。会员和 Super Thanks 没有单独扣除，所以这是把它们也摊进去的综合值。"})
    if cfg.get("explain_rpm", True):
        S.append({"type": "explainer", "section": None if back else "收入估算", "eyebrow": "什么是 RPM", "title": "RPM：每 1,000 次播放带来的收益（美元）",
                  "example": f"100 万播放 ÷ 1,000 × ${main['rpm']} = {usd(1000 * main['rpm'])}（约 {cnyw(1000 * main['rpm'])}）",
                  "left": {"title": "RPM 不是固定的", "bullets": ["每个视频的 RPM 都不一样，同一个视频不同月份也会变。", "只有频道主在 YouTube 后台（YouTube Studio）能看到真实数字。", "外人只能根据公开信息估算，这份分析的 RPM 都是估算值。"]},
                  "right": {"title": "RPM 由多种因素共同决定", "chips": ["观众来源（国家）", "题材", "视频时长", "语言", "季节"], "text": "英语内容、欧美观众多、视频 8 分钟以上能插中间广告，RPM 都会更高。"}})
    for ch in chans[1:]:
        top3 = sorted(ch["long"], key=lambda v: -v["views"])[:3]
        S.append({"type": "channel_card", "eyebrow": f"{ch['label']}收入", "title": f"{ch['label']} {ch['name']}：约 {cnyw(ch['usd'])}", "bg": "alt",
                  "tiles": [{"value": f"{len(ch['long'])} 条", "label": "长视频"}, {"value": wan(ch["long_views"], 0), "label": "长视频播放"},
                            {"value": f"${ch['rpm']}", "label": "RPM" + (f"（{ch['rpm_note']}）" if ch.get("rpm_note") else ""), "accent": True},
                            {"value": cny(ch["long_usd"] / max(len(ch["long"]), 1)), "label": "平均每条"}],
                  "total": {"label": "合计", "value": f"{usd(ch['usd'])} ≈ {cnyw(ch['usd'])}"},
                  "list_title": "播放最高的 3 条",
                  "list": [{"title": titles_zh.get(v["id"]) or short_title(v["title"], 22), "value": f"{wan(v['views'])}播放\n{cny(rev(v, ch))}"} for v in top3],
                  "side_note": f"{len(ch['shorts'])} 条 Shorts 共 {wan(ch['shorts_views'])}播放，按每千次 ${ch['shorts_rpm']} 计入。" if ch["shorts"] else ""})
    if tip:
        tiers_rows = [[f"${a:g}", f"{p:.0%}", f"${a * p:.2f}"] for a, p in tip["tiers"]] + [["加权平均", "100%", f"${tip['avg']:.2f}"]]
        S.append({"type": "tips", "eyebrow": "站外打赏", "title": f"{tip['platform']} 打赏：到手约 {cnyw(tip['net'])}",
                  "table_title": f"{tip['supporters']:,} 位支持者，按金额分档", "columns": [{"label": "打赏金额", "align": "left"}, {"label": "人数占比", "align": "right"}, {"label": "对人均的贡献", "align": "right"}],
                  "rows": tiers_rows, "steps_title": "从毛收入到到手",
                  "steps": [{"label": "毛收入", "desc": f"{tip['supporters']:,} 位 × ${tip['avg']:.2f}", "value": usd(tip["gross"])},
                            {"label": "平台费", "desc": f"{tip['platform_fee']:.0%}", "value": "−" + usd(tip["fee_platform"])},
                            {"label": "支付手续费", "desc": f"{tip['payment_pct']:.1%} + 每笔 ${tip['payment_fixed']:.2f}", "value": "−" + usd(tip["fee_payment"])},
                            {"label": "到手", "desc": f"约 {cnyw(tip['net'])}元", "value": usd(tip["net"]), "dark": True}],
                  "note": "支持者人数取自公开页面。按每人打赏一次估算，打赏多次的人会让实际金额更高；分档比例是假设值。"})
    parts = []
    palette = ["accent", "accentLight", "blue", "lightBlue", "muted"]
    for ch in chans:
        if ch["main"] and ch["shorts"]:
            parts.append([f"{ch['label']}长视频", f"{wan(ch['long_views'])}播放 × ${ch['rpm']}", ch["long_usd"]])
            parts.append([f"{ch['label']} Shorts", f"{wan(ch['shorts_views'])}播放 × ${ch['shorts_rpm']}", ch["shorts_usd"]])
        else:
            parts.append([ch["label"], f"{wan(ch['long_views'])}播放 × ${ch['rpm']}", ch["usd"]])
    if tip:
        parts.append([tip["platform"], "扣手续费后到手", tip["net"]])
    S.append({"type": "table", "eyebrow": "总收入估算", "title": f"全部收入合计约 {cnyw(total, 0)}（{usd(total)}）",
              "bar": [{"label": p[0], "value": p[2], "color": palette[i % len(palette)]} for i, p in enumerate(parts)],
              "columns": [{"label": "收入来源", "align": "left", "width": 0.22}, {"label": "估算方法", "align": "left", "width": 0.30}, {"label": "美元", "align": "right", "width": 0.15},
                          {"label": "人民币", "align": "right", "width": 0.18}, {"label": "占比", "align": "right", "width": 0.15}],
              "rows": [[p[0], p[1], usd(p[2]), cny(p[2]), f"{p[2] / total:.1%}"] for p in parts] + [["合计", "", usd(total), cny(total), "100%"]],
              "total_row": True, "font_size": 15, "row_h": 0.48,
              "note": "会员和 Super Thanks 已包含在长视频的 RPM 估算里；没有公开收入数据的平台不计入。"})
    items = [{"label": c["label"] if not c["main"] else c["label"], "value": c["usd"]} for c in chans] + ([{"label": tip["platform"], "value": tip["net"]}] if tip else [])
    items.sort(key=lambda x: -x["value"])
    S.append({"type": "monthly", "eyebrow": "平均每月", "title": f"平均每月约 {cnyw(total / months)}", "bg": "alt",
              "total": {"label": "全部收入 · 平均每月", "value": cny(total / months), "sub": f"{usd(total / months)} / 月", "caption": f"累计 {cny(total)} ÷ {months:.1f} 个月"},
              "items": [{"label": x["label"], "value": cny(x["value"] / months) + " / 月", "share": x["value"] / total, "color": palette[i % len(palette)]} for i, x in enumerate(items)][:4],
              "note": f"按 {start}（{main['label']}第一条长视频）到 {as_of} 共 {months:.1f} 个月平摊。最近发的视频还在涨播放，以后算出来的月均会更高。"})
    below = sum(1 for v in vids if rev(v) < per_video)
    bul = [f"平均值被几条爆款拉高：{len(vids)} 条里有 {below} 条低于平均，一半视频的收入不到 {cnyw(median_v / 1000 * main['rpm'])}。"]
    if len(chans) > 1:
        sub = chans[1]
        bul.append(f"{sub['label']}平均每条 {cny(sub['long_usd'] / max(len(sub['long']), 1))}，约为{main['label']}的 1/{max(round(per_video / max(sub['long_usd'] / max(len(sub['long']), 1), 1)), 1)}。")
    S.append({"type": "stats4", "eyebrow": "平均每条", "title": f"{main['label']}平均每条长视频约 {cnyw(per_video)}",
              "tiles": [{"label": "平均", "value": cny(per_video), "sub": usd(per_video), "dark": True},
                        {"label": "中位数", "value": cny(median_v / 1000 * main["rpm"]), "sub": f"{views_text(median_v)}播放"},
                        {"label": "最高", "value": cny(rev(vids[0])), "sub": f"{views_text(vids[0]['views'])}播放"},
                        {"label": "最低", "value": cny(rev(vids[-1])), "sub": f"{views_text(vids[-1]['views'])}播放"}],
              "bullets": bul})
    S.append({"type": "table", "section": "内容分析", "eyebrow": "爆款视频", "title": "播放最高的 10 条视频，各赚了多少",
              "columns": [{"label": "#", "align": "left", "width": 0.045}, {"label": "视频标题（中译）" if titles_zh else "视频标题", "align": "left", "width": 0.465},
                          {"label": "发布", "align": "left", "width": 0.115}, {"label": "播放", "align": "right", "width": 0.115},
                          {"label": "收入（美元）", "align": "right", "width": 0.12}, {"label": "收入（人民币）", "align": "right", "width": 0.14}],
              "rows": [[str(t["rank"]), t["title_zh"], t["date"], fmt(t["views"]), usd(t["usd"]), cny(t["usd"])] for t in numbers["top10"]],
              "bold_col": 5, "font_size": 12, "row_h": 0.38,
              "note": f"按 RPM ${main['rpm']}、汇率 {rate:.4f} 计算。前 10 条合计占{main['label']}长视频播放的 {top10_share:.0%}。"})
    if topics:
        by_n = sorted(topics, key=lambda t: (-t["n"], -t["avg"]))
        top_avg = topics[:5]
        right = [{"label": f"{i + 1}. {t['topic']}", "value": t["n"], "text": f"{t['n']} 条"} for i, t in enumerate(by_n[:5])]
        S.append({"type": "topic_bars", "eyebrow": "题材分析", "title": "最受欢迎的题材 vs 拍得最多的题材", "bg": "alt",
                  "left": {"title": "最受欢迎前 5（按平均每条播放）", "items": [{"label": f"{i + 1}. {t['topic']}", "value": t["avg"], "text": f"{wan(t['avg'])} · {t['n']} 条", "highlight": i < 2} for i, t in enumerate(top_avg)]},
                  "right": {"title": "拍得最多前 5（按条数）", "items": right},
                  "insight": f"「{by_n[0]['topic']}」拍得最多（{by_n[0]['n']} 条）；「{topics[0]['topic']}」平均每条播放最高（{wan(topics[0]['avg'])}）；「{topics[-1]['topic']}」平均播放最低。"})
        S.append({"type": "table", "eyebrow": "题材分析", "title": f"{len(topics)} 个题材的分类明细",
                  "columns": [{"label": "题材", "align": "left", "width": 0.17}, {"label": "条数", "align": "right", "width": 0.07}, {"label": "平均播放", "align": "right", "width": 0.11},
                              {"label": "总播放", "align": "right", "width": 0.11}, {"label": "代表作（播放最高的一条）", "align": "left", "width": 0.54}],
                  "rows": [[t["topic"], str(t["n"]), wan(t["avg"]), wan(t["total"], 0), t["best"]] for t in topics],
                  "font_size": 12, "row_h": 0.4, "note": "按平均播放从高到低排列。题材按视频标题人工归类，每条视频只归入一类。"})
    colors = ["accent", "accentLight", "blue", "lightBlue", "muted", "gray"]
    S.append({"type": "stacked_columns", "eyebrow": "更新频率", "title": f"{'各频道' if len(chans) > 1 else ''}每个月发多少条", "bg": "alt",
              "series": [{"label": s, "color": colors[i % len(colors)]} for i, s in enumerate(freq["series"])],
              "categories": [m.replace("-", ".") for m in freq["months"]], "values": freq["values"],
              "note": f"柱子上方是当月合计条数，柱子里是各类条数（只标 2 条以上的）。{as_of.strftime('%Y-%m')} 只统计到 {as_of.day} 日。"})
    cols = []
    if len(chans) == 1:
        c = main["cadence"]
        lb = [f"共 {c['long_n']} 条，每月 {c['long_per_month']:.1f} 条（约每周 {c['long_per_month'] / 4.345:.1f} 条）",
              f"最近 90 天：每月 {c['long_recent_per_month']:.1f} 条", f"第一条：{main['first_long']}"]
        cols.append({"title": "长视频", "bullets": lb})
        if main["shorts"]:
            fm, fn = c["shorts_first_month"]
            cols.append({"title": "Shorts", "bullets": [f"共 {c['shorts_n']} 条，每月 {c['shorts_per_month']:.1f} 条", f"第一条：{main['first_short']}（当月 {fn} 条）"]})
        busiest = max(zip(freq["months"], [r[0] for r in freq["values"]]), key=lambda x: x[1])
        cols.append({"title": "节奏特点", "dark": True, "bullets": [f"长视频最多的月份：{busiest[0]}（{busiest[1]} 条）",
                     "最近 90 天" + ("提速了" if c["long_recent_per_month"] > c["long_per_month"] * 1.1 else "放慢了" if c["long_recent_per_month"] < c["long_per_month"] * 0.9 else "和平均差不多")]})
    for ch in (chans[:2] if len(chans) > 1 else []):
        c = ch["cadence"]
        b = []
        if "long_per_month" in c:
            b.append(f"长视频 {c['long_n']} 条，每月 {c['long_per_month']:.1f} 条（约每周 {c['long_per_month'] / 4.345:.1f} 条）")
            b.append(f"最近 90 天：每月 {c['long_recent_per_month']:.1f} 条")
        if "shorts_per_month" in c:
            fm, fn = c["shorts_first_month"]
            b.append(f"Shorts {c['shorts_n']} 条，每月 {c['shorts_per_month']:.1f} 条（{fm} 起步月 {fn} 条）")
        cols.append({"title": f"{ch['label']} {ch['name']}", "bullets": b})
    if len(chans) > 1:
        cols.append({"title": "所有频道合计", "dark": True, "bullets": [f"长视频 {all_long} 条，平均每月 {combined['long_per_month']:.1f} 条（约每周 {combined['long_per_month'] / 4.345:.1f} 条）",
                                                                   f"加上 Shorts 共 {all_items} 条，平均每月约 {combined['all_per_month']:.0f} 条"]})
    S.append({"type": "three_cols", "eyebrow": "更新频率", "title": "更新节奏：从起步到现在", "cols": cols})
    for s in S:
        if s.get("section") is None:
            s.pop("section", None)
    deck = {"meta": {"title": title, "footer": f"{title} · 数据截至 {as_of}"}, "slides": S}
    json.dump(deck, open(os.path.join(out, "deck.json"), "w"), ensure_ascii=False, indent=1)
    print(f"total {usd(total)} ({cny(total)}), monthly {cny(total / months)}, per video {cny(per_video)}; {len(S)} slides drafted")
    print(f"wrote {out}/numbers.json, report.md, deck.json and *_long.csv")


if __name__ == "__main__":
    main()
