#!/usr/bin/env bash
# Build BOTH decks from one deck.json — 16:9 landscape and 9:16 portrait — then render-check
# both with Keynote and export PDFs. This is the default deliverable of the skill.
#
#   build_decks.sh OUT/deck.json WORK_DIR "<标题>"
#
# Writes WORK_DIR/<标题>.pptx (+ .pdf, png/) and WORK_DIR/<标题>-竖屏.pptx (+ .pdf, png-portrait/).
set -euo pipefail
S="$(cd "$(dirname "$0")" && pwd)"
deck="$1"; work="$2"; title="$3"
export NODE_PATH="${NODE_PATH:-$HOME/.cache/ycr-node/node_modules}"
[ -d "$NODE_PATH/pptxgenjs" ] || npm install --prefix "$HOME/.cache/ycr-node" pptxgenjs@3.12.0 >/dev/null
node "$S/build_deck.js" "$deck" "$work/$title.pptx"
node "$S/build_deck_portrait.js" "$deck" "$work/$title-竖屏.pptx"
# Keynote sometimes loses the freshly opened document on the first AppleScript call; retry once.
render() { "$S/render_check.sh" "$1" "$2" --pdf || { sleep 4; "$S/render_check.sh" "$1" "$2" --pdf; }; }
render "$work/$title.pptx" "$work/png"
render "$work/$title-竖屏.pptx" "$work/png-portrait"
echo "landscape: $work/$title.pptx  portrait: $work/$title-竖屏.pptx"
