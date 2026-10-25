#!/usr/bin/env python3
"""Narration analysis for voice-over driven channels (旁白分析).

Reads YouTube auto captions (en-orig, word-level timing) for every long video and reports, per video
and overall: how much of the runtime is narrated, words per minute, filler words, past-tense recall,
other speakers, and how often each part of the usual script template shows up. With --comments it also
scans comments for reactions to the voice (praise, "is this AI?", "do you write it in Chinese first?")
and the uploader's own replies about accent, voice or script.

  python3 narration_stats.py <channel_dir> --subs <dir> [--comments <dir>] [--titles titles_zh.json]
         [--name Kiki] [--out narration.json] [--slides narration_slides.json] [--proxy socks5://...]

Missing captions are downloaded with yt-dlp into --subs. Numbers are drafts: the reading of translated
phrases, the pipeline (script -> translation -> read aloud) and voice-over vs. live sound still need a
person to check frames and listen (see references/narration.md).
"""
import argparse, glob, json, os, re, statistics, subprocess, sys

FILLERS = r"\b(uh|um|erm|uhm|hmm)\b"
PAST = r"\bI (was|went|decided|ended up|realized|realised|found|got|walked|started|thought|noticed|ordered|paid|chose|came|felt|sat|took|kept|saw|met|tried)\b"
PRESENT = r"\b(I'm|I am) (going|heading|on my way|getting|here|at|done|ready|finally|now)\b"
MONEY = r"\b\d[\d,.]*\s?(RMB|yuan|kuai|R&amp;B|dollars?|USD|euros?|EUR|pounds?|GBP|rupees?|won|yen|baht|pesos?)\b|[$€£¥]\s?\d"
USD = r"\b(US dollars?|USD|dollars?)\b|\$\s?\d"
ASK = r"let me know|I'm curious|I'd love to (hear|know)|what about you|how about you|in the comments|where you live\?|your country|do you ever"
CLOCK = r"\b\d{1,2}:\d\d\b|\b\d{1,2} ?(a\.m\.|p\.m\.|am|pm)\b"
CLOSING = r"see you|good ?night|bye|thanks? (you )?for watching|thanks for spending"
# literal translations and learner slips worth a manual look; extend as new channels turn them up
CALQUES = [
    (r"transparent person", "透明人（英文多说 invisible）"),
    (r"fresh graduate", "应届生（母语者多说 recent graduate）"),
    (r"\b(\d[\d,]*) ?(RMB|yuan|dollars?) is still \1", "X 块也是钱"),
    (r"make my world (a little )?bigger", "让我的世界大一点"),
    (r"eat(ing)? bitterness", "吃苦"),
    (r"add oil", "加油"),
    (r"lying flat", "躺平"),
    (r"open my eyes", "开眼界"),
    (r"people mountain people sea", "人山人海"),
    (r"\beveryone (have|are|were|do)\b", "主谓不一致（everyone + 复数动词）"),
    (r"\b(he|she|it) (don't|have been|are)\b", "主谓不一致"),
]
COMMENT_PATTERNS = {
    "夸声音 / 英语": r"your voice|love (your|the) voice|your english|english is (so |very |really )?good|cute accent|accent is (so )?cute|your narration|love (your|the) narration",
    "怀疑 AI 配音": r"\bAI voice|voice is AI|is (this|it|she|kiki) (real or )?AI\b|is AI\b|using AI|AI[- ]generated|not her (real )?voice|prove .* not AI|text[- ]to[- ]speech|\bTTS\b",
    "替她说是本人": r"(real|natural|own) voice|can't mispronounce|not (an )?AI voice",
    "问写稿 / 翻译": r"(write|wrote) it in \w+ first|translat\w+ (it|to english)|is (that|this) you speaking|using a translator|script",
}
UPLOADER_TOPICS = r"accent|voice|script|translat|english|narrat|\bAI\b|record"


def ts(s):
    h, m, x = s.split(":")
    return int(h) * 3600 + int(m) * 60 + float(x)


def words(path):
    """(time, word) pairs from a YouTube auto-caption vtt; only the cue lines that carry word timing."""
    out = []
    for block in open(path, encoding="utf-8").read().split("\n\n"):
        lines = block.split("\n")
        if len(lines) < 2 or "-->" not in lines[0]:
            continue
        t = ts(lines[0].split(" --> ")[0])
        for line in lines[1:]:
            if "<c>" not in line and not re.search(r"<\d\d:", line):
                continue
            for tok in re.split(r"(<\d\d:\d\d:\d\d\.\d+>)", line):
                m = re.match(r"<(\d\d:\d\d:\d\d\.\d+)>", tok)
                if m:
                    t = ts(m.group(1))
                    continue
                for w in re.sub(r"</?c>", "", tok).split():
                    if not w.startswith("["):
                        out.append((t, w))
    return out


def fetch_subs(vid, subs, proxy):
    cmd = ["yt-dlp", "-q", "--skip-download", "--write-auto-subs", "--sub-langs", "en-orig,en",
           "--sub-format", "vtt", "-o", os.path.join(subs, "%(id)s"), f"https://www.youtube.com/watch?v={vid}"]
    if proxy:
        cmd[1:1] = ["--proxy", proxy]
    subprocess.run(cmd, check=False)


def caption_file(vid, subs):
    for lang in ("en-orig", "en"):
        p = os.path.join(subs, f"{vid}.{lang}.vtt")
        if os.path.exists(p):
            return p
    return None


def secs(d):
    if isinstance(d, (int, float)):
        return float(d)
    parts = [int(x) for x in str(d).split(":")]
    s = 0
    for x in parts:
        s = s * 60 + x
    return float(s)


def analyse(vid, path, dur, name):
    w = words(path)
    ivs = []
    for i, (t, _) in enumerate(w):
        nt = w[i + 1][0] if i + 1 < len(w) else t + 0.4
        ivs.append((t, nt if nt - t < 1.2 else t + 0.4))
    cover = sum(b - a for a, b in ivs)
    text = " ".join(x for _, x in w)
    raw = open(path, encoding="utf-8").read()
    first60 = " ".join(x for t, x in w if t < 60)
    intro = r"\bI'?m " + (re.escape(name) if name else r"[A-Z][a-z]+") + r"\b"
    calq = []
    for pat, gloss in CALQUES:
        for m in re.finditer(pat, text, re.I):
            a = max(0, m.start() - 60)
            calq.append({"gloss": gloss, "context": text[a:m.end() + 40]})
    return {
        "id": vid, "duration_s": dur, "words": len(w),
        "wpm": round(len(w) / (dur / 60), 1) if dur else None,
        "coverage": round(cover / dur, 3) if dur else None,
        "fillers": len(re.findall(FILLERS, text, re.I)),
        "past_tense": len(re.findall(PAST, text)),
        "present_progressive": len(re.findall(PRESENT, text)),
        "other_speakers": raw.count("&gt;&gt;"),
        "music_tags": raw.count("[music]"),
        "template": {
            "self_intro": bool(re.search(intro, first60, re.I)),
            "money": len(re.findall(MONEY, text, re.I)),
            "usd": len(re.findall(USD, text, re.I)),
            "ask_audience": len(re.findall(ASK, text, re.I)),
            "clock_times": len(re.findall(CLOCK, text, re.I)),
            "closing": bool(re.search(CLOSING, " ".join(x for t, x in w if t > (dur or 0) - 90), re.I)),
        },
        "opening": " ".join(x for _, x in w[:45]),
        "calques": calq,
    }


def scan_comments(cdir):
    hits = {k: [] for k in COMMENT_PATTERNS}
    replies = []
    for f in sorted(glob.glob(os.path.join(cdir, "*.info.json"))):
        d = json.load(open(f, encoding="utf-8"))
        cs = d.get("comments") or []
        by = {c["id"]: c for c in cs}
        for c in cs:
            if c.get("author_is_uploader"):
                if re.search(UPLOADER_TOPICS, c.get("text", ""), re.I):
                    p = by.get(c.get("parent"))
                    replies.append({"video": d["id"], "question": (p or {}).get("text", "")[:300], "reply": c["text"][:300]})
                continue
            for k, pat in COMMENT_PATTERNS.items():
                if re.search(pat, c.get("text", ""), re.I):
                    hits[k].append({"video": d["id"], "likes": c.get("like_count") or 0, "author": c.get("author"), "text": c["text"][:300]})
    out = {}
    for k, v in hits.items():
        v.sort(key=lambda x: -x["likes"])
        out[k] = {"comments": len(v), "people": len({x["author"] for x in v}), "top": v[:5]}
    return out, replies


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("channel_dir")
    ap.add_argument("--subs", required=True, help="folder with <id>.en-orig.vtt (missing ones are downloaded)")
    ap.add_argument("--comments", help="folder of yt-dlp --write-comments info.json files")
    ap.add_argument("--titles", help="titles_zh.json for nicer labels")
    ap.add_argument("--name", help="creator's on-screen name, for the self-introduction check")
    ap.add_argument("--out", default="narration.json")
    ap.add_argument("--slides")
    ap.add_argument("--proxy")
    a = ap.parse_args()

    vids = json.load(open(os.path.join(a.channel_dir, "long.json"), encoding="utf-8"))
    vids.sort(key=lambda v: v.get("date") or "")
    titles = json.load(open(a.titles, encoding="utf-8")) if a.titles else {}
    os.makedirs(a.subs, exist_ok=True)
    rows = []
    for v in vids:
        path = caption_file(v["id"], a.subs)
        if not path:
            fetch_subs(v["id"], a.subs, a.proxy)
            path = caption_file(v["id"], a.subs)
        if not path:
            print(f"  no captions: {v['id']} {v['title'][:40]}", file=sys.stderr)
            continue
        r = analyse(v["id"], path, secs(v.get("duration") or 0), a.name)
        r.update(date=v.get("date"), views=v.get("views"), title=v["title"], title_zh=titles.get(v["id"]))
        rows.append(r)
    if not rows:
        sys.exit("no captions found")

    tot_w = sum(r["words"] for r in rows)
    tot_d = sum(r["duration_s"] for r in rows)
    cov = sum(r["coverage"] * r["duration_s"] for r in rows) / tot_d
    top3 = sorted(rows, key=lambda r: -(r["views"] or 0))[:3]
    n = len(rows)
    tmpl = {
        "反差 / 钩子开头": sum(1 for r in rows if not re.search(r"\bI'?m \w+", " ".join(r["opening"].split()[:8]), re.I)),
        "自我介绍": sum(r["template"]["self_intro"] for r in rows),
        "报具体金额": sum(1 for r in rows if r["template"]["money"]),
        "换算成美元": sum(1 for r in rows if r["template"]["usd"]),
        "报时间点": sum(1 for r in rows if r["template"]["clock_times"]),
        "向观众提问": sum(1 for r in rows if r["template"]["ask_audience"]),
        "结尾告别": sum(r["template"]["closing"] for r in rows),
    }
    summary = {
        "videos": n, "words": tot_w, "minutes": round(tot_d / 60, 1),
        "coverage": round(cov, 3),
        "wpm_overall": round(tot_w / (tot_d / 60), 1),
        "wpm_range": [min(r["wpm"] for r in rows), max(r["wpm"] for r in rows)],
        "wpm_top3_median": statistics.median(r["wpm"] for r in top3),
        "top3": [r["id"] for r in top3],
        "fillers": sum(r["fillers"] for r in rows),
        "fillers_per_1000": round(sum(r["fillers"] for r in rows) / tot_w * 1000, 2),
        "past_tense_max": max(rows, key=lambda r: r["past_tense"])["id"],
        "template": tmpl,
    }
    result = {"summary": summary, "videos": rows}
    if a.comments:
        result["comments"], result["uploader_replies"] = scan_comments(a.comments)
    json.dump(result, open(a.out, "w", encoding="utf-8"), ensure_ascii=False, indent=1)

    s = summary
    print(f"{n} videos, {s['minutes']} min, {tot_w:,} words")
    print(f"  narration covers {s['coverage']*100:.0f}% of runtime; {s['wpm_overall']} wpm overall "
          f"({s['wpm_range'][0]:.0f}-{s['wpm_range'][1]:.0f}); top-3 median {s['wpm_top3_median']}")
    print(f"  fillers (uh/um): {s['fillers']} = {s['fillers_per_1000']} per 1,000 words  (spontaneous talk is usually 10+)")
    for r in rows:
        print(f"  {r['date']} {r['id']} cov {r['coverage']*100:3.0f}%  wpm {r['wpm']:5.1f}  fillers {r['fillers']}  "
              f"past {r['past_tense']:2d}  others {r['other_speakers']}  {r['title'][:38]}")
    print("  template:", ", ".join(f"{k} {v}/{n}" for k, v in tmpl.items()))
    calq = [c for r in rows for c in r["calques"]]
    if calq:
        print(f"  calque candidates ({len(calq)}), check by hand:")
        for c in calq[:12]:
            print(f"    [{c['gloss']}] …{c['context']}…")
    if a.comments:
        for k, v in result["comments"].items():
            print(f"  comments {k}: {v['comments']} ({v['people']} people)")
        for rp in result["uploader_replies"][:8]:
            print(f"    uploader: Q {rp['question'][:80]!r} -> A {rp['reply'][:100]!r}")

    if a.slides:
        def label(r):
            return f"{r['date'][5:]} {r['title_zh'] or r['title'][:18]}"
        slides = [
            {"type": "stats4", "section": "旁白分析", "eyebrow": "旁白分析",
             "title": f"旁白是核心：全片 {s['coverage']*100:.0f}% 的时间都在说话",
             "tiles": [{"label": "旁白占全片时长", "value": f"{s['coverage']*100:.0f}%", "sub": f"{n} 条平均", "dark": True},
                       {"label": "语速", "value": f"{s['wpm_overall']:.0f} 词/分", "sub": f"{n} 条在 {s['wpm_range'][0]:.0f}–{s['wpm_range'][1]:.0f}"},
                       {"label": "旁白总量", "value": f"{tot_w/10000:.1f} 万词" if tot_w >= 10000 else f"{tot_w:,} 词", "sub": f"{n} 条视频"},
                       {"label": "uh / um 口头语", "value": f"{s['fillers']} 个", "sub": f"每千词 {s['fillers_per_1000']} 个"}],
             "bullets": ["（结论：画面是配图还是主角？）", "（结论：照稿念还是即兴说？口头语越少越像念稿）"],
             "note": "按油管自动英文字幕的逐词时间统计；词与词间隔小于 1.2 秒算连续说话。",
             "video": {"bullets": ["（关键词）", "（关键词）"]}},
            {"type": "table", "eyebrow": "旁白分析", "title": "逐条看：旁白占比和语速",
             "columns": [{"label": "视频", "align": "left", "width": 0.46}, {"label": "旁白占比", "align": "right", "width": 0.18},
                         {"label": "每分钟词数", "align": "right", "width": 0.18}, {"label": "口头语", "align": "right", "width": 0.18}],
             "rows": [[label(r), f"{r['coverage']*100:.0f}%", f"{r['wpm']:.0f}", str(r["fillers"])] for r in rows],
             "font_size": 13, "row_h": 0.4, "video": False,
             "portrait": {"columns": [{"label": "视频", "align": "left", "width": 0.52}, {"label": "旁白", "align": "right", "width": 0.24},
                                      {"label": "词/分", "align": "right", "width": 0.24}],
                          "rows": [[label(r), f"{r['coverage']*100:.0f}%", f"{r['wpm']:.0f}"] for r in rows]}},
            {"type": "rows", "eyebrow": "旁白分析", "title": "每条旁白都套同一个模板",
             "rows": [{"name": k, "desc": "（补一句原话做例子）", "tag": f"{v} / {n}"} for k, v in tmpl.items()][:6],
             "notes": "数字是出现该环节的视频条数，由关键词粗算，要对照字幕核对。"},
        ]
        if a.comments:
            c = result["comments"]
            slides.append({"type": "panels", "eyebrow": "旁白分析", "title": "观众怎么看她的旁白",
                           "panels": [{"title": "夸声音和英语", "big": f"{c['夸声音 / 英语']['people']} 人", "line": "（引一句高赞原话）", "sub": "评论关键词统计"},
                                      {"title": "怀疑是 AI 配音", "big": f"约 {c['怀疑 AI 配音']['comments']} 条", "line": "（引一句原话）",
                                       "sub": f"另有 {c['替她说是本人']['comments']} 条替她说话", "dark": True}],
                           "box": {"title": "她怎么回应", "text": "（看 uploader_replies，写她本人对口音、配音、写稿的回复）"}})
        json.dump(slides, open(a.slides, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
        print(f"wrote {len(slides)} draft slides to {a.slides} — fill the （…） placeholders, then splice in under 旁白分析")


if __name__ == "__main__":
    main()
