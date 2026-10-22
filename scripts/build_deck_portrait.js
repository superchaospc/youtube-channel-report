#!/usr/bin/env node
// Build a 9:16 portrait .pptx (7.5 × 13.333 in, plays full-screen on a vertical screen / phone)
// from the same deck.json that build_deck.js uses. Every slide type is re-laid out top-to-bottom.
//
//   NODE_PATH=~/.cache/ycr-node/node_modules node build_deck_portrait.js deck.json out.pptx
//
// Optional per-slide overrides for portrait only: put them under "portrait": {...} on a slide
// (e.g. {"portrait": {"columns": [...], "rows": [...]}} to drop table columns) — they are merged
// over the slide before rendering. "portrait": false skips the slide.
const fs = require("fs");
const path = require("path");

let pptxgen, JSZip;
try {
  pptxgen = require("pptxgenjs");
  try { JSZip = require("jszip"); } catch { JSZip = require(require.resolve("jszip", { paths: [path.dirname(require.resolve("pptxgenjs"))] })); }
} catch {
  console.error("pptxgenjs not found. Install once:\n  npm install --prefix ~/.cache/ycr-node pptxgenjs@3.12.0\nthen run with NODE_PATH=~/.cache/ycr-node/node_modules");
  process.exit(2);
}

const [deckPath, outPath] = process.argv.slice(2);
if (!deckPath || !outPath) { console.error("usage: build_deck_portrait.js deck.json out.pptx"); process.exit(1); }
const deck = JSON.parse(fs.readFileSync(deckPath, "utf8"));
const meta = deck.meta || {};
const HEAD = (meta.fonts && meta.fonts.head) || "Songti SC";
const BODY = (meta.fonts && meta.fonts.body) || "PingFang SC";
const PALETTE = { dk1: "1E2230", lt1: "F7F4EE", dk2: "4C5262", lt2: "EDE7DC", accent1: "C2412D", accent2: "B8AD9A",
  accent3: "5F6370", accent4: "C9CCD6", accent5: "2F5D8A", accent6: "E8A894", hlink: "C2412D", folHlink: "2F5D8A" };

const pres = new pptxgen();
pres.defineLayout({ name: "PORTRAIT_9x16", width: 7.5, height: 13.333 });
pres.layout = "PORTRAIT_9x16";
pres.theme = { headFontFace: HEAD, bodyFontFace: BODY };
pres.title = meta.title || "";
const C = pres.SchemeColor;
const NAMED = { ink: C.text1, paper: C.background1, paper2: C.background2, sub: C.text2, accent: C.accent1, muted: C.accent2,
  gray: C.accent3, soft: C.accent4, blue: C.accent5, accentLight: C.accent6, lightBlue: "9DB7D5", rule: "D8D0C2", tint: "E3D9CB" };
const col = (c, dflt) => (c ? NAMED[c] || c.replace("#", "") : dflt);
// Facecam mode (talk decks): the presenter's own landscape video fills the whole bottom of the screen,
// at 16:9 (full width × 4.22 in, about the lower 32%; meta.facecam_ratio overrides), so nothing is drawn there — no footer, no page
// number. Wider side margins and a lower top edge keep text clear of the TikTok / 抖音 overlay (status
// bar, back / search icons, the like / comment column on the right). Type is scaled down to fit the
// shorter content area and small print goes to the speaker notes. A slide can carry "video": {...}
// overrides (merged after "portrait") to trim text for this version only.
const FACECAM = !process.argv.includes("--no-facecam") && (!!meta.facecam || process.argv.includes("--facecam"));
const SW = 7.5, SH = 13.333, MX = FACECAM ? 0.85 : 0.5, CW = SW - 2 * MX, GAP = 0.2, FOOT_Y = 12.75;
const CAM_RATIO = meta.facecam_ratio || 16 / 9, CAM_H = SW / CAM_RATIO, CAM_TOP = SH - CAM_H, TOP = FACECAM ? 1.62 : 0.85;
// Video version: the top of the screen belongs to the phone and 抖音 — status bar (clock, Dynamic
// Island, signal / battery) down to ~0.92 in, then the back arrow and search icon centred 1.26 in down
// at the two edges (measured on an iPhone 16 Pro Max; 抖音 fills the screen by height and crops ~0.37 in
// off each side). Nothing goes in the status bar. The row between the arrow and the magnifier works
// like an app's nav bar: the eyebrow sits there, centred (NAV_*), and the title starts right below it.
const NAV_Y = 1.26, NAV_X = 1.15, NAV_W = SW - 2 * NAV_X;
function navLabel(s, text) {
  txt(s, text || "", { x: NAV_X, y: NAV_Y - 0.2, w: NAV_W, h: 0.4, fontSize: 14 / SCALE, bold: true, color: C.accent1, charSpacing: 1, align: "center", valign: "middle", fit: "shrink" });
}
const BOTTOM = FACECAM ? CAM_TOP - 0.35 : 12.45, BASE_SCALE = FACECAM ? 0.86 : 1;
// Type scale. The video version picks it per page: the largest step that still fits (see FIT_SCALES).
let SCALE = BASE_SCALE;
const FIT_SCALES = [1.4, 1.35, 1.3, 1.25, 1.2, 1.15, 1.1, 1.05, 1.0, 0.96, 0.92, 0.89, 0.86];
// Pages whose boxes have fixed heights (stat tiles, gear rows, charts, panels) only grow to 1.1, or
// their text would spill out of the boxes; pages whose blocks grow with the text can go to 1.4.
const FIXED_TYPES = ["cover", "gear", "monthly", "stacked_columns", "topic_bars", "panels", "numbered"];
const maxScale = (d) => (FIXED_TYPES.includes(d.type) || (d.tiles && d.tiles.length) ? 1.1 : 1.4);
const RX = MX;
const warnings = [];

function master(name, bg) {
  pres.defineSlideMaster({
    title: name,
    background: { color: bg },
    objects: FACECAM ? [] : [{ text: { text: meta.footer || meta.title || "", options: { x: RX, y: FOOT_Y, w: SW - MX - RX - 0.8, h: 0.3, fontFace: BODY, fontSize: 10, color: C.accent3, margin: 0, valign: "middle", fit: "shrink" } } }],
    ...(FACECAM ? {} : { slideNumber: { x: SW - MX - 0.7, y: FOOT_Y, w: 0.7, h: 0.3, fontFace: BODY, fontSize: 11, color: PALETTE.accent3, align: "right" } }),
  });
}
master("P_LIGHT", C.background1);
master("P_ALT", C.background2);
pres.defineSlideMaster({ title: "P_COVER", background: { color: C.background1 }, objects: [] });

// ---------------------------------------------------------------- helpers
const isCJK = (ch) => /[　-鿿＀-￯]/.test(ch);
const widthPt = (s, size) => [...String(s)].reduce((a, ch) => a + (isCJK(ch) ? size : size * 0.55), 0);
// Estimated wrapped line count for a box w inches wide.
const lines = (s, size, w) => String(s || "").split("\n").reduce((a, l) => a + Math.max(1, Math.ceil(widthPt(l, size * SCALE) / (w * 72 * 0.95))), 0);
const textH = (s, size, w, ls = 1.2) => (lines(s, size, w) * size * SCALE * ls * 1.08) / 72;
let slideNo = 0;
function txt(s, text, o) {
  o = Object.assign({}, o, { fontSize: Math.round((o.fontSize || 16) * SCALE * 2) / 2 });
  const size = o.fontSize;
  if (typeof text === "string" && !o.wrap && !text.includes("\n") && widthPt(text, size) > o.w * 72 * 0.98)
    warnings.push(`slide ${slideNo}: "${text.slice(0, 30)}…" may not fit on one line (${widthPt(text, size).toFixed(0)}pt > ${(o.w * 72).toFixed(0)}pt)`);
  const opts = Object.assign({ isTextBox: true, margin: 0, fontFace: BODY, valign: "top" }, o);
  delete opts.wrap;
  s.addText(text, opts);
}
const box = (s, x, y, w, h, fill, name, kind) => {
  const k = kind || pres.shapes.ROUNDED_RECTANGLE;
  s.addShape(k, Object.assign({ x, y, w, h, fill: { color: fill }, line: { color: fill, width: 0 }, objectName: name }, k === pres.shapes.ROUNDED_RECTANGLE ? { rectRadius: 0.1 } : {}));
};
const rect = (s, x, y, w, h, fill, name) => box(s, x, y, w, h, fill, name, pres.shapes.RECTANGLE);
const oval = (s, x, y, d, n, name) => {
  s.addShape(pres.shapes.OVAL, { x, y, w: d, h: d, fill: { color: C.accent1 }, line: { color: C.accent1, width: 0 }, objectName: name });
  txt(s, String(n), { x, y, w: d, h: d, fontSize: 15, bold: true, color: C.background1, align: "center", valign: "middle" });
};
const th = (t, al) => ({ text: t, options: { bold: true, fill: { color: C.text1 }, color: C.background1, align: al } });
const bullets = (items) => items.map((t, i) => ({ text: t, options: { bullet: true, breakLine: i < items.length - 1 } }));
const bulletsH = (items, size, w) => items.reduce((a, t) => a + textH(t, size, w - 0.4, 1.3) + 0.14, 0);
let pendingNotes = [];
function note(s, text, y) {
  if (!text) return y;
  // Facecam decks are recorded, not read: small print goes to the speaker notes instead of the slide.
  if (FACECAM) { pendingNotes.push(text); return y; }
  const h = textH(text, 12, CW, 1.2);
  const yy = Math.min(y, BOTTOM - h);
  txt(s, text, { x: MX, y: yy, w: CW, h, fontSize: 12, color: C.text2, wrap: true, lineSpacingMultiple: 1.2 });
  return yy + h;
}
const noteRes = (t, extra = 0.3) => (!t || FACECAM ? 0.1 : textH(t, 12, CW) + extra);
const LIMIT = BOTTOM;
let lastY = 0;
function check(y) { lastY = y; if (y > LIMIT + 0.05) warnings.push(`slide ${slideNo}: content runs to ${y.toFixed(2)} in (bottom ${LIMIT})`); }
// Full-width slot for a stacked item; hOf(w) returns the item's height at width w.
function lane(y, hOf) { return { x: MX, w: CW, h: hOf(CW) }; }
// Dark banner / statement block that grows with its text.
function block(s, text, y, o = {}) {
  const size = o.size || 15, pad = 0.22, { x, w, h } = lane(y, (w) => textH(text, size, w - 0.5, 1.25) + 2 * pad);
  box(s, x, y, w, h, o.fill || C.text1, o.name || "block");
  txt(s, text, { x: x + 0.25, y: y + pad, w: w - 0.5, h: h - 2 * pad, fontSize: size, bold: o.bold !== false, color: o.color || C.background1, valign: "middle", wrap: true, lineSpacingMultiple: 1.25 });
  return y + h;
}

// Extra height per item so stacked cards fill the screen (capped so they never look bloated).
const spread = (heights, T, gap, reserve, cap = 0.6) => Math.max(0, Math.min(FACECAM ? cap * 4 : cap, (BOTTOM - T - reserve - heights.reduce((a, b) => a + b + gap, 0)) / Math.max(heights.length, 1)));

// ---------------------------------------------------------------- slide types
const R = {};

R.cover = (s, d) => {
  const Y0 = FACECAM ? 1.0 : 1.3;
  if (FACECAM) navLabel(s, d.eyebrow);
  else txt(s, d.eyebrow || "", { x: MX, y: Y0, w: CW, h: 0.4, fontSize: 14, bold: true, color: C.accent1, charSpacing: 1, fit: "shrink" });
  const ls = String(d.title || "").split("\n"), TW = CW;
  const fits = (sz) => ls.every((l) => widthPt(l, sz) <= TW * 72 * 0.98);
  const size = d.title_size_portrait || [44, 40, 36, 34, 32, 30, 28].find((z) => fits(z * SCALE)) || 28;
  if (!fits(size)) warnings.push(`slide ${slideNo}: cover title line too wide at ${size}pt`);
  const tH = (ls.length * size * SCALE * 1.3) / 72, TY = Y0 + 1.25;
  rect(s, MX, Y0 + 0.85, 0.9, 0.08, C.accent1, "cover-rule");
  txt(s, d.title || "", { x: MX, y: TY, w: TW, h: tH, fontSize: size, bold: true, fontFace: HEAD, color: C.text1, wrap: true, lineSpacingMultiple: 1.15 });
  let y = TY + tH + 0.35;
  if (d.subtitle) { const h = textH(d.subtitle, 18, CW); txt(s, d.subtitle, { x: MX, y, w: CW, h, fontSize: 18, color: C.text2, wrap: true }); y += h + 0.3; }
  if (d.kpi) {
    y = FACECAM ? y + 0.3 : Math.max(y + 0.4, 6.6);
    box(s, MX, y, CW, 2.7, C.text1, "key-figure");
    txt(s, d.kpi.label || "", { x: MX + 0.4, y: y + 0.35, w: CW - 0.8, h: 0.35, fontSize: 14, color: C.accent4 });
    txt(s, d.kpi.value || "", { x: MX + 0.4, y: y + 0.8, w: CW - 0.8, h: 1.0, fontSize: 54, bold: true, fontFace: HEAD, color: C.background1, valign: "middle" });
    txt(s, d.kpi.sub || "", { x: MX + 0.4, y: y + 1.95, w: CW - 0.8, h: 0.4, fontSize: 17, color: C.accent4 });
  }
  if (d.kpi) y += 2.7;
  txt(s, d.meta || (meta.footer || "").split(" · ").slice(-1)[0] || "", { x: MX, y: FACECAM ? Math.max(y + 0.3, BOTTOM - 0.4) : 12.3, w: CW, h: 0.4, fontSize: 14, color: C.text2 });
  check(FACECAM ? Math.max(y + 0.7, BOTTOM) : 0);
};

// 2-column grid of tiles; returns bottom y.
function tiles2(s, tiles, y, o = {}) {
  const W = (CW - GAP) / 2, H = o.h || 1.9;
  tiles.forEach((t, i) => {
    const x = MX + (i % 2) * (W + GAP), yy = y + Math.floor(i / 2) * (H + GAP), dark = !!t.dark;
    const oy = yy + (H - 1.9) / 2;
    box(s, x, yy, W, H, dark ? C.text1 : o.alt ? C.background1 : C.background2, "tile-" + (i + 1));
    const lab = t.label || "", val = t.value || "", sub = t.desc || t.sub || "";
    const top = o.valueFirst ? [val, lab] : [lab, val];
    if (o.valueFirst) {
      txt(s, val, { x: x + 0.25, y: oy + 0.2, w: W - 0.5, h: 0.7, fontSize: 28, bold: true, fontFace: HEAD, color: dark ? C.background1 : C.text1, valign: "middle", fit: "shrink" });
      txt(s, lab, { x: x + 0.25, y: oy + 0.95, w: W - 0.5, h: 0.35, fontSize: 14, bold: true, color: dark ? C.background1 : C.text1, wrap: true });
    } else {
      txt(s, lab, { x: x + 0.25, y: oy + 0.22, w: W - 0.5, h: 0.35, fontSize: 14, bold: true, color: dark ? C.accent4 : C.text2, wrap: true });
      txt(s, val, { x: x + 0.25, y: oy + 0.62, w: W - 0.5, h: 0.7, fontSize: 28, bold: true, fontFace: HEAD, color: dark ? C.background1 : C.text1, valign: "middle", fit: "shrink" });
    }
    txt(s, sub, { x: x + 0.25, y: oy + 1.38, w: W - 0.5, h: 0.4, fontSize: 12, color: dark ? C.accent4 : C.text2, wrap: true });
    void top;
  });
  return y + Math.ceil(tiles.length / 2) * (H + GAP) - GAP;
}

R.kpis = (s, d, T) => {
  let y = tiles2(s, d.tiles || [], T, { valueFirst: true });
  y += 0.45;
  const fhs = (d.findings || []).map((f) => textH(f.text, 15, CW - 0.5, 1.3) + 0.85), fex = spread(fhs, y, 0.2, 0.1, 0.5);
  (d.findings || []).forEach((f, i) => {
    const { x, w, h: h0 } = lane(y, (w) => textH(f.text, 15, w - 0.5, 1.3) + 0.85), h = h0 + fex;
    box(s, x, y, w, h, d.bg === "alt" ? C.background1 : C.background2, "finding");
    txt(s, f.title, { x: x + 0.25, y: y + 0.2, w: w - 0.5, h: 0.4, fontSize: 17, bold: true, color: C.accent1, fit: "shrink" });
    txt(s, f.text, { x: x + 0.25, y: y + 0.65, w: w - 0.5, h: h - 0.8, fontSize: 15, color: C.text1, wrap: true, lineSpacingMultiple: 1.3 });
    y += h + 0.2;
  });
  check(y);
};

R.rows = (s, d, T) => {
  let y = T;
  const rows = (d.rows || []).slice(0, 6), bg = d.bg === "alt" ? C.background1 : C.background2;
  const hOf = (r) => (w) => 0.75 + textH(r.desc || "", 15, w - 1.05, 1.3) + 0.25;
  const ex = spread(rows.map((r) => hOf(r)(CW)), T, 0.18, noteRes(d.note));
  rows.forEach((r, i) => {
    const { x, w, h: h0 } = lane(y, hOf(r)), h = h0 + ex, c = y + ex / 2, tagW = Math.min(2.2, w * 0.4);
    box(s, x, y, w, h, bg, "row-" + (i + 1));
    oval(s, x + 0.22, c + 0.22, 0.44, (d._n0 || 0) + i + 1, "row-num-" + (i + 1));
    txt(s, r.name, { x: x + 0.85, y: c + 0.2, w: w - 1.1 - tagW, h: 0.48, fontSize: 18, bold: true, color: C.text1, valign: "middle", fit: "shrink" });
    txt(s, r.tag || "", { x: x + w - tagW - 0.2, y: c + 0.2, w: tagW, h: 0.48, fontSize: 15, bold: true, color: C.accent1, valign: "middle", align: "right", fit: "shrink" });
    txt(s, r.desc || "", { x: x + 0.85, y: c + 0.75, w: w - 1.05, h: textH(r.desc || "", 15, w - 1.05, 1.3), fontSize: 15, color: C.text2, wrap: true, lineSpacingMultiple: 1.3 });
    y += h + 0.18;
  });
  check(note(s, d.note, y + 0.1));
};

R.explainer = (s, d, T) => {
  let y = T;
  const ex = (d.example_label || "举例") + "：" + (d.example || "");
  y = block(s, ex, y, { size: 18 }) + 0.3;
  [d.left, d.right].forEach((P, i) => {
    if (!P) return;
    const hOf = (w) => 0.85 + (P.bullets ? bulletsH(P.bullets, 15, w - 0.5) : 0) + (P.chips ? Math.ceil(P.chips.length / 3) * 0.62 : 0) + (P.text ? textH(P.text, 13, w - 0.5) + 0.15 : 0);
    const { x, w, h } = lane(y, hOf);
    box(s, x, y, w, h, C.background2, "panel-" + i);
    txt(s, P.title || "", { x: x + 0.3, y: y + 0.25, w: w - 0.6, h: 0.45, fontSize: 18, bold: true, color: C.accent1 });
    let yy = y + 0.8;
    if (P.bullets) { const bh = bulletsH(P.bullets, 15, w - 0.6); txt(s, bullets(P.bullets), { x: x + 0.3, y: yy, w: w - 0.6, h: bh, fontSize: 15, color: C.text1, paraSpaceAfter: 6, lineSpacingMultiple: 1.2 }); yy += bh; }
    if (P.chips) {
      const cw = (w - 0.6 - 0.3) / 3;
      P.chips.forEach((c, k) => {
        const cx = x + 0.3 + (k % 3) * (cw + 0.15), cy = yy + Math.floor(k / 3) * 0.62;
        box(s, cx, cy, cw, 0.48, C.background1, "chip-" + k);
        txt(s, c, { x: cx, y: cy, w: cw, h: 0.48, fontSize: 13, color: C.text1, align: "center", valign: "middle", fit: "shrink" });
      });
      yy += Math.ceil(P.chips.length / 3) * 0.62;
    }
    if (P.text) txt(s, P.text, { x: x + 0.3, y: yy + 0.1, w: w - 0.6, h: textH(P.text, 13, w - 0.6), fontSize: 13, color: C.text2, wrap: true });
    y += h + 0.25;
  });
  check(y);
};

R.stats4 = (s, d, T) => {
  let y = tiles2(s, (d.tiles || []).slice(0, 4), T, { h: FACECAM ? 2.0 : 2.3 }) + 0.4;
  if (d.bullets && d.bullets.length) {
    const { x, w, h: h0 } = lane(y, (w) => bulletsH(d.bullets, 15, w - 0.6) + 0.45), h = FACECAM ? Math.max(h0, BOTTOM - y - 0.25) : h0;
    box(s, x, y, w, h, d.bg === "alt" ? C.background1 : C.background2, "insight");
    txt(s, bullets(d.bullets), { x: x + 0.3, y: y + 0.22, w: w - 0.6, h: h - 0.4, fontSize: 15, color: C.text1, paraSpaceAfter: 6, lineSpacingMultiple: 1.25, valign: FACECAM ? "middle" : "top" });
    y += h + 0.25;
  }
  check(note(s, d.note, y));
};

R.monthly = (s, d, T) => {
  const t = d.total || {};
  let y = T;
  box(s, MX, y, CW, 3.0, C.text1, "monthly-total");
  txt(s, t.label || "", { x: MX + 0.4, y: y + 0.35, w: CW - 0.8, h: 0.35, fontSize: 15, color: C.accent4 });
  txt(s, t.value || "", { x: MX + 0.4, y: y + 0.8, w: CW - 0.8, h: 1.0, fontSize: 48, bold: true, fontFace: HEAD, color: C.background1, valign: "middle" });
  txt(s, t.sub || "", { x: MX + 0.4, y: y + 1.85, w: CW - 0.8, h: 0.4, fontSize: 18, color: C.background1 });
  txt(s, t.caption || "", { x: MX + 0.4, y: y + 2.4, w: CW - 0.8, h: 0.35, fontSize: 13, color: C.accent4 });
  y += 3.3;
  const items = (d.items || []).slice(0, 4), maxShare = Math.max(...items.map((x) => x.share || 0), 0.0001);
  items.forEach((it, i) => {
    box(s, MX, y, CW, 1.15, d.bg === "alt" ? C.background1 : C.background2, "monthly-" + i);
    txt(s, it.label, { x: MX + 0.3, y: y + 0.18, w: CW - 0.6, h: 0.35, fontSize: 16, bold: true, color: C.text1 });
    txt(s, it.value || "", { x: MX + 0.3, y: y + 0.6, w: 2.6, h: 0.4, fontSize: 18, bold: true, fontFace: HEAD, color: C.text1, valign: "middle" });
    const bw = ((it.share || 0) / maxShare) * (CW - 4.3);
    rect(s, MX + 3.0, y + 0.7, Math.max(bw, 0.05), 0.22, col(it.color, C.accent1), "mbar-" + i);
    txt(s, ((it.share || 0) * 100).toFixed(1) + "%", { x: MX + 3.1 + bw, y: y + 0.6, w: 0.9, h: 0.4, fontSize: 13, color: C.text2, valign: "middle" });
    y += 1.3;
  });
  check(note(s, d.note, y + 0.1));
};

R.table = (s, d, T) => {
  const cols = d.columns || [], rows = d.rows || [];
  const fs_ = d.font_size_portrait || (cols.length >= 4 ? 15 : 16), widths = cols.map((c) => (c.width || 1 / cols.length) * CW);
  // Row height from the tallest wrapped cell.
  const rh = (r) => Math.max(d.row_h_portrait || 0.56, ...r.map((t, j) => textH(String(t), fs_, widths[j] - 0.2, 1.15) + 0.14));
  const hdrH = Math.max(0.5, ...cols.map((c, j) => textH(c.label, fs_, widths[j] - 0.2, 1.15) + 0.14));
  let heights = rows.map(rh);
  // Spread rows over the free height so a short table does not leave half the screen empty.
  const noteH = FACECAM ? 0 : (d.note ? textH(d.note, 12, CW) + 0.2 : 0), avail = BOTTOM - T - 0.3 - noteH, natural = hdrH + heights.reduce((a, b) => a + b, 0);
  if (natural < avail * 0.8) { const f = Math.min((avail * 0.85) / natural, 1.7); heights = heights.map((h) => h * f); }
  const body = rows.map((r, i) => r.map((t, j) => ({ text: String(t), options: Object.assign({ align: (cols[j] || {}).align || "left" },
    (i % 2 || (d.total_row && i === rows.length - 1)) ? { fill: { color: C.background2 } } : {},
    (d.total_row && i === rows.length - 1) || j === d.bold_col ? { bold: true } : {}) })));
  s.addTable([cols.map((c) => th(c.label, c.align || "left"))].concat(body), { x: MX, y: T, w: CW, colW: widths, rowH: [hdrH].concat(heights), fontSize: Math.round(fs_ * SCALE), fontFace: BODY, color: C.text1,
    valign: "middle", margin: [0.04, 0.08, 0.04, 0.08], border: { type: "solid", pt: 0.5, color: NAMED.rule }, objectName: "table" });
  const y = T + hdrH + heights.reduce((a, b) => a + b, 0) + 0.2;
  check(note(s, d.note, y));
};

R.topic_bars = (s, d, T) => {
  let y = T;
  const nItems = [d.left, d.right].reduce((a, p) => a + (p ? Math.min((p.items || []).length, 6) : 0), 0), nPanels = [d.left, d.right].filter(Boolean).length;
  const insH = d.insight ? textH(d.insight, 15, CW - 0.5, 1.25) + 0.64 : 0;
  const pitch = Math.min(0.85, Math.max(0.58, (BOTTOM - T - insH - 0.5 - nPanels * 0.9) / Math.max(nItems, 1)));
  [d.left, d.right].forEach((panel, pi) => {
    if (!panel) return;
    const items = (panel.items || []).slice(0, 6), max = Math.max(...items.map((x) => x.value || 0), 1);
    const t = lane(y, () => 0.5);
    txt(s, panel.title || "", { x: t.x, y, w: t.w, h: 0.42, fontSize: 17, bold: true, color: C.text1, fit: "shrink" });
    y += 0.55;
    items.forEach((it, i) => {
      const { x, w } = lane(y, () => pitch), LW = Math.min(2.55, w * 0.42), BW = w - LW - 1.85;
      txt(s, it.label, { x, y, w: LW - 0.1, h: 0.5, fontSize: 15, color: C.text1, valign: "middle", fit: "shrink" });
      const bw = ((it.value || 0) / max) * BW;
      const c = pi === 0 ? (it.highlight ? C.accent1 : C.accent2) : (i === 0 ? C.accent5 : NAMED.lightBlue);
      rect(s, x + LW, y + 0.12, Math.max(bw, 0.04), 0.26, c, `bar-${pi}-${i}`);
      txt(s, it.text || "", { x: x + LW + bw + 0.1, y, w: w - LW - bw - 0.1, h: 0.5, fontSize: 14, bold: true, color: C.text1, valign: "middle", fit: "shrink" });
      y += pitch;
    });
    y += FACECAM ? 0.2 : 0.35;
  });
  if (d.insight) y = block(s, d.insight, y, { size: 15, bold: false, fill: d.bg === "alt" ? C.background1 : C.background2, color: C.text1, name: "insight" }) + 0.2;
  check(note(s, d.note, y));
};

R.stacked_columns = (s, d, T) => {
  const series = d.series || [], cats = d.categories || [], vals = d.values || [];
  series.forEach((se, i) => {
    const x = MX + i * 3.0;
    rect(s, x, T + 0.07, 0.22, 0.22, col(se.color, C.accent1), "legend-" + i);
    txt(s, se.label, { x: x + 0.32, y: T, w: 2.6, h: 0.36, fontSize: 14, color: C.text1, valign: "middle" });
  });
  const totals = vals.map((r) => r.reduce((a, b) => a + b, 0)), maxT = Math.max(...totals, 1);
  const BASE = BOTTOM - (FACECAM ? 0.55 : 1.6), HMAX = BASE - T - 1.2, pitch = CW / Math.max(cats.length, 1), bw = Math.min(0.6, pitch * 0.62);
  const fsz = cats.length > 16 ? 10 : 13, every = Math.ceil(cats.length / 7);
  cats.forEach((m, i) => {
    const cx = MX + i * pitch, x = cx + (pitch - bw) / 2;
    let y = BASE;
    (vals[i] || []).forEach((c, k) => {
      if (!c) return;
      const h = (c / maxT) * HMAX; y -= h;
      rect(s, x, y, bw, h, col((series[k] || {}).color, C.accent1), `col-${i}-${k}`);
    });
    if (totals[i] >= maxT * 0.03 || cats.length <= 16) txt(s, String(totals[i]), { x: cx - 0.25, y: y - 0.3, w: pitch + 0.5, h: 0.28, fontSize: fsz, bold: true, color: C.text1, align: "center", valign: "bottom" });
    if (i % every === 0) txt(s, m, { x: cx - 0.35, y: BASE + 0.08, w: pitch + 0.7, h: 0.3, fontSize: 12, color: C.text1, align: "center" });
  });
  rect(s, MX, BASE, CW, 0.015, C.accent3, "axis");
  check(note(s, d.note, BASE + 0.6));
};

R.three_cols = (s, d, T) => {
  let y = T;
  const cs = (d.cols || []).slice(0, 3), hOf = (c) => (w) => 0.8 + bulletsH(c.bullets || [], 15, w - 0.6) + 0.25;
  const cex = spread(cs.map((c) => hOf(c)(CW)), T, 0.25, d.banner ? 1.2 : 0.1, 1.2);
  cs.forEach((c, i) => {
    const dark = !!c.dark, { x, w, h: h0 } = lane(y, hOf(c)), h = h0 + cex, bh = bulletsH(c.bullets || [], 15, w - 0.6);
    box(s, x, y, w, h, dark ? C.text1 : C.background2, "col-" + i);
    txt(s, c.title || "", { x: x + 0.3, y: y + 0.22, w: w - 0.6, h: 0.42, fontSize: 18, bold: true, color: dark ? C.background1 : C.accent1 });
    txt(s, bullets(c.bullets || []), { x: x + 0.3, y: y + 0.75, w: w - 0.6, h: bh, fontSize: 15, color: dark ? C.background1 : C.text1, paraSpaceAfter: 6, lineSpacingMultiple: 1.2 });
    y += h + 0.25;
  });
  if (d.banner) y = block(s, d.banner, y, { fill: C.accent1 }) + 0.2;
  check(y);
};

R.lessons = (s, d, T) => {
  let y = T;
  const hd = d.headers || ["要点", "怎么做", "数据佐证"], rows = (d.rows || []).slice(0, 5), bg = d.bg === "alt" ? C.background1 : C.background2;
  const ev = (r) => (hd[2] ? hd[2] + "：" : "") + (r.evidence || "");
  const hOf = (r) => (w) => 0.7 + textH(r.how || "", 15, w - 1.05, 1.25) + textH(ev(r), 13, w - 1.05, 1.2) + 0.3;
  const ex = spread(rows.map((r) => hOf(r)(CW)), T, 0.18, noteRes(d.note));
  rows.forEach((r, i) => {
    const { x, w, h: h0 } = lane(y, hOf(r)), h = h0 + ex, c = y + ex / 2, hh = textH(r.how || "", 15, w - 1.05, 1.25);
    box(s, x, y, w, h, bg, "lesson-" + i);
    oval(s, x + 0.22, c + 0.2, 0.44, (d._n0 || 0) + i + 1, "lesson-num-" + i);
    txt(s, r.title, { x: x + 0.85, y: c + 0.18, w: w - 1.05, h: 0.48, fontSize: 18, bold: true, color: C.text1, valign: "middle", fit: "shrink" });
    txt(s, r.how || "", { x: x + 0.85, y: c + 0.7, w: w - 1.05, h: hh, fontSize: 15, color: C.text1, wrap: true, lineSpacingMultiple: 1.25 });
    txt(s, ev(r), { x: x + 0.85, y: c + 0.78 + hh, w: w - 1.05, h: textH(ev(r), 13, w - 1.05, 1.2), fontSize: 13, color: C.accent1, wrap: true });
    y += h + 0.18;
  });
  check(note(s, d.note, y + 0.05));
};

R.cards = (s, d, T) => {
  let y = T;
  if (d.statement) y = block(s, d.statement, y, { size: 16 }) + 0.3;
  else if (d.lead) { const h = textH(d.lead, 13, CW); txt(s, d.lead, { x: MX, y, w: CW, h, fontSize: 13, color: C.text2, wrap: true }); y += h + 0.2; }
  const cards = d.cards || [], ncol = d._ncol || (cards.length === 4 || cards.length > 5 ? 2 : 1), g = 0.2;
  const bodySize = ncol === 2 ? 15 : 16;
  const cardH = (c, W) => 0.25 + (c.num ? 0.4 : 0) + textH(c.title || "", 17, W - 0.5, 1.15) + 0.12 + textH(c.body || "", bodySize, W - 0.5, 1.3) + (c.note ? textH(c.note, 12, W - 0.5) + 0.2 : 0) + 0.25;
  const rowH = (rc) => (tw) => Math.max(...rc.map((c) => cardH(c, (tw - (ncol - 1) * g) / ncol)));
  const rowsC = [];
  for (let r = 0; r * ncol < cards.length; r++) rowsC.push(cards.slice(r * ncol, r * ncol + ncol));
  const banH = d.banner ? textH(d.banner, 15, CW - 0.5, 1.25) + 0.74 : 0, cex = spread(rowsC.map((rc) => rowH(rc)(CW)), y, g, banH + (noteRes(d.note)), 1.0);
  rowsC.forEach((rowCards, r) => {
    const L = lane(y, rowH(rowCards)), H = L.h + cex, W = (L.w - (ncol - 1) * g) / ncol;
    rowCards.forEach((c, k) => {
      const x = L.x + k * (W + g), dark = !!c.dark;
      box(s, x, y, W, H, dark ? C.text1 : col(c.fill, d.bg === "alt" ? C.background1 : C.background2), "card-" + (r * ncol + k));
      let yy = y + 0.22;
      if (c.num) { txt(s, String(c.num), { x: x + 0.25, y: yy, w: W - 0.5, h: 0.36, fontSize: 18, bold: true, fontFace: HEAD, color: C.accent1 }); yy += 0.4; }
      const th_ = textH(c.title || "", 17, W - 0.5, 1.15);
      txt(s, c.title || "", { x: x + 0.25, y: yy, w: W - 0.5, h: th_, fontSize: 17, bold: true, color: dark ? C.accent6 : C.text1, wrap: true });
      yy += th_ + 0.12;
      const bh = textH(c.body || "", bodySize, W - 0.5, 1.3);
      if (c.body) txt(s, c.body, { x: x + 0.25, y: yy, w: W - 0.5, h: bh, fontSize: bodySize, color: dark ? C.background1 : C.text1, wrap: true, lineSpacingMultiple: 1.3 });
      if (c.note) { const nh = textH(c.note, 12, W - 0.5); txt(s, c.note, { x: x + 0.25, y: y + H - nh - 0.22, w: W - 0.5, h: nh, fontSize: 12, color: dark ? C.accent4 : C.accent1, wrap: true }); }
    });
    y += H + g;
  });
  if (d.banner) y = block(s, d.banner, y + 0.1, { size: 15, bold: false, fill: d.bg === "alt" ? C.background1 : C.background2, color: C.text1, name: "banner" }) + 0.2;
  check(note(s, d.note, y));
};

R.numbered = (s, d, T) => {
  let y = T;
  const items = (d.items || []).slice(0, 5), bg = d.bg === "alt" ? C.background1 : C.background2;
  const hOf = (it) => (w) => 0.9 + textH(it.body || "", 15, w - 1.35, 1.3) + 0.2;
  const banH = d.banner ? textH(d.banner, 15, CW - 0.5, 1.25) + 0.64 : 0, ex = spread(items.map((it) => hOf(it)(CW)), T, 0.2, banH + 0.3);
  items.forEach((it, i) => {
    const { x, w, h: h0 } = lane(y, hOf(it)), h = h0 + ex, c = y + ex / 2;
    box(s, x, y, w, h, bg, "item-" + i);
    txt(s, String((d._n0 || 0) + i + 1), { x: x + 0.3, y: c + 0.2, w: 0.7, h: 0.7, fontSize: 40, bold: true, fontFace: HEAD, color: C.accent1, valign: "middle" });
    txt(s, it.title, { x: x + 1.1, y: c + 0.28, w: w - 1.35, h: 0.5, fontSize: 19, bold: true, color: C.text1, fit: "shrink" });
    txt(s, it.body || "", { x: x + 1.1, y: c + 0.85, w: w - 1.35, h: textH(it.body || "", 15, w - 1.35, 1.3), fontSize: 15, color: C.text2, wrap: true, lineSpacingMultiple: 1.3 });
    y += h + 0.2;
  });
  if (d.banner) y = block(s, d.banner, y + 0.1, { size: 15 }) + 0.2;
  check(y);
};

R.panels = (s, d, T) => {
  let y = T;
  (d.panels || []).slice(0, 2).forEach((p, i) => {
    const dark = !!p.dark, { x, w, h } = lane(y, (w) => 2.0 + textH(p.sub || "", 14, w - 0.7) + 0.2);
    box(s, x, y, w, h, dark ? C.text1 : d.bg === "alt" ? C.background1 : C.background2, "panel-" + i);
    txt(s, p.title || "", { x: x + 0.35, y: y + 0.25, w: w - 0.7, h: 0.42, fontSize: 17, bold: true, color: dark ? C.accent6 : C.accent1, fit: "shrink" });
    txt(s, p.big || "", { x: x + 0.35, y: y + 0.75, w: w - 0.7, h: 0.75, fontSize: 40, bold: true, fontFace: HEAD, color: dark ? C.background1 : C.text1, valign: "middle" });
    txt(s, p.line || "", { x: x + 0.35, y: y + 1.5, w: w - 0.7, h: 0.4, fontSize: 15, bold: true, color: dark ? C.background1 : C.text1, fit: "shrink" });
    txt(s, p.sub || "", { x: x + 0.35, y: y + 1.95, w: w - 0.7, h: textH(p.sub || "", 14, w - 0.7), fontSize: 14, color: dark ? C.accent4 : C.text2, wrap: true });
    y += h + 0.22;
  });
  if (d.box) {
    const { x, w, h } = lane(y, (w) => 0.85 + textH(d.box.text || "", 15, w - 0.7, 1.3) + 0.2);
    box(s, x, y, w, h, d.bg === "alt" ? C.background1 : C.background2, "panel-box");
    txt(s, d.box.title || "", { x: x + 0.35, y: y + 0.22, w: w - 0.7, h: 0.4, fontSize: 16, bold: true, color: C.accent1 });
    txt(s, d.box.text || "", { x: x + 0.35, y: y + 0.7, w: w - 0.7, h: h - 0.9, fontSize: 15, color: C.text1, wrap: true, lineSpacingMultiple: 1.3 });
    y += h + 0.2;
  }
  check(note(s, d.note, y));
};

R.gear = (s, d, T) => {
  let y = T;
  const style = (d.style || []).slice(0, 6), total = d.frames || style.reduce((a, x) => a + x.count, 0) || 1, max = Math.max(...style.map((x) => x.count), 1);
  if (style.length) { txt(s, d.style_title || `拍摄方式（${total} 张截帧统计）`, { x: MX, y, w: CW, h: 0.42, fontSize: 17, bold: true, color: C.text1 }); y += 0.55; }
  const sp = FACECAM && !(d.items && d.items.length) && style.length ? Math.min(0.95, Math.max(0.5, (BOTTOM - y - 0.7) / style.length)) : 0.5;
  style.forEach((x, i) => {
    const bw = (x.count / max) * Math.min(2.4, CW - 3.9);
    txt(s, x.label, { x: MX, y, w: 2.4, h: 0.5, fontSize: 15, color: C.text1, valign: "middle", fit: "shrink" });
    const bh = Math.max(0.24, Math.min(0.42, sp * 0.45));
    rect(s, MX + 2.5, y + 0.25 - bh / 2, Math.max(bw, 0.04), bh, i === 0 ? C.accent1 : C.accent2, "style-" + i);
    txt(s, `${x.count} 张 · ${Math.round((x.count / total) * 100)}%`, { x: MX + 2.6 + bw, y, w: CW - 2.6 - bw, h: 0.5, fontSize: 14, bold: true, color: C.text1, valign: "middle" });
    y += sp;
  });
  if (d.specs) { txt(s, "画质：" + d.specs, { x: MX, y: y + 0.05, w: CW, h: 0.4, fontSize: 13, color: C.text2 }); y += 0.55; }
  if (d.items && d.items.length) {
    if (style.length) y += 0.25;
    txt(s, d.items_title || "器材推断", { x: MX, y, w: CW, h: 0.42, fontSize: 17, bold: true, color: C.text1 });
    y += 0.55;
  }
  (d.items || []).slice(0, 5).forEach((it, i) => {
    const sure = /证据|确认|confirmed/i.test(it.level || ""), { x, w } = lane(y, () => 0.86);
    box(s, x, y, w, 0.86, d.bg === "alt" ? C.background1 : C.background2, "gear-" + i);
    txt(s, it.category || "", { x: x + 0.25, y: y + 0.12, w: 1.0, h: 0.4, fontSize: 14, bold: true, color: C.accent1, valign: "middle" });
    txt(s, it.name || "", { x: x + 1.25, y: y + 0.12, w: w - 2.45, h: 0.4, fontSize: 15, bold: true, color: C.text1, valign: "middle", fit: "shrink" });
    txt(s, it.basis || "", { x: x + 1.25, y: y + 0.5, w: w - 1.5, h: 0.35, fontSize: 13, color: C.text2, fit: "shrink" });
    box(s, x + w - 1.05, y + 0.15, 0.85, 0.34, sure ? C.accent1 : C.accent2, "level-" + i);
    txt(s, it.level || "推断", { x: x + w - 1.05, y: y + 0.15, w: 0.85, h: 0.34, fontSize: 12, bold: true, color: C.background1, align: "center", valign: "middle" });
    y += 0.94;
  });
  if (d.summary) y = block(s, d.summary, y + 0.15, { size: 15, bold: false }) + 0.2;
  check(note(s, d.summary ? null : d.note, y));
};

R.images = (s, d, T) => {
  let y = T;
  if (d.statement) y = block(s, d.statement, y, { size: 15 }) + 0.25;
  const imgs = (d.images || []).slice(0, 3), capH = 0.42, base = path.dirname(path.resolve(deckPath));
  const bannerH = d.banner ? textH(d.banner, 15, CW - 0.5, 1.25) + 0.64 : 0;
  const avail = BOTTOM - y - (d.banner ? bannerH + 0.3 : noteRes(d.note)) - (imgs.length - 1) * 0.25;
  imgs.forEach((im, i) => {
    const r = im.ratio || 16 / 9, slotH = avail / imgs.length - (im.caption ? capH : 0);
    let w = CW, h = w / r;
    if (h > slotH) { h = slotH; w = h * r; }
    if (FACECAM && w < CW * 0.68) warnings.push(`slide ${slideNo}: image shrunk to ${w.toFixed(2)} in wide, may not fit`);
    if (im.caption) { txt(s, im.caption, { x: MX, y, w: CW, h: capH - 0.06, fontSize: 15, bold: true, color: im.accent ? C.accent1 : C.text1, valign: "middle", fit: "shrink" }); y += capH; }
    s.addImage({ path: path.resolve(base, im.path), x: MX + (CW - w) / 2, y, w, h });
    y += h + (FACECAM && i === imgs.length - 1 ? 0 : 0.25);
  });
  if (d.banner) y = block(s, d.banner, y + (FACECAM ? 0.3 : 0.05), { size: 15, bold: false, fill: d.bg === "alt" ? C.background1 : C.background2, color: C.text1, name: "banner" }) + (FACECAM ? 0 : 0.2);
  check(note(s, d.banner ? null : d.note, y));
};

// Break a long title after a punctuation mark so no line ends with an orphan character.
function smartBreak(t, size, w) {
  if (t.includes("\n") || widthPt(t, size) <= w * 72 * 0.95) return t;
  const cs = [...t], lim = w * 72 * 0.95;
  let best = null;
  cs.forEach((ch, i) => {
    if (!/[：，、—；]/.test(ch) || i === cs.length - 1) return;
    const a = cs.slice(0, i + 1).join(""), b = cs.slice(i + 1).join("").trim();
    if (widthPt(a, size) > lim || widthPt(b, size) > lim) return;
    const score = Math.abs(widthPt(a, size) - widthPt(b, size));
    if (!best || score < best.score) best = { score, t: a + "\n" + b };
  });
  return best ? best.t : t;
}

// Types not used often fall back to a readable list of their text fields.
function fallback(s, d, T) {
  const parts = [];
  for (const [k, v] of Object.entries(d)) if (typeof v === "string" && !["type", "title", "eyebrow", "bg", "section", "notes"].includes(k)) parts.push(v);
  const t = parts.join("\n\n");
  txt(s, t, { x: MX, y: T, w: CW, h: BOTTOM - T, fontSize: 15, color: C.text1, wrap: true });
  warnings.push(`slide ${slideNo}: type "${d.type}" has no portrait layout, rendered as plain text`);
}

// ---------------------------------------------------------------- build
function header(s, d) {
  if (FACECAM) {
    navLabel(s, d.eyebrow);
    const ts = (30 * Math.min(SCALE, 1.1)) / SCALE;   // titles stay a steady size while body type grows
    const title = d.title_portrait || smartBreak(d.title || "", ts * SCALE, CW), th_ = textH(title, ts, CW, 1.15);
    if (lines(title, ts, CW) > 2) warnings.push(`slide ${slideNo}: title needs ${lines(title, ts, CW)} lines`);
    txt(s, title, { x: MX, y: TOP, w: CW, h: th_, fontSize: ts, bold: true, fontFace: HEAD, color: C.text1, wrap: true, lineSpacingMultiple: 1.1 });
    return TOP + th_ + 0.35;
  }
  txt(s, d.eyebrow || "", { x: MX, y: TOP, w: CW, h: 0.32, fontSize: 13, bold: true, color: C.accent1, charSpacing: 1, fit: "shrink" });
  const title = d.title_portrait || smartBreak(d.title || "", 30 * SCALE, CW), size = 30, tw = CW;
  const th_ = textH(title, size, tw, 1.15);
  if (lines(title, size, tw) > 2) warnings.push(`slide ${slideNo}: title needs ${lines(title, size, tw)} lines`);
  txt(s, title, { x: MX, y: TOP + 0.4, w: tw, h: th_, fontSize: size, bold: true, fontFace: HEAD, color: C.text1, wrap: true, lineSpacingMultiple: 1.1 });
  return TOP + 0.4 + th_ + 0.45;
}

// Lay a slide out on a throwaway canvas and report whether it stays above the bottom limit.
const NULL_SLIDE = { addText() {}, addShape() {}, addTable() {}, addImage() {}, addNotes() {} };
function fitsPage(d) {
  const w0 = warnings.length, n0 = pendingNotes.length;
  lastY = 0;
  try { (R[d.type] || fallback)(NULL_SLIDE, d, d.type === "cover" ? 0 : header(NULL_SLIDE, d)); } catch { return true; }
  const tooWide = warnings.slice(w0).some((w) => /may not fit|title needs/.test(w));
  warnings.length = w0; pendingNotes.length = n0;
  return lastY <= LIMIT + 0.05 && !tooWide;
}

// Video version: the content area above the facecam band is short, so a slide that overflows is
// split into continuation pages (same title) instead of shrinking the type further. Lead-in fields
// (statement, tiles) stay on the first page; closing ones (banner, insight, note…) on the last.
const SPLIT = { table: "rows", cards: "cards", rows: "rows", lessons: "rows", numbered: "items", three_cols: "cols", panels: "panels", stats4: "bullets", images: "images", kpis: "findings" };
const NUMBERED = { rows: 1, lessons: 1, numbered: 1 };
function paginate(d) {
  if (!FACECAM || fitsPage(d)) return [d];
  if (d.type === "gear") return [Object.assign({}, d, { items: [], summary: null, note: null }), ...paginateList(Object.assign({}, d, { style: [], specs: null }), "items")];
  if (d.type === "topic_bars" && d.left && d.right) return [Object.assign({}, d, { right: null, insight: null, note: null }), Object.assign({}, d, { left: null })];
  return paginateList(d, SPLIT[d.type]);
}

function paginateList(d, key) {
  const all = (key && d[key]) || [];
  if (all.length < 2 || fitsPage(d)) return [d];
  // Cards keep the column count of the whole set, so a 2-column grid stays 2 columns on every page.
  const unit = d.type === "cards" && (all.length === 4 || all.length > 5) ? 2 : 1;
  const extra = d.type === "cards" ? { _ncol: unit } : {};
  const mk = (start, k, first = start === 0) => Object.assign({}, d, extra, { [key]: all.slice(start, start + k) },
    first ? {} : { statement: null, lead: null, tiles: [] },
    start + k < all.length ? { banner: null, box: null, insight: null, summary: null, note: null } : {},
    NUMBERED[d.type] ? { _n0: start } : {});
  // Greedy pass finds how many pages are needed; then try spreading the items evenly over that many.
  // The first page may hold only the lead-in (tiles / statement) when even one item would not fit.
  const leadOnly = (d.tiles && d.tiles.length) || d.statement;
  const greedy = [];
  for (let start = 0; start < all.length;) {
    const first = greedy.length === 0;
    let k = all.length - start;
    const min = first && leadOnly ? 0 : unit;
    while (k > min && !fitsPage(mk(start, k, first))) k -= k % unit || unit;
    greedy.push(mk(start, k, first));
    start += k;
  }
  const P = greedy.length, even = Math.ceil(all.length / P / unit) * unit, balanced = [];
  for (let start = 0; start < all.length; start += even) balanced.push(mk(start, Math.min(even, all.length - start)));
  return balanced.length === P && balanced.every(fitsPage) ? balanced : greedy;
}

const hasSections = deck.slides.some((d) => d.section);
let section = null, n = 0;
deck.slides.forEach((d0) => {
  if (d0.portrait === false) return;
  const d1 = Object.assign({}, d0, d0.portrait || {}, (FACECAM && d0.video) || {});
  SCALE = BASE_SCALE;
  paginate(d1).forEach((d) => {
  // Video version: use the largest type that still fits, so a short page is not left half empty;
  // stacked cards and blocks then stretch (spread) over whatever height is left.
  if (FACECAM) SCALE = FIT_SCALES.find((sc) => { SCALE = sc; return sc <= maxScale(d) && fitsPage(d); }) || BASE_SCALE;
  slideNo = ++n;
  if (hasSections && (d.section || !section) && d.section !== section) { section = d.section || "概览"; pres.addSection({ title: section }); }
  const masterName = d.type === "cover" ? "P_COVER" : d.bg === "alt" ? "P_ALT" : "P_LIGHT";
  const s = pres.addSlide(Object.assign({ masterName }, hasSections ? { sectionTitle: section } : {}));
  pendingNotes = [];
  const T = d.type === "cover" ? 0 : header(s, d);
  (R[d.type] || fallback)(s, d, T);
  const allNotes = [d.notes, ...pendingNotes].filter(Boolean).join("\n\n");
  if (allNotes) s.addNotes(allNotes);
  });
});

(async () => {
  await pres.writeFile({ fileName: outPath });
  const zip = await JSZip.loadAsync(fs.readFileSync(outPath));
  const p = "ppt/theme/theme1.xml";
  let xml = await zip.file(p).async("string");
  for (const [k, v] of Object.entries(PALETTE)) xml = xml.replace(new RegExp(`<a:${k}>[\\s\\S]*?</a:${k}>`), `<a:${k}><a:srgbClr val="${v}"/></a:${k}>`);
  const fix = (block_, face) => block_.replace(/<a:ea typeface="[^"]*"\/>/, `<a:ea typeface="${face}"/>`).replace(/<a:font script="Hans" typeface="[^"]*"\/>/, `<a:font script="Hans" typeface="${face}"/>`);
  xml = xml.replace(/<a:majorFont>[\s\S]*?<\/a:majorFont>/, (m) => fix(m, HEAD)).replace(/<a:minorFont>[\s\S]*?<\/a:minorFont>/, (m) => fix(m, BODY));
  zip.file(p, xml);
  fs.writeFileSync(outPath, await zip.generateAsync({ type: "nodebuffer", compression: "DEFLATE" }));
  warnings.forEach((w) => console.warn("WARN " + w));
  console.log(`wrote ${outPath} (${n} slides, 9:16 portrait${FACECAM ? `, bottom ${(CAM_RATIO * 9).toFixed(0)}:9 facecam band kept free` : ""}${warnings.length ? `, ${warnings.length} layout warnings` : ""})`);
})();
