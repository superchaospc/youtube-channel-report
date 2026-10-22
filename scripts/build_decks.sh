#!/usr/bin/env bash
# Build THREE decks from one deck.json — 16:9 landscape, 9:16 portrait reading version, and
# 9:16 portrait video version (whole bottom kept free for the user's 16:9 landscape facecam) — then
# render-check all three with Keynote and export PDFs. This is the default deliverable of the skill.
#
#   build_decks.sh OUT/deck.json WORK_DIR "<标题>"
#
# Writes WORK_DIR/<标题>.pptx (+ .pdf, png/), WORK_DIR/<标题>-竖屏阅读版.pptx (+ .pdf, png-portrait/)
# and WORK_DIR/<标题>-竖屏视频版.pptx (+ .pdf, png-facecam/).
# The reading version ignores meta.facecam; the video version always keeps the bottom band free.
set -euo pipefail
S="$(cd "$(dirname "$0")" && pwd)"
deck="$1"; work="$2"; title="$3"
export NODE_PATH="${NODE_PATH:-$HOME/.cache/ycr-node/node_modules}"
[ -d "$NODE_PATH/pptxgenjs" ] || npm install --prefix "$HOME/.cache/ycr-node" pptxgenjs@3.12.0 >/dev/null
# Decks get posted to 抖音 / 小红书: flag risky wording first (warning only, see references/compliance.md).
python3 "$S/compliance_check.py" "$deck" || echo "COMPLIANCE: fix the flagged wording above in deck.json and rebuild before delivering"
node "$S/build_deck.js" "$deck" "$work/$title.pptx"
node "$S/build_deck_portrait.js" "$deck" "$work/$title-竖屏阅读版.pptx" --no-facecam
node "$S/build_deck_portrait.js" "$deck" "$work/$title-竖屏视频版.pptx" --facecam
# Keynote sometimes loses the freshly opened document on the first AppleScript call; retry once.
render() { "$S/render_check.sh" "$1" "$2" --pdf || { sleep 4; "$S/render_check.sh" "$1" "$2" --pdf; }; }
render "$work/$title.pptx" "$work/png"
render "$work/$title-竖屏阅读版.pptx" "$work/png-portrait"
render "$work/$title-竖屏视频版.pptx" "$work/png-facecam"
# Video version preview with a 16:9 placeholder where the facecam goes (png-facecam/preview/).
python3 "$S/facecam_preview.py" "$work/png-facecam"
echo "landscape: $work/$title.pptx  portrait: $work/$title-竖屏阅读版.pptx  video: $work/$title-竖屏视频版.pptx"
