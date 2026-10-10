#!/usr/bin/env python3
"""Collect evidence about a channel's filming gear and shooting style.

    python3 gear_scan.py WORK/data/<handle> --out WORK/gear [--top 8 --recent 4 --comments 200 --proxy socks5://127.0.0.1:1091]

YouTube exposes no camera metadata, so this gathers what can be seen from outside:
  1. every long video's description + the channel description, scanned for gear words and affiliate links;
  2. top-level comments on the sampled videos, scanned for gear / voice / shooting-style remarks
     (creator comments flagged);
  3. three auto-captured frames per sampled video (i.ytimg.com maxres1-3, falling back to hq1-3),
     tiled into labelled contact sheets for visual review;
  4. optionally, resolution / fps / dynamic range from yt-dlp (needs --proxy or an unblocked IP).

Writes evidence.json, evidence.md, frames/*.jpg and sheet-N.jpg into --out. The model then looks at the
sheets, counts shooting styles per frame and writes gear.json (see references/gear.md).
"""
import argparse
import json
import os
import re
import shutil
import subprocess
import sys
import time
import urllib.request
from collections import Counter
from concurrent.futures import ThreadPoolExecutor

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import yt  # noqa: E402

GEAR = {
    # Brand words are only counted with a model or "camera" next to them: "Pachelbel's Canon" and
    # "x3 the price" were real false hits.
    "相机/云台": r"\b(dji|osmo|pocket ?[234]|osmo action ?[3-6]|insta ?360( x[345]| ace pro| go ?3)?|gopro|hero ?1[0-4]|sony (zv|a7|fx)\S*|zv-?e?1\d*|fx3|fx30|canon (eos|r\d+|g7)\S*|g7x|nikon z\S*|fujifilm|x-?s20|lumix|gimbal|stabili[sz]er)\b",
    "手机": r"\b(iphone ?1\d( pro( max)?)?|iphone|samsung galaxy|galaxy s2\d|pixel ?\d( pro)?|xiaomi ?1\d|huawei (p|mate) ?\d+)\b",
    "麦克风": r"\b(dji mic|mic ?mini|rode|wireless go|lark|hollyland|lav(alier)?|microphone|wrist ?band mic)\b",
    "三脚架/灯光": r"\b(tripod|selfie stick|neewer|ulanzi|ring light|softbox|led light)\b",
    "剪辑软件": r"\b(capcut|剪映|premiere|final cut|davinci|lumafusion)\b",
    "配音/AI": r"\b(ai voice|elevenlabs|text to speech|tts|voice ?over|own voice|real voice)\b",
    "音乐素材": r"\b(epidemic sound|artlist|musicbed|soundstripe)\b",
    "带货链接": r"(amzn\.to|amazon\.com/shop|geni\.us|kit\.co|bit\.ly)",
}
STYLE = r"\b(camera angles?|camera work|cameraman|set(ting)? up (the|your) camera|tripod|selfie|pov|drone|subtitles?|editing|cinematic|documentary)\b"


def snippet(text, m, pad=80):
    return text[max(0, m.start() - pad):m.end() + pad].replace("\n", " ").strip()


def description(vid):
    try:
        r = yt.call("next", {"videoId": vid})
        return vid, next((x.get("content") for x in yt.walk(r, "attributedDescription") if isinstance(x, dict) and x.get("content")), "") or ""
    except Exception:  # noqa: BLE001
        return vid, ""


def comments(vid, limit):
    """Top-level comments in the default (top) order."""
    try:
        r = yt.call("next", {"videoId": vid})
    except Exception:  # noqa: BLE001
        return []
    tok = None
    for s in yt.walk(r, "itemSectionRenderer"):
        if s.get("sectionIdentifier") == "comment-item-section":
            tok = next((c["token"] for c in yt.walk(s, "continuationCommand")), None)
            break
    out, seen, pages = [], set(), 0
    while tok and len(out) < limit and pages < 40:
        try:
            rr = yt.call("next", {"continuation": tok})
        except Exception:  # noqa: BLE001
            break
        pages += 1
        new = []
        for m in yt.walk(rr, "commentEntityPayload"):
            p = m.get("properties", {})
            if p.get("replyLevel", 0) or p.get("commentId") in seen:
                continue
            seen.add(p.get("commentId"))
            new.append({"text": p.get("content", {}).get("content", ""), "likes": m.get("toolbar", {}).get("likeCountNotliked", "0").strip() or "0",
                        "creator": bool(m.get("author", {}).get("isCreator"))})
        if not new:
            break
        out += new
        tok = None
        for ci in yt.walk(rr, "continuationItemRenderer"):
            ce = ci.get("continuationEndpoint")
            if ce and ce.get("continuationCommand"):
                tok = ce["continuationCommand"]["token"]
        time.sleep(0.2)
    return out


def likes_num(s):
    s = str(s).replace(",", "")
    m = re.match(r"([\d.]+)\s*([KM]?)", s)
    return int(float(m.group(1)) * {"": 1, "K": 1e3, "M": 1e6}[m.group(2)]) if m else 0


def fetch_frame(vid, k, dest):
    for name in (f"maxres{k}.jpg", f"hq{k}.jpg"):
        try:
            data = urllib.request.urlopen(f"https://i.ytimg.com/vi/{vid}/{name}", timeout=20).read()
            if len(data) > 3000:
                open(dest, "wb").write(data)
                return True
        except Exception:  # noqa: BLE001
            continue
    return False


def tile(frames, out_dir):
    """Contact sheets of 12 labelled frames (Pillow if available, else ffmpeg without labels)."""
    sheets = []
    try:
        from PIL import Image, ImageDraw
        W, H = 420, 236
        for g in range(0, len(frames), 12):
            chunk = frames[g:g + 12]
            sheet = Image.new("RGB", (W * 3 + 40, (H + 10) * 4 + 10), "#202020")
            dr = ImageDraw.Draw(sheet)
            for i, (label, path) in enumerate(chunk):
                im = Image.open(path).convert("RGB")
                w, h = im.size
                ch = w * 9 // 16
                im = im.crop((0, max((h - ch) // 2, 0), w, max((h - ch) // 2, 0) + min(ch, h))).resize((W, H))
                x, y = 10 + (i % 3) * (W + 10), 10 + (i // 3) * (H + 10)
                sheet.paste(im, (x, y))
                dr.rectangle([x, y, x + 64, y + 22], fill="#000000")
                dr.text((x + 6, y + 5), label, fill="#ffffff")
            p = os.path.join(out_dir, f"sheet-{g // 12 + 1}.jpg")
            sheet.save(p, quality=85)
            sheets.append(p)
    except ImportError:
        ff = shutil.which("ffmpeg")
        if not ff:
            return sheets
        for g in range(0, len(frames), 12):
            chunk = frames[g:g + 12]
            lst = os.path.join(out_dir, f"list-{g // 12 + 1}.txt")
            open(lst, "w").write("".join(f"file '{os.path.abspath(p)}'\n" for _, p in chunk))
            p = os.path.join(out_dir, f"sheet-{g // 12 + 1}.jpg")
            subprocess.run([ff, "-y", "-loglevel", "error", "-f", "concat", "-safe", "0", "-i", lst, "-vf",
                            "scale=420:236:force_original_aspect_ratio=increase,crop=420:236,tile=3x4:padding=10:margin=10", "-frames:v", "1", p])
            os.remove(lst)
            if os.path.exists(p):
                sheets.append(p)
    return sheets


def specs(vids, proxy):
    yd = shutil.which("yt-dlp")
    if not yd:
        return []
    env = dict(os.environ, NO_PROXY="*") if proxy else None
    out = []
    for vid in vids:
        cmd = [yd, "--skip-download", "--print", "%(id)s|%(width)s|%(height)s|%(fps)s|%(dynamic_range)s", f"https://www.youtube.com/watch?v={vid}"]
        if proxy:
            cmd[1:1] = ["--proxy", proxy]
        try:
            r = subprocess.run(cmd, capture_output=True, text=True, timeout=120, env=env)
            line = next((l for l in r.stdout.splitlines() if l.startswith(vid)), None)
            if line:
                _, w, h, fps, dyn = line.split("|")
                out.append({"id": vid, "width": w, "height": h, "fps": fps, "dynamic_range": dyn})
        except Exception:  # noqa: BLE001
            continue
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("channel_dir", help="a folder written by fetch_channel.py")
    ap.add_argument("--out", required=True)
    ap.add_argument("--top", type=int, default=8, help="most-viewed long videos to sample")
    ap.add_argument("--recent", type=int, default=4, help="most recent long videos to add (gear changes over time)")
    ap.add_argument("--comments", type=int, default=200, help="top-level comments per sampled video")
    ap.add_argument("--proxy", help="e.g. socks5://127.0.0.1:1091, for yt-dlp specs when this IP is bot-blocked")
    ap.add_argument("--no-specs", action="store_true")
    a = ap.parse_args()
    os.makedirs(os.path.join(a.out, "frames"), exist_ok=True)
    about = json.load(open(os.path.join(a.channel_dir, "about.json")))
    long = json.load(open(os.path.join(a.channel_dir, "long.json")))
    by_views = sorted(long, key=lambda v: -(v.get("views") or 0))
    by_date = sorted(long, key=lambda v: v.get("date") or "", reverse=True)
    sample = []
    for v in by_views[:a.top] + by_date[:a.recent]:
        if v["id"] not in [s["id"] for s in sample]:
            sample.append(v)

    # 1. descriptions (all long videos) + channel description
    with ThreadPoolExecutor(6) as ex:
        descs = dict(ex.map(description, [v["id"] for v in long]))
    try:
        ch_desc = re.search(r'"description":"((?:[^"\\]|\\.)*)"', yt.get_html(f"https://www.youtube.com/channel/{about['channel_id']}/about"))
        ch_desc = json.loads('"' + ch_desc.group(1) + '"') if ch_desc else ""
    except Exception:  # noqa: BLE001
        ch_desc = ""
    desc_hits = []
    for vid, text in list(descs.items()) + [("channel", ch_desc)]:
        for cat, pat in GEAR.items():
            for m in re.finditer(pat, text, re.I):
                desc_hits.append({"video": vid, "category": cat, "match": m.group(0), "context": snippet(text, m)})

    # 2. comments on the sampled videos
    with ThreadPoolExecutor(4) as ex:
        coms = dict(zip([v["id"] for v in sample], ex.map(lambda v: comments(v["id"], a.comments), sample)))
    com_hits, cat_count, style_count, n_com = [], Counter(), Counter(), 0
    for vid, L in coms.items():
        n_com += len(L)
        for c in L:
            cats = [cat for cat, pat in GEAR.items() if re.search(pat, c["text"], re.I)]
            styles = re.findall(STYLE, c["text"], re.I)
            for cat in cats:
                cat_count[cat] += 1
            for s_ in styles:
                style_count[(s_[0] if isinstance(s_, tuple) else s_).lower()] += 1
            if cats or styles:
                com_hits.append({"video": vid, "categories": cats, "styles": [(s_[0] if isinstance(s_, tuple) else s_).lower() for s_ in styles],
                                 "likes": likes_num(c["likes"]), "creator": c["creator"], "text": c["text"].replace("\n", " ")[:220]})
    com_hits.sort(key=lambda x: (not x["creator"], -x["likes"]))

    # 3. frames
    frames, labels = [], {}
    for i, v in enumerate(sample, 1):
        for k in (1, 2, 3):
            p = os.path.join(a.out, "frames", f"{v['id']}_{k}.jpg")
            if fetch_frame(v["id"], k, p):
                lab = f"V{i}-{k}"
                frames.append((lab, p))
                labels[lab] = {"id": v["id"], "title": v.get("title"), "date": v.get("date"), "views": v.get("views")}
    sheets = tile(frames, a.out)

    # 4. specs
    spec = [] if a.no_specs else specs([v["id"] for v in sample[:4]], a.proxy)

    ev = {"channel": about.get("title"), "handle": about.get("handle"), "sampled": [{"label": f"V{i}", "id": v["id"], "title": v.get("title"), "date": v.get("date"), "views": v.get("views")} for i, v in enumerate(sample, 1)],
          "descriptions_scanned": len(descs), "description_hits": desc_hits, "comments_scanned": n_com,
          "comment_gear_counts": dict(cat_count), "comment_style_counts": dict(style_count.most_common(12)),
          "comment_hits": com_hits[:60], "frames": labels, "sheets": sheets, "specs": spec}
    json.dump(ev, open(os.path.join(a.out, "evidence.json"), "w"), ensure_ascii=False, indent=1)

    md = [f"# {about.get('title')} 拍摄器材证据", "",
          f"- 简介：扫描 {len(descs)} 条长视频简介 + 频道简介，器材相关命中 {len(desc_hits)} 处",
          f"- 评论：{len(sample)} 条视频共 {n_com} 条一级评论；器材类 {dict(cat_count)}；拍摄方式类 {dict(style_count.most_common(8))}",
          f"- 截帧：{len(frames)} 张，联系表 {len(sheets)} 张",
          f"- 技术参数：" + ("; ".join(f"{s['id']} {s['width']}x{s['height']} {s['fps']}fps {s['dynamic_range']}" for s in spec) or "未获取"), "",
          "## 简介命中", ""] + [f"- [{h['category']}] {h['video']}: …{h['context']}…" for h in desc_hits[:30]] + \
         ["", "## 评论命中（博主本人优先，其余按赞数）", ""] + [f"- {'【博主】' if h['creator'] else ''}{h['likes']} 赞 {h['categories'] + h['styles']}: {h['text']}" for h in com_hits[:30]] + \
         ["", "## 截帧标签", ""] + [f"- {k}: {v['date']} {v['views']:,} 播放 · {v['title']}" for k, v in labels.items()]
    open(os.path.join(a.out, "evidence.md"), "w").write("\n".join(md) + "\n")
    print("\n".join(md[:7]))
    print("sheets:", *sheets, sep="\n  ")


if __name__ == "__main__":
    main()
