#!/usr/bin/env python3
"""Sample frames at a fixed interval from a channel's long videos and tile them into labelled
contact sheets, for counting who is on screen and who is filming (role / collaboration analysis).

    python3 frame_sample.py DATA/<handle> --out WORK/collab [--every 20] [--top 12] [--proxy socks5://…]

gear_scan.py only gets YouTube's 3 auto-thumbnails per video; that is enough for camera style but
not for "how much of the video is the sister / the brother / the dad". This downloads a 240p
video-only copy (≈20 MB per 15 min, kept in OUT/video/ so reruns are free), takes one frame every
N seconds, and writes OUT/sheets/<n>-<id>.jpg (6 columns, each tile labelled V<n> mm:ss) plus
OUT/frames.json listing every sampled frame. Then look at each sheet and record the counts in
roles.json (see references/collab.md).
"""
import argparse, json, os, subprocess, sys
from concurrent.futures import ThreadPoolExecutor
from PIL import Image, ImageDraw, ImageFont

COLS, TW, TH = 6, 320, 180


def download(vid, dest, proxy):
    out = os.path.join(dest, f"{vid}.mp4")
    if os.path.exists(out) and os.path.getsize(out) > 0:
        return out
    cmd = ["yt-dlp", "-q", "--no-progress", "-f", "133/160/134/18", "-o", out,
           f"https://www.youtube.com/watch?v={vid}"]
    if proxy:
        cmd[1:1] = ["--proxy", proxy]
    subprocess.run(cmd, check=True)
    return out


def extract(path, every, fdir):
    os.makedirs(fdir, exist_ok=True)
    subprocess.run(["ffmpeg", "-loglevel", "error", "-y", "-i", path, "-vf",
                    f"fps=1/{every},scale={TW}:{TH}:force_original_aspect_ratio=decrease,"
                    f"pad={TW}:{TH}:(ow-iw)/2:(oh-ih)/2",
                    os.path.join(fdir, "%04d.jpg")], check=True)
    return sorted(os.path.join(fdir, f) for f in os.listdir(fdir) if f.endswith(".jpg"))


def font(size):
    for f in ("/System/Library/Fonts/Supplemental/Arial Bold.ttf", "/System/Library/Fonts/Helvetica.ttc"):
        if os.path.exists(f):
            return ImageFont.truetype(f, size)
    return ImageFont.load_default()


def tile(label, frames, every, out):
    rows = (len(frames) + COLS - 1) // COLS
    sheet = Image.new("RGB", (COLS * (TW + 6) + 6, rows * (TH + 6) + 6), (30, 30, 30))
    d, f = ImageDraw.Draw(sheet), font(18)
    for i, fp in enumerate(frames):
        x, y = 6 + (i % COLS) * (TW + 6), 6 + (i // COLS) * (TH + 6)
        sheet.paste(Image.open(fp), (x, y))
        t = (i + 1) * every - every // 2 if every > 1 else i
        txt = f"{label} {t // 60:02d}:{t % 60:02d}"
        d.rectangle([x, y, x + 118, y + 24], fill=(0, 0, 0))
        d.text((x + 5, y + 2), txt, fill=(255, 255, 255), font=f)
    sheet.save(out, quality=85)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("data")
    ap.add_argument("--out", required=True)
    ap.add_argument("--every", type=int, default=20, help="seconds between frames")
    ap.add_argument("--top", type=int, default=12, help="how many long videos (newest first)")
    ap.add_argument("--proxy")
    a = ap.parse_args()
    vids = json.load(open(os.path.join(a.data, "long.json")))
    vids = sorted(vids, key=lambda v: v.get("date", ""), reverse=True)[: a.top]
    vids = sorted(vids, key=lambda v: v.get("date", ""))          # V1 = oldest, reads as a timeline
    vdir, sdir = os.path.join(a.out, "video"), os.path.join(a.out, "sheets")
    os.makedirs(vdir, exist_ok=True); os.makedirs(sdir, exist_ok=True)
    with ThreadPoolExecutor(3) as ex:
        paths = list(ex.map(lambda v: download(v["id"], vdir, a.proxy), vids))
    index = []
    for n, (v, p) in enumerate(zip(vids, paths), 1):
        frames = extract(p, a.every, os.path.join(a.out, "frames", v["id"]))
        sheet = os.path.join(sdir, f"{n:02d}-{v['id']}.jpg")
        tile(f"V{n}", frames, a.every, sheet)
        index.append({"label": f"V{n}", "id": v["id"], "title": v["title"], "date": v.get("date"),
                      "views": v.get("views"), "frames": len(frames), "every": a.every, "sheet": sheet})
        print(f"V{n} {v['id']} {len(frames)} frames -> {sheet}")
    json.dump(index, open(os.path.join(a.out, "frames.json"), "w"), ensure_ascii=False, indent=1)


if __name__ == "__main__":
    sys.exit(main())
