#!/usr/bin/env python3
"""Preview of the video version: lay a 16:9 placeholder (--ratio) over the bottom of each rendered slide
(where the user's landscape facecam goes), mock the phone's status bar on top, shade the strips
抖音 crops off the sides, and tile the pages into contact sheets.

    python3 facecam_preview.py WORK/png-facecam [--cols 6] [--rows 2]

Writes WORK/png-facecam/preview/preview-N.png. Content touching the placeholder means the slide
runs into the camera band.
"""
import argparse
import glob
import os

from PIL import Image, ImageDraw, ImageFont

ap = argparse.ArgumentParser()
ap.add_argument("png_dir")
ap.add_argument("--cols", type=int, default=6)
ap.add_argument("--rows", type=int, default=2)
ap.add_argument("--ratio", default="16:9", help="facecam aspect ratio, same as meta.facecam_ratio")
a = ap.parse_args()

pages = sorted(p for p in glob.glob(os.path.join(a.png_dir, "*.png")) if not os.path.basename(p).startswith("sheet-"))
if not pages:
    raise SystemExit(f"no slide pngs in {a.png_dir}")
out = os.path.join(a.png_dir, "preview")
os.makedirs(out, exist_ok=True)


def font(size):
    for f in ("/System/Library/Fonts/PingFang.ttc", "/System/Library/Fonts/STHeiti Medium.ttc"):
        if os.path.exists(f):
            return ImageFont.truetype(f, size)
    return ImageFont.load_default()


def overlay(path, n):
    im = Image.open(path).convert("RGB")
    w, h = im.size
    rw, rh = (float(x) for x in a.ratio.split(":"))
    cam_h = round(w * rh / rw)
    d = ImageDraw.Draw(im, "RGBA")
    d.rectangle([0, h - cam_h, w, h], fill=(40, 44, 56, 215))
    f = font(max(14, w // 22))
    label = f"{a.ratio} 自拍画面"
    tw = d.textlength(label, font=f)
    d.text(((w - tw) / 2, h - cam_h / 2 - f.size / 2), label, font=font(max(14, w // 22)), fill=(235, 235, 235))
    # Mock 抖音 status bar (and the Dynamic Island below): the app crops ~0.37 in off each side of the 7.5 in slide, clock centred
    # 0.46 in down at x 1.63 in, signal / wifi / battery centred at x 5.86 in.
    px = w / 7.5
    cy, fs = 0.46 * px, font(max(11, round(0.27 * px)))
    clock = "21:20"
    d.text((1.63 * px - d.textlength(clock, font=fs) / 2, cy - fs.size * 0.6), clock, font=fs, fill=(120, 120, 120))
    bx = 5.78 * px
    for k in range(4):  # signal bars
        bh = (k + 1) * 0.045 * px
        d.rectangle([bx - 0.62 * px + k * 0.07 * px, cy + 0.09 * px - bh, bx - 0.57 * px + k * 0.07 * px, cy + 0.09 * px], fill=(120, 120, 120))
    d.rounded_rectangle([bx + 0.05 * px, cy - 0.09 * px, bx + 0.42 * px, cy + 0.09 * px], radius=0.05 * px, fill=(120, 120, 120))
    # 抖音 back arrow and search icon, centred 1.26 in down; Dynamic Island in the middle of the status bar.
    by, r = 1.26 * px, 0.11 * px
    d.line([(0.8 * px, by - r), (0.68 * px, by), (0.8 * px, by + r)], fill=(120, 120, 120), width=max(2, round(px * 0.03)))
    d.ellipse([6.62 * px - r, by - r, 6.62 * px + r * 0.6, by + r * 0.6], outline=(120, 120, 120), width=max(2, round(px * 0.03)))
    d.rounded_rectangle([2.78 * px, 0.17 * px, 4.71 * px, 0.73 * px], radius=0.28 * px, fill=(0, 0, 0))
    d.rectangle([0, 0, 0.37 * px, h], fill=(0, 0, 0, 60))
    d.rectangle([w - 0.37 * px, 0, w, h], fill=(0, 0, 0, 60))
    d.text((0.4 * px, 1.65 * px), str(n), font=font(max(12, w // 30)), fill=(150, 150, 150))
    return im


per = a.cols * a.rows
for s in range(0, len(pages), per):
    ims = [overlay(p, s + i + 1) for i, p in enumerate(pages[s:s + per])]
    w, h = ims[0].size
    gap = 12
    rows = (len(ims) + a.cols - 1) // a.cols
    sheet = Image.new("RGB", (a.cols * w + (a.cols + 1) * gap, rows * h + (rows + 1) * gap), (140, 140, 140))
    for i, im in enumerate(ims):
        sheet.paste(im, (gap + (i % a.cols) * (w + gap), gap + (i // a.cols) * (h + gap)))
    dst = os.path.join(out, f"preview-{s // per + 1}.png")
    sheet.save(dst)
    print(dst)
