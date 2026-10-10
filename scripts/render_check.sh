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
  -e 'tell application "Keynote"' \
  -e '  set d to open f' \
  -e '  delay 3' \
  -e '  export d to o as slide images with properties {image format:PNG}' \
  -e '  close d saving no' \
  -e 'end tell'

if [ "$pdf" = "--pdf" ]; then
  pdfout="${deck%.pptx}.pdf"
  osascript \
    -e "set f to POSIX file \"$deck\"" \
    -e "set o to POSIX file \"$pdfout\"" \
    -e 'tell application "Keynote"' \
    -e '  set d to open f' \
    -e '  delay 3' \
    -e '  export d to o as PDF' \
    -e '  close d saving no' \
    -e 'end tell'
  echo "pdf: $pdfout"
fi

# Contact sheets, 6 slides each (needs Pillow; skipped quietly without it).
"${PYTHON:-python3}" - "$out" <<'EOF' || echo "(no Pillow: open the PNGs directly)"
import glob, sys
from PIL import Image
fs = sorted(f for f in glob.glob(sys.argv[1] + "/*.png") if "/sheet-" not in f)
W, H = 900, 506
for g in range(0, len(fs), 6):
    sheet = Image.new("RGB", (W * 2 + 30, (H + 20) * 3 + 10), "#888")
    for i, f in enumerate(fs[g:g + 6]):
        sheet.paste(Image.open(f).convert("RGB").resize((W, H)), (10 + (i % 2) * (W + 10), 10 + (i // 2) * (H + 20)))
    p = f"{sys.argv[1]}/sheet-{g // 6 + 1}.png"
    sheet.save(p)
    print(p)
EOF
ls "$out"/*.png | grep -vc sheet- | xargs echo "slides rendered:"
