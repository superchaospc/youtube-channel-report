#!/usr/bin/env bash
# Render a .pptx to PNGs (and optionally a PDF) with Keynote, then tile the PNGs
# into contact sheets for a quick visual check. macOS only.
#
#   render_check.sh deck.pptx OUT_DIR [--pdf]
#
# Keynote's import is close to PowerPoint's rendering for text, tables and shapes
# (it shows native pptxgenjs charts as blank, which is why build_deck.js draws
# bars with shapes). Without Keynote, use LibreOffice:
#   soffice --headless --convert-to pdf deck.pptx && pdftoppm -png -r 80 deck.pdf slide
set -euo pipefail
deck="$(cd "$(dirname "$1")" && pwd)/$(basename "$1")"
out="$2"; pdf="${3:-}"
mkdir -p "$out"; out="$(cd "$out" && pwd)"
rm -f "$out"/*.png

pgrep -x Keynote >/dev/null || { open -a Keynote; sleep 5; }
osascript \
  -e "set f to POSIX file \"$deck\"" \
  -e "set o to POSIX file \"$out\"" \
  -e 'with timeout of 900 seconds' -e 'tell application "Keynote"' \
  -e '  set d to open f' \
  -e '  delay 3' \
  -e '  export d to o as slide images with properties {image format:PNG}' \
  -e '  close d saving no' \
  -e 'end tell' -e 'end timeout'

if [ "$pdf" = "--pdf" ]; then
  pdfout="${deck%.pptx}.pdf"
  osascript \
    -e "set f to POSIX file \"$deck\"" \
    -e "set o to POSIX file \"$pdfout\"" \
    -e 'with timeout of 900 seconds' -e 'tell application "Keynote"' \
    -e '  set d to open f' \
    -e '  delay 3' \
    -e '  export d to o as PDF' \
    -e '  close d saving no' \
    -e 'end tell' -e 'end timeout'
  echo "pdf: $pdfout"
fi

# Contact sheets, 6 landscape or 8 portrait slides each (needs Pillow; skipped quietly without it).
"${PYTHON:-python3}" - "$out" <<'EOF' || echo "(no Pillow: open the PNGs directly)"
import glob, sys
from PIL import Image
fs = sorted(f for f in glob.glob(sys.argv[1] + "/*.png") if "/sheet-" not in f)
# Keep the slide's own aspect ratio: 6 landscape slides as 2×3, or 8 portrait (9:16) slides as 4×2.
w0, h0 = Image.open(fs[0]).size if fs else (16, 9)
portrait = h0 > w0
cols, rows = (4, 2) if portrait else (2, 3)
W = 440 if portrait else 900
H = round(W * h0 / w0)
per = cols * rows
for g in range(0, len(fs), per):
    sheet = Image.new("RGB", ((W + 10) * cols + 10, (H + 20) * rows + 10), "#888")
    for i, f in enumerate(fs[g:g + per]):
        sheet.paste(Image.open(f).convert("RGB").resize((W, H)), (10 + (i % cols) * (W + 10), 10 + (i // cols) * (H + 20)))
    p = f"{sys.argv[1]}/sheet-{g // per + 1}.png"
    sheet.save(p)
    print(p)
EOF
ls "$out"/*.png | grep -vc sheet- | xargs echo "slides rendered:"
