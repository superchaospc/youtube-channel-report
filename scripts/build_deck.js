#!/usr/bin/env node
// Build a 16:9 .pptx from deck.json (slide types: references/deck-json.md).
//
//   npm install --prefix ~/.cache/ycr-node pptxgenjs@3.12.0      # once
//   NODE_PATH=~/.cache/ycr-node/node_modules node build_deck.js deck.json out.pptx
//
// Charts are drawn with shapes, not native PowerPoint charts: Keynote and
// macOS Quick Look render pptxgenjs charts as blank boxes.
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
if (!deckPath || !outPath) { console.error("usage: build_deck.js deck.json out.pptx"); process.exit(1); }
const deck = JSON.parse(fs.readFileSync(deckPath, "utf8"));
const meta = deck.meta || {};
const HEAD = (meta.fonts && meta.fonts.head) || "PingFang SC";   // Apple-style: PingFang for titles too (user rule, 2026-10-23)
const BODY = (meta.fonts && meta.fonts.body) || "PingFang SC";
const PALETTE = { dk1: "1E2230", lt1: "F7F4EE", dk2: "4C5262", lt2: "EDE7DC", accent1: "C2412D", accent2: "B8AD9A",
  accent3: "5F6370", accent4: "C9CCD6", accent5: "2F5D8A", accent6: "E8A894", hlink: "C2412D", folHlink: "2F5D8A" };

const pres = new pptxgen();
pres.layout = "LAYOUT_WIDE";
pres.theme = { headFontFace: HEAD, bodyFontFace: BODY };
pres.title = meta.title || "";
const C = pres.SchemeColor;
const NAMED = { ink: C.text1, paper: C.background1, paper2: C.background2, sub: C.text2, accent: C.accent1, muted: C.accent2,
  gray: C.accent3, soft: C.accent4, blue: C.accent5, accentLight: C.accent6, lightBlue: "9DB7D5", rule: "D8D0C2", tint: "E3D9CB" };
const col = (c, dflt) => (c ? NAMED[c] || c.replace("#", "") : dflt);
const MX = 0.889, CW = 11.556, GAP = 0.222;
const warnings = [];

// ---------------------------------------------------------------- layouts
function contentLayout(name, bg) {
  pres.defineSlideMaster({
    title: name,
    background: { color: bg },
    objects: [
      { text: { text: meta.footer || meta.title || "", options: { x: MX, y: 6.8, w: 8, h: 0.25, fontFace: BODY, fontSize: 12, color: C.accent3, margin: 0, valign: "middle" } } },
      { placeholder: { options: { name: "eyebrow", type: "body", x: MX, y: 0.889, w: CW, h: 0.3, fontFace: BODY, fontSize: 12, bold: true, color: C.accent1, charSpacing: 1, margin: 0, valign: "top" }, text: "" } },
      { placeholder: { options: { name: "title", type: "title", x: MX, y: 1.24, w: CW, h: 0.7, fontFace: HEAD, fontSize: 36, bold: true, color: C.text1, margin: 0, valign: "top", align: "left" }, text: "" } },
    ],
    slideNumber: { x: 11.445, y: 6.8, w: 1.0, h: 0.25, fontFace: BODY, fontSize: 12, color: PALETTE.accent3, align: "right" },
  });
}
contentLayout("CONTENT_LIGHT", C.background1);
contentLayout("CONTENT_ALT", C.background2);
pres.defineSlideMaster({
  title: "COVER",
  background: { color: C.background1 },
  objects: [
    { placeholder: { options: { name: "eyebrow", type: "body", x: MX, y: 0.889, w: CW, h: 0.4, fontFace: BODY, fontSize: 16, bold: true, color: C.accent1, charSpacing: 2, margin: 0, valign: "top" }, text: "" } },
  ],
});

// ---------------------------------------------------------------- helpers
// Rough single-line width (pt): CJK = 1 em, everything else ≈ 0.55 em.
const widthPt = (s, size) => [...String(s)].reduce((a, ch) => a + (/[　-鿿＀-￯]/.test(ch) ? size : size * 0.55), 0);
let slideNo = 0;
function txt(s, text, o) {
  const size = o.fontSize || 18;
  if (typeof text === "string" && !o.wrap && !text.includes("\n") && widthPt(text, size) > o.w * 72 * 0.98)
    warnings.push(`slide ${slideNo}: "${text.slice(0, 30)}…" may not fit on one line (${widthPt(text, size).toFixed(0)}pt > ${(o.w * 72).toFixed(0)}pt)`);
  const opts = Object.assign({ isTextBox: true, margin: 0, fontFace: BODY, valign: "top" }, o);
  delete opts.wrap;
  s.addText(text, opts);
}
const box = (s, x, y, w, h, fill, name, kind) => {
  const k = kind || pres.shapes.ROUNDED_RECTANGLE;
  s.addShape(k, Object.assign({ x, y, w, h, fill: { color: fill }, line: { color: fill, width: 0 }, objectName: name }, k === pres.shapes.ROUNDED_RECTANGLE ? { rectRadius: 0.12 } : {}));
};
const rect = (s, x, y, w, h, fill, name) => box(s, x, y, w, h, fill, name, pres.shapes.RECTANGLE);
const note = (s, text, y) => text && txt(s, text, { x: MX, y, w: CW, h: 0.5, fontSize: 13, color: C.text2, wrap: true, lineSpacingMultiple: 1.15 });
const th = (t, al) => ({ text: t, options: { bold: true, fill: { color: C.text1 }, color: C.background1, align: al } });
const bullets = (items, o) => items.map((t, i) => ({ text: t, options: { bullet: true, breakLine: i < items.length - 1 } }));
const oval = (s, x, y, d, n, name) => {
  s.addShape(pres.shapes.OVAL, { x, y, w: d, h: d, fill: { color: C.accent1 }, line: { color: C.accent1, width: 0 }, objectName: name });
  txt(s, String(n), { x, y, w: d, h: d, fontSize: 15, bold: true, color: C.background1, align: "center", valign: "middle" });
};

// ---------------------------------------------------------------- slide types
const R = {};

R.cover = (s, d) => {
  s.addText(d.eyebrow || "", { placeholder: "eyebrow" });
  // The cover title is a plain text box, not the title placeholder: pptxgenjs drops size and position
  // overrides on placeholders, and Keynote silently shrinks overflowing placeholder text while
  // PowerPoint does not, so a long title looked fine in the render check but spilled in PowerPoint.
  // The size is the largest that fits every line on one line (or title_size), bottom-aligned above the subtitle.
  const lines = String(d.title || "").split("\n"), TW = 7.6;
  // Also cap the block height: it grows upward from y=3.6 and must stay below the eyebrow (~1.4 in).
  const fits = (sz) => lines.every((l) => widthPt(l, sz) <= TW * 72 * 0.98) && (lines.length * sz * 1.2) / 72 <= 1.95;
  const size = d.title_size || [54, 48, 44, 40, 36, 32, 30, 28].find(fits) || 28;
  if (!fits(size)) warnings.push(`slide ${slideNo}: cover title line too wide at ${size}pt`);
  const th = (lines.length * size * 1.2) / 72;
  txt(s, d.title || "", { x: MX, y: 3.6 - th, w: TW, h: th, fontSize: size, bold: true, fontFace: HEAD, color: C.text1, valign: "bottom", wrap: true });
  if (d.subtitle) txt(s, d.subtitle, { x: MX, y: 3.75, w: 7.2, h: 0.9, fontSize: 20, color: C.text2, wrap: true, lineSpacingMultiple: 1.2 });
  if (d.kpi) {
    box(s, 8.75, 2.45, 3.695, 2.4, C.text1, "key-figure");
    txt(s, d.kpi.label || "", { x: 9.1, y: 2.75, w: 3.1, h: 0.3, fontSize: 12, color: C.accent4 });
    txt(s, d.kpi.value || "", { x: 9.1, y: 3.1, w: 3.1, h: 0.95, fontSize: 44, bold: true, fontFace: HEAD, color: C.background1, valign: "middle" });
    txt(s, d.kpi.sub || "", { x: 9.1, y: 4.15, w: 3.1, h: 0.35, fontSize: 16, color: C.accent4 });
  }
  if (d.meta) txt(s, d.meta, { x: MX, y: 6.35, w: CW, h: 0.35, fontSize: 16, color: C.text2 });
};

R.kpis = (s, d) => {
  const tiles = d.tiles || [], n = Math.max(tiles.length, 1), W = (CW - (n - 1) * GAP) / n;
  tiles.forEach((t, i) => {
    const x = MX + i * (W + GAP), y = 2.2, dark = !!t.dark;
    box(s, x, y, W, 1.9, dark ? C.text1 : C.background2, "kpi-" + (i + 1));
    txt(s, t.value, { x: x + 0.3, y: y + 0.25, w: W - 0.6, h: 0.65, fontSize: 28, bold: true, fontFace: HEAD, color: dark ? C.background1 : C.text1, valign: "middle" });
    txt(s, t.label || "", { x: x + 0.3, y: y + 0.98, w: W - 0.6, h: 0.35, fontSize: 14, bold: true, color: dark ? C.background1 : C.text1 });
    txt(s, t.desc || "", { x: x + 0.3, y: y + 1.36, w: W - 0.6, h: 0.42, fontSize: 12, color: dark ? C.accent4 : C.text2, wrap: true });
  });
  const f = d.findings || [], m = Math.max(f.length, 1), FW = (CW - (m - 1) * GAP) / m;
  f.forEach((x, i) => {
    const xx = MX + i * (FW + GAP);
    txt(s, x.title, { x: xx, y: 4.35, w: FW, h: 0.4, fontSize: 16, bold: true, color: C.accent1, wrap: true });
    txt(s, x.text, { x: xx, y: 4.8, w: FW, h: 1.4, fontSize: 14, color: C.text1, wrap: true, lineSpacingMultiple: 1.25 });
  });
};

R.accounts = (s, d) => {
  const a = d.accounts || [], n = Math.max(a.length, 1), W = (CW - (n - 1) * GAP) / n;
  a.forEach((x, i) => {
    const xx = MX + i * (W + GAP), y = 2.2, hot = !!x.highlight;
    box(s, xx, y, W, 4.1, hot ? C.text1 : C.background1, "account-" + (i + 1));
    const fg = hot ? C.background1 : C.text1, sub = hot ? C.accent4 : C.text2;
    txt(s, x.platform || "", { x: xx + 0.25, y: y + 0.3, w: W - 0.5, h: 0.3, fontSize: 12, bold: true, color: hot ? C.accent6 : C.accent1, wrap: true });
    txt(s, x.name || "", { x: xx + 0.25, y: y + 0.65, w: W - 0.5, h: 0.6, fontSize: 16, bold: true, color: fg, wrap: true });
    txt(s, x.value || "", { x: xx + 0.25, y: y + 1.5, w: W - 0.5, h: 0.6, fontSize: 28, bold: true, fontFace: HEAD, color: fg, valign: "middle" });
    txt(s, x.unit || "", { x: xx + 0.25, y: y + 2.12, w: W - 0.5, h: 0.3, fontSize: 12, color: sub });
    txt(s, x.detail || "", { x: xx + 0.25, y: y + 2.65, w: W - 0.5, h: 1.25, fontSize: 12, color: sub, wrap: true, lineSpacingMultiple: 1.3 });
  });
  note(s, d.note, 6.38);
};

R.rows = (s, d) => {
  (d.rows || []).slice(0, 6).forEach((r, i) => {
    const y = 2.15 + i * 0.8;
    box(s, MX, y, CW, 0.68, i % 2 ? C.background1 : C.background2, "row-" + (i + 1));
    oval(s, MX + 0.2, y + 0.12, 0.44, i + 1, "row-num-" + (i + 1));
    txt(s, r.name, { x: MX + 0.85, y, w: 3.6, h: 0.68, fontSize: 16, bold: true, color: C.text1, valign: "middle", wrap: true });
    txt(s, r.desc || "", { x: MX + 4.5, y, w: 4.4, h: 0.68, fontSize: 13, color: C.text2, valign: "middle", wrap: true });
    txt(s, r.tag || "", { x: MX + 9.0, y, w: 2.4, h: 0.68, fontSize: 13, bold: true, color: C.accent1, valign: "middle", align: "right", wrap: true });
  });
  note(s, d.note, 6.25);
};

R.disclosure = (s, d) => {
  box(s, MX, 2.2, 5.2, 3.9, C.text1, "disclosed");
  txt(s, d.amount_label || "累计收入", { x: MX + 0.45, y: 2.6, w: 4.3, h: 0.35, fontSize: 16, color: C.accent4 });
  txt(s, d.amount, { x: MX + 0.45, y: 3.05, w: 4.3, h: 1.1, fontSize: 54, bold: true, fontFace: HEAD, color: C.background1, valign: "middle" });
  txt(s, d.amount_sub || "", { x: MX + 0.45, y: 4.25, w: 4.3, h: 0.4, fontSize: 20, color: C.background1 });
  txt(s, d.caption || "", { x: MX + 0.45, y: 5.4, w: 4.3, h: 0.35, fontSize: 12, color: C.accent4 });
  txt(s, d.parts_title || "", { x: MX + 5.6, y: 2.2, w: 5.9, h: 0.4, fontSize: 16, bold: true, color: C.text1 });
  (d.parts || []).slice(0, 4).forEach((t, i) => {
    const y = 2.75 + i * 0.75;
    box(s, MX + 5.6, y, CW - 5.6, 0.6, C.background2, "part-" + (i + 1));
    txt(s, String(i + 1), { x: MX + 5.85, y, w: 0.4, h: 0.6, fontSize: 18, bold: true, fontFace: HEAD, color: C.accent1, valign: "middle" });
    txt(s, t, { x: MX + 6.35, y, w: CW - 6.6, h: 0.6, fontSize: 16, color: C.text1, valign: "middle" });
  });
  if (d.parts_note) txt(s, d.parts_note, { x: MX + 5.6, y: 5.85, w: CW - 5.6, h: 0.35, fontSize: 14, color: C.text2, wrap: true });
};

R.backcalc = (s, d) => {
  const steps = (d.steps || []).slice(0, 4), SW = 2.35, SG = (CW - 3.0 - steps.length * SW) / Math.max(steps.length, 1);
  steps.forEach((st, i) => {
    const x = MX + i * (SW + SG), y = 2.4;
    box(s, x, y, SW, 2.4, C.background1, "step-" + (i + 1));
    txt(s, st.label, { x: x + 0.22, y: y + 0.28, w: SW - 0.44, h: 0.3, fontSize: 13, bold: true, color: C.accent1 });
    txt(s, st.value, { x: x + 0.22, y: y + 0.7, w: SW - 0.44, h: 0.6, fontSize: 22, bold: true, fontFace: HEAD, color: C.text1, valign: "middle" });
    txt(s, st.desc || "", { x: x + 0.22, y: y + 1.45, w: SW - 0.44, h: 0.8, fontSize: 12, color: C.text2, wrap: true, lineSpacingMultiple: 1.2 });
    s.addShape(pres.shapes.CHEVRON, { x: x + SW + SG / 2 - 0.12, y: y + 1.05, w: 0.24, h: 0.3, fill: { color: C.accent2 }, line: { color: C.accent2, width: 0 }, objectName: "arrow-" + (i + 1) });
  });
  const rx = MX + steps.length * (SW + SG), r = d.result || {};
  box(s, rx, 2.4, CW - (rx - MX), 2.4, C.accent1, "result");
  txt(s, r.label || "", { x: rx + 0.25, y: 2.68, w: 2.4, h: 0.3, fontSize: 13, bold: true, color: C.background1 });
  txt(s, r.value || "", { x: rx + 0.25, y: 3.1, w: 2.5, h: 0.9, fontSize: 44, bold: true, fontFace: HEAD, color: C.background1, valign: "middle" });
  txt(s, r.sub || "", { x: rx + 0.25, y: 4.1, w: 2.5, h: 0.3, fontSize: 12, color: C.background1 });
  note(s, d.note, 5.15);
};

R.explainer = (s, d) => {
  box(s, MX, 2.15, CW, 0.9, C.text1, "example");
  txt(s, d.example_label || "举例", { x: MX + 0.35, y: 2.15, w: 0.8, h: 0.9, fontSize: 14, bold: true, color: C.accent4, valign: "middle" });
  txt(s, d.example || "", { x: MX + 1.25, y: 2.15, w: CW - 1.5, h: 0.9, fontSize: 22, bold: true, fontFace: HEAD, color: C.background1, valign: "middle" });
  const HW = (CW - GAP) / 2, L = d.left || {}, Rt = d.right || {};
  box(s, MX, 3.3, HW, 2.8, C.background2, "left");
  txt(s, L.title || "", { x: MX + 0.35, y: 3.55, w: HW - 0.7, h: 0.4, fontSize: 18, bold: true, color: C.accent1 });
  if (L.bullets) txt(s, bullets(L.bullets), { x: MX + 0.35, y: 4.05, w: HW - 0.7, h: 1.9, fontSize: 14, color: C.text1, paraSpaceAfter: 8 });
  const rx = MX + HW + GAP;
  box(s, rx, 3.3, HW, 2.8, C.background2, "right");
  txt(s, Rt.title || "", { x: rx + 0.35, y: 3.55, w: HW - 0.7, h: 0.4, fontSize: 18, bold: true, color: C.accent1 });
  (Rt.chips || []).slice(0, 6).forEach((c, i) => {
    const cw = (HW - 0.7 - 0.3) / 3, x = rx + 0.35 + (i % 3) * (cw + 0.15), y = 4.1 + Math.floor(i / 3) * 0.6;
    box(s, x, y, cw, 0.46, C.background1, "chip-" + (i + 1));
    txt(s, c, { x, y, w: cw, h: 0.46, fontSize: 12, color: C.text1, align: "center", valign: "middle", wrap: true });
  });
  if (Rt.text) txt(s, Rt.text, { x: rx + 0.35, y: 5.35, w: HW - 0.7, h: 0.6, fontSize: 12, color: C.text2, wrap: true });
};

R.channel_card = (s, d) => {
  const TW = (5.4 - GAP) / 2;
  (d.tiles || []).slice(0, 4).forEach((t, i) => {
    const x = MX + (i % 2) * (TW + GAP), y = 2.2 + Math.floor(i / 2) * 1.32;
    box(s, x, y, TW, 1.15, C.background1, "tile-" + (i + 1));
    txt(s, t.value, { x: x + 0.3, y: y + 0.15, w: TW - 0.6, h: 0.55, fontSize: 24, bold: true, fontFace: HEAD, color: t.accent ? C.accent1 : C.text1, valign: "middle" });
    txt(s, t.label || "", { x: x + 0.3, y: y + 0.72, w: TW - 0.6, h: 0.3, fontSize: 12, color: C.text2 });
  });
  if (d.total) {
    box(s, MX, 4.9, 5.4, 1.25, C.text1, "total");
    txt(s, d.total.label || "", { x: MX + 0.3, y: 5.05, w: 2, h: 0.3, fontSize: 12, color: C.accent4 });
    txt(s, d.total.value || "", { x: MX + 0.3, y: 5.35, w: 4.8, h: 0.6, fontSize: 24, bold: true, fontFace: HEAD, color: C.background1, valign: "middle" });
  }
  const ex = MX + 5.8, ew = CW - 5.8;
  txt(s, d.list_title || "", { x: ex, y: 2.2, w: ew, h: 0.4, fontSize: 16, bold: true, color: C.text1 });
  (d.list || []).slice(0, 3).forEach((it, i) => {
    const y = 2.75 + i * 0.95;
    box(s, ex, y, ew, 0.8, C.background1, "list-" + (i + 1));
    txt(s, it.title, { x: ex + 0.25, y, w: ew - 2.3, h: 0.8, fontSize: 14, color: C.text1, valign: "middle", wrap: true });
    txt(s, it.value || "", { x: ex + ew - 2.0, y, w: 1.8, h: 0.8, fontSize: 13, bold: true, color: C.accent1, align: "right", valign: "middle" });
  });
  if (d.side_note) txt(s, d.side_note, { x: ex, y: 5.65, w: ew, h: 0.6, fontSize: 12, color: C.text2, wrap: true });
};

R.tips = (s, d) => {
  const cols = d.columns || [], LW = 5.6;
  txt(s, d.table_title || "", { x: MX, y: 2.15, w: LW, h: 0.4, fontSize: 16, bold: true, color: C.text1 });
  const rows = d.rows || [];
  s.addTable([cols.map((c) => th(c.label, c.align || "left"))].concat(rows.map((r, i) => r.map((t, j) => ({ text: t, options: Object.assign(
    { align: (cols[j] || {}).align || "left" }, i % 2 ? { fill: { color: C.background2 } } : {}, i === rows.length - 1 ? { bold: true } : {}) })))),
  { x: MX, y: 2.65, w: LW, colW: cols.map(() => LW / cols.length), rowH: 0.55, fontSize: 16, fontFace: BODY, color: C.text1, valign: "middle", margin: [0.04, 0.18, 0.04, 0.18], border: { type: "solid", pt: 0.5, color: NAMED.rule }, objectName: "tips-table" });
  const wx = MX + 6.0, ww = CW - 6.0;
  txt(s, d.steps_title || "", { x: wx, y: 2.15, w: ww, h: 0.4, fontSize: 16, bold: true, color: C.text1 });
  (d.steps || []).slice(0, 5).forEach((st, i) => {
    const y = 2.65 + i * 0.72, dark = !!st.dark, fg = dark ? C.background1 : C.text1;
    box(s, wx, y, ww, 0.6, dark ? C.text1 : i === 0 ? C.background2 : C.background1, "tip-step-" + (i + 1));
    txt(s, st.label, { x: wx + 0.25, y, w: 1.5, h: 0.6, fontSize: 15, bold: true, color: fg, valign: "middle" });
    txt(s, st.desc || "", { x: wx + 1.8, y, w: 2.2, h: 0.6, fontSize: 13, color: dark ? C.accent4 : C.text2, valign: "middle" });
    txt(s, st.value || "", { x: wx + ww - 1.85, y, w: 1.6, h: 0.6, fontSize: 18, bold: true, fontFace: HEAD, color: fg, align: "right", valign: "middle" });
  });
  note(s, d.note, 5.75);
};

R.table = (s, d) => {
  const cols = d.columns || [], rows = d.rows || [];
  let y = 2.1;
  if (d.bar && d.bar.length) {
    const tot = d.bar.reduce((a, b) => a + b.value, 0);
    let bx = MX;
    d.bar.forEach((b, i) => { const w = (b.value / tot) * CW; rect(s, bx, 2.15, w, 0.3, col(b.color, C.accent1), "share-" + (i + 1)); bx += w; });
    const lw = CW / d.bar.length;
    d.bar.forEach((b, i) => {
      rect(s, MX + i * lw, 2.6, 0.18, 0.18, col(b.color, C.accent1), "legend-" + (i + 1));
      txt(s, b.label, { x: MX + i * lw + 0.28, y: 2.52, w: lw - 0.35, h: 0.34, fontSize: 12, color: C.text1, valign: "middle" });
    });
    y = 3.0;
  }
  const fs = d.font_size || 14, rh = d.row_h || 0.45, widths = cols.map((c) => (c.width || 1 / cols.length) * CW);
  const body = rows.map((r, i) => r.map((t, j) => ({ text: String(t), options: Object.assign({ align: (cols[j] || {}).align || "left" },
    (i % 2 || (d.total_row && i === rows.length - 1)) ? { fill: { color: C.background2 } } : {},
    (d.total_row && i === rows.length - 1) || j === d.bold_col ? { bold: true } : {}) })));
  s.addTable([cols.map((c) => th(c.label, c.align || "left"))].concat(body), { x: MX, y, w: CW, colW: widths, rowH: rh, fontSize: fs, fontFace: BODY, color: C.text1,
    valign: "middle", margin: [0.03, 0.12, 0.03, 0.12], border: { type: "solid", pt: 0.5, color: NAMED.rule }, objectName: d.name || "table" });
  note(s, d.note, Math.min(y + (rows.length + 1) * rh + 0.12, 6.38));
};

R.monthly = (s, d) => {
  const t = d.total || {};
  box(s, MX, 2.2, 4.3, 3.7, C.text1, "monthly-total");
  txt(s, t.label || "", { x: MX + 0.4, y: 2.55, w: 3.5, h: 0.3, fontSize: 14, color: C.accent4 });
  txt(s, t.value || "", { x: MX + 0.4, y: 3.0, w: 3.6, h: 0.9, fontSize: 38, bold: true, fontFace: HEAD, color: C.background1, valign: "middle" });
  txt(s, t.sub || "", { x: MX + 0.4, y: 3.95, w: 3.5, h: 0.4, fontSize: 18, color: C.background1 });
  txt(s, t.caption || "", { x: MX + 0.4, y: 5.25, w: 3.6, h: 0.35, fontSize: 12, color: C.accent4 });
  const items = (d.items || []).slice(0, 4), mx0 = MX + 4.7, mw = CW - 4.7, maxShare = Math.max(...items.map((x) => x.share || 0), 0.0001);
  const pitch = items.length > 3 ? 0.95 : 1.28, h = pitch - 0.18;
  items.forEach((it, i) => {
    const y = 2.2 + i * pitch, bw = ((it.share || 0) / maxShare) * (mw - 4.7);
    box(s, mx0, y, mw, h, C.background1, "monthly-" + (i + 1));
    txt(s, it.label, { x: mx0 + 0.3, y: y + 0.12, w: 3.1, h: 0.35, fontSize: 15, bold: true, color: C.text1 });
    txt(s, it.value || "", { x: mx0 + 0.3, y: y + h / 2, w: 3.1, h: 0.4, fontSize: 18, bold: true, fontFace: HEAD, color: C.text1, valign: "middle" });
    rect(s, mx0 + 3.5, y + h / 2 - 0.12, Math.max(bw, 0.05), 0.24, col(it.color, C.accent1), "monthly-bar-" + (i + 1));
    txt(s, ((it.share || 0) * 100).toFixed(1) + "%", { x: mx0 + 3.6 + Math.max(bw, 0.05), y: y + h / 2 - 0.22, w: 0.8, h: 0.44, fontSize: 13, color: C.text2, valign: "middle" });
  });
  note(s, d.note, 6.1);
};

R.stats4 = (s, d) => {
  const tiles = (d.tiles || []).slice(0, 4), n = Math.max(tiles.length, 1), W = (CW - (n - 1) * GAP) / n;
  tiles.forEach((t, i) => {
    const x = MX + i * (W + GAP), y = 2.2, dark = !!t.dark;
    box(s, x, y, W, 2.0, dark ? C.text1 : C.background2, "stat-" + (i + 1));
    txt(s, t.label || "", { x: x + 0.3, y: y + 0.28, w: W - 0.6, h: 0.3, fontSize: 14, bold: true, color: dark ? C.accent4 : C.text2 });
    txt(s, t.value, { x: x + 0.3, y: y + 0.7, w: W - 0.6, h: 0.65, fontSize: 28, bold: true, fontFace: HEAD, color: dark ? C.background1 : C.text1, valign: "middle" });
    txt(s, t.sub || "", { x: x + 0.3, y: y + 1.42, w: W - 0.6, h: 0.3, fontSize: 13, color: dark ? C.accent4 : C.text2 });
  });
  if (d.bullets && d.bullets.length) {
    box(s, MX, 4.5, CW, 1.5, C.background2, "insight");
    txt(s, bullets(d.bullets), { x: MX + 0.35, y: 4.7, w: CW - 0.7, h: 1.15, fontSize: 15, color: C.text1, paraSpaceAfter: 8 });
  }
  note(s, d.note, 6.2);
};

R.topic_bars = (s, d) => {
  const cw2 = (CW - 0.5) / 2;
  [d.left, d.right].forEach((panel, pi) => {
    if (!panel) return;
    const x0 = MX + pi * (cw2 + 0.5), items = (panel.items || []).slice(0, 6), max = Math.max(...items.map((x) => x.value || 0), 1);
    txt(s, panel.title || "", { x: x0, y: 2.1, w: cw2, h: 0.4, fontSize: 16, bold: true, color: C.text1 });
    items.forEach((it, i) => {
      const y = 2.6 + i * 0.56;
      txt(s, it.label, { x: x0, y, w: 2.2, h: 0.5, fontSize: 14, color: C.text1, valign: "middle", wrap: true });
      if (it.bar === false) { txt(s, it.text || "", { x: x0 + 2.25, y, w: cw2 - 2.3, h: 0.5, fontSize: 13, bold: true, color: C.text1, valign: "middle", wrap: true }); return; }
      const bw = ((it.value || 0) / max) * 1.9;
      const c = pi === 0 ? (it.highlight ? C.accent1 : C.accent2) : (i === 0 ? C.accent5 : NAMED.lightBlue);
      rect(s, x0 + 2.25, y + 0.13, Math.max(bw, 0.04), 0.24, c, `bar-${pi}-${i}`);
      txt(s, it.text || "", { x: x0 + 2.25 + bw + 0.1, y, w: cw2 - 2.4 - bw, h: 0.5, fontSize: 13, bold: true, color: C.text1, valign: "middle" });
    });
  });
  if (d.insight) {
    box(s, MX, 5.55, CW, 0.85, C.background1, "topic-insight");
    txt(s, d.insight, { x: MX + 0.3, y: 5.55, w: CW - 0.6, h: 0.85, fontSize: 14, color: C.text1, valign: "middle", wrap: true });
  }
};

R.stacked_columns = (s, d) => {
  const series = d.series || [], cats = d.categories || [], vals = d.values || [];
  series.forEach((se, i) => {
    const x = MX + i * Math.min(2.3, CW / Math.max(series.length, 1));
    rect(s, x, 2.15, 0.2, 0.2, col(se.color, C.accent1), "legend-" + (i + 1));
    txt(s, se.label, { x: x + 0.3, y: 2.08, w: 1.95, h: 0.34, fontSize: 12, color: C.text1, valign: "middle" });
  });
  const totals = vals.map((r) => r.reduce((a, b) => a + b, 0)), maxT = Math.max(...totals, 1);
  const BASE = 5.75, HMAX = 2.9, pitch = CW / Math.max(cats.length, 1), bw = Math.min(0.52, pitch * 0.6), fsz = cats.length > 16 ? 10 : 12;
  // Long histories: shorten "2025.11" to "25.11" and label every n-th month so labels never collide.
  const every = Math.ceil(cats.length / 14), short = cats.length > 14;
  cats.forEach((m, i) => {
    const cx = MX + i * pitch, x = cx + (pitch - bw) / 2;
    let y = BASE;
    (vals[i] || []).forEach((c, k) => {
      if (!c) return;
      const h = (c / maxT) * HMAX; y -= h;
      const fill = col((series[k] || {}).color, C.accent1);
      rect(s, x, y, bw, h, fill, `col-${i}-${k}`);
      const darkFill = ["accent", "blue", "ink"].includes((series[k] || {}).color);
      if (h >= 0.3 && c >= 2) txt(s, String(c), { x, y, w: bw, h, fontSize: fsz, bold: true, color: darkFill ? C.background1 : C.text1, align: "center", valign: "middle" });
    });
    if (!short || totals[i] >= 3) txt(s, String(totals[i]), { x: cx - 0.2, y: y - 0.32, w: pitch + 0.4, h: 0.28, fontSize: fsz, bold: true, color: C.text1, align: "center", valign: "bottom", wrap: true });
    if (i % every === 0) txt(s, short ? m.replace(/^20/, "") : m, { x: cx - 0.3, y: BASE + 0.08, w: pitch + 0.6, h: 0.28, fontSize: fsz, color: C.text1, align: "center", wrap: true });
  });
  note(s, d.note, 6.3);
};

R.three_cols = (s, d) => {
  const cols = (d.cols || []).slice(0, 3), n = Math.max(cols.length, 1), W = (CW - (n - 1) * GAP) / n, h = d.banner ? 3.25 : 3.9;
  cols.forEach((c, i) => {
    const x = MX + i * (W + GAP), y = 2.15, dark = !!c.dark;
    box(s, x, y, W, h, dark ? C.text1 : C.background2, "col-" + (i + 1));
    // A title that needs two lines pushes the bullets down instead of overlapping them.
    const tl = widthPt(c.title || "", 16) > (W - 0.6) * 72 ? 2 : 1;
    txt(s, c.title || "", { x: x + 0.3, y: y + 0.25, w: W - 0.6, h: 0.4 * tl, fontSize: 16, bold: true, color: dark ? C.background1 : C.accent1, wrap: true });
    txt(s, bullets(c.bullets || []), { x: x + 0.3, y: y + 0.4 + 0.35 * tl, w: W - 0.6, h: h - 0.55 - 0.35 * tl, fontSize: 13, color: dark ? C.background1 : C.text1, paraSpaceAfter: 8, lineSpacingMultiple: 1.15 });
  });
  if (d.banner) {
    box(s, MX, 5.6, CW, 0.95, C.accent1, "banner");
    txt(s, d.banner, { x: MX + 0.3, y: 5.6, w: CW - 0.6, h: 0.95, fontSize: 15, bold: true, color: C.background1, valign: "middle", wrap: true });
  }
};

R.lessons = (s, d) => {
  const hd = d.headers || ["要点", "怎么做", "数据佐证"];
  [[hd[0], 0.8], [hd[1], 3.1], [hd[2], 7.15]].forEach(([l, dx]) => txt(s, l, { x: MX + dx, y: 2.08, w: 2, h: 0.3, fontSize: 12, bold: true, color: C.accent3 }));
  (d.rows || []).slice(0, 5).forEach((r, i) => {
    const y = 2.45 + i * 0.78;
    box(s, MX, y, CW, 0.7, C.background2, "lesson-" + (i + 1));
    oval(s, MX + 0.2, y + 0.13, 0.44, i + 1, "lesson-num-" + (i + 1));
    txt(s, r.title, { x: MX + 0.8, y, w: 2.2, h: 0.7, fontSize: 15, bold: true, color: C.text1, valign: "middle", wrap: true });
    txt(s, r.how || "", { x: MX + 3.1, y, w: 3.85, h: 0.7, fontSize: 13, color: C.text1, valign: "middle", wrap: true });
    txt(s, r.evidence || "", { x: MX + 7.15, y, w: 4.2, h: 0.7, fontSize: 12, color: C.text2, valign: "middle", wrap: true });
  });
  note(s, d.note, 6.32);
};

R.cards = (s, d) => {
  let top = 2.15;
  if (d.statement) {
    box(s, MX, 2.1, CW, 0.75, C.text1, "statement");
    txt(s, d.statement, { x: MX + 0.35, y: 2.1, w: CW - 0.7, h: 0.75, fontSize: 15, bold: true, color: C.background1, valign: "middle", wrap: true });
    top = 3.0;
  } else if (d.lead) {
    txt(s, d.lead, { x: MX, y: 2.02, w: CW, h: 0.45, fontSize: 12, color: C.text2, wrap: true });
    top = 2.6;
  }
  const cards = d.cards || [], ncol = d.columns || (cards.length <= 3 ? cards.length : cards.length <= 6 && cards.length !== 4 ? 3 : 4);
  const nrow = Math.ceil(cards.length / ncol), bottom = d.banner ? 5.9 : 6.3, g = 0.2;
  const W = (CW - (ncol - 1) * g) / ncol, H = Math.min((bottom - top - (nrow - 1) * 0.15) / nrow, 2.2);
  cards.forEach((c, i) => {
    const x = MX + (i % ncol) * (W + g), y = top + Math.floor(i / ncol) * (H + 0.15), dark = !!c.dark;
    // Cards take the opposite tone of the slide background so they stay visible on either.
    box(s, x, y, W, H, dark ? C.text1 : col(c.fill, d.bg === "alt" ? C.background1 : C.background2), "card-" + (i + 1));
    let yy = y + 0.16;
    if (c.num) { txt(s, String(c.num), { x: x + 0.25, y: yy, w: W - 0.5, h: 0.32, fontSize: 15, bold: true, fontFace: HEAD, color: dark ? C.accent6 : C.accent1 }); yy += 0.34; }
    txt(s, c.title || "", { x: x + 0.25, y: yy, w: W - 0.5, h: 0.32, fontSize: 15, bold: true, color: dark ? C.accent6 : c.num ? C.text1 : C.accent1, wrap: true });
    yy += 0.38;
    if (c.body) txt(s, c.body, { x: x + 0.25, y: yy, w: W - 0.5, h: 0.6, fontSize: 12, color: dark ? C.background1 : C.text1, wrap: true, lineSpacingMultiple: 1.1 });
    if (c.bar) {
      const bw = W - 0.5, max = c.bar.max || 100, by = y + H - (c.note ? 0.72 : 0.45);
      rect(s, x + 0.25, by, bw, 0.14, d.bg === "alt" ? C.background2 : C.background1, `card-track-${i}`);
      rect(s, x + 0.25, by, (c.bar.value / max) * bw, 0.14, c.bar.good ? C.accent1 : C.accent2, `card-bar-${i}`);
      if (c.bar.base != null) rect(s, x + 0.25 + (c.bar.base / max) * bw - 0.01, by - 0.06, 0.02, 0.26, C.text1, `card-base-${i}`);
      if (c.bar.label) txt(s, c.bar.label, { x: x + 0.25, y: by + 0.18, w: W - 0.5, h: 0.24, fontSize: 11, bold: true, color: c.bar.good ? C.accent1 : C.text2 });
    }
    if (c.note) txt(s, c.note, { x: x + 0.25, y: y + H - 0.32, w: W - 0.5, h: 0.24, fontSize: 11, color: dark ? C.accent4 : C.text2 });
  });
  if (d.banner) {
    box(s, MX, 6.0, CW, 0.6, C.background2, "banner");
    txt(s, d.banner, { x: MX + 0.3, y: 6.0, w: CW - 0.6, h: 0.6, fontSize: 13, color: C.text1, valign: "middle", wrap: true });
  } else note(s, d.note, 6.38);
};

R.numbered = (s, d) => {
  const AW2 = (CW - GAP) / 2;
  (d.items || []).slice(0, 4).forEach((it, i) => {
    const x = MX + (i % 2) * (AW2 + GAP), y = 2.2 + Math.floor(i / 2) * 1.75;
    box(s, x, y, AW2, 1.55, C.background1, "item-" + (i + 1));
    txt(s, String(i + 1), { x: x + 0.3, y, w: 0.5, h: 1.55, fontSize: 36, bold: true, fontFace: HEAD, color: C.accent1, valign: "middle" });
    txt(s, it.title, { x: x + 1.0, y: y + 0.3, w: AW2 - 1.3, h: 0.4, fontSize: 18, bold: true, color: C.text1 });
    txt(s, it.body || "", { x: x + 1.0, y: y + 0.82, w: AW2 - 1.3, h: 0.5, fontSize: 14, color: C.text2, wrap: true });
  });
  if (d.banner) {
    box(s, MX, 5.75, CW, 0.85, C.text1, "banner");
    txt(s, d.banner, { x: MX + 0.35, y: 5.75, w: CW - 0.7, h: 0.85, fontSize: 15, color: C.background1, valign: "middle", wrap: true });
  }
};

R.panels = (s, d) => {
  const HW = (CW - GAP) / 2;
  (d.panels || []).slice(0, 2).forEach((p, i) => {
    const x = MX + i * (HW + GAP), y = 2.15, dark = !!p.dark;
    box(s, x, y, HW, 2.55, dark ? C.text1 : d.bg === "alt" ? C.background1 : C.background2, "panel-" + (i + 1));
    txt(s, p.title || "", { x: x + 0.35, y: y + 0.25, w: HW - 0.7, h: 0.4, fontSize: 16, bold: true, color: dark ? C.accent6 : C.accent1 });
    txt(s, p.big || "", { x: x + 0.35, y: y + 0.75, w: HW - 0.7, h: 0.5, fontSize: 24, bold: true, fontFace: HEAD, color: dark ? C.background1 : C.text1, valign: "middle" });
    txt(s, p.line || "", { x: x + 0.35, y: y + 1.35, w: HW - 0.7, h: 0.4, fontSize: 15, bold: true, color: dark ? C.background1 : C.text1, wrap: true });
    txt(s, p.sub || "", { x: x + 0.35, y: y + 1.85, w: HW - 0.7, h: 0.5, fontSize: 13, color: dark ? C.accent4 : C.text2, wrap: true });
  });
  if (d.box) {
    box(s, MX, 4.95, CW, 1.25, d.bg === "alt" ? C.background1 : C.background2, "panel-box");
    txt(s, d.box.title || "", { x: MX + 0.35, y: 5.05, w: 3, h: 0.35, fontSize: 14, bold: true, color: C.accent1 });
    txt(s, d.box.text || "", { x: MX + 0.35, y: 5.4, w: CW - 0.7, h: 0.7, fontSize: 14, color: C.text1, wrap: true });
  }
  note(s, d.note, 6.3);
};

R.gear = (s, d) => {
  // Left: shooting styles counted over sampled frames. Right: gear items with how sure we are.
  const LW = 4.9, style = (d.style || []).slice(0, 6), total = d.frames || style.reduce((a, x) => a + x.count, 0) || 1;
  const max = Math.max(...style.map((x) => x.count), 1);
  txt(s, d.style_title || `拍摄方式（${total} 张截帧统计）`, { x: MX, y: 2.1, w: LW, h: 0.4, fontSize: 16, bold: true, color: C.text1 });
  style.forEach((x, i) => {
    const y = 2.6 + i * 0.52, bw = (x.count / max) * 1.4;
    txt(s, x.label, { x: MX, y, w: 2.2, h: 0.46, fontSize: 13, color: C.text1, valign: "middle", wrap: true });
    rect(s, MX + 2.25, y + 0.12, Math.max(bw, 0.04), 0.22, i === 0 ? C.accent1 : C.accent2, "style-bar-" + i);
    txt(s, `${x.count} 张 · ${Math.round((x.count / total) * 100)}%`, { x: MX + 2.25 + bw + 0.1, y, w: LW - 2.35 - bw, h: 0.46, fontSize: 12, bold: true, color: C.text1, valign: "middle" });
  });
  if (d.specs) txt(s, "画质：" + d.specs, { x: MX, y: 2.6 + style.length * 0.52 + 0.1, w: LW, h: 0.5, fontSize: 12, color: C.text2, wrap: true });
  const rx = MX + LW + 0.4, rw = CW - LW - 0.4, items = (d.items || []).slice(0, 5);
  txt(s, d.items_title || "器材推断", { x: rx, y: 2.1, w: rw, h: 0.4, fontSize: 16, bold: true, color: C.text1 });
  items.forEach((it, i) => {
    const y = 2.6 + i * 0.68, sure = /证据|确认|confirmed/i.test(it.level || "");
    box(s, rx, y, rw, 0.6, d.bg === "alt" ? C.background1 : C.background2, "gear-" + i);
    txt(s, it.category || "", { x: rx + 0.2, y, w: 1.1, h: 0.6, fontSize: 12, bold: true, color: C.accent1, valign: "middle", wrap: true });
    txt(s, it.name || "", { x: rx + 1.35, y: y + 0.05, w: rw - 2.3, h: 0.28, fontSize: 13, bold: true, color: C.text1 });
    txt(s, it.basis || "", { x: rx + 1.35, y: y + 0.31, w: rw - 1.5, h: 0.26, fontSize: 11, color: C.text2 });
    box(s, rx + rw - 0.85, y + 0.08, 0.7, 0.26, sure ? C.accent1 : C.accent2, "level-" + i);
    txt(s, it.level || "推断", { x: rx + rw - 0.85, y: y + 0.08, w: 0.7, h: 0.26, fontSize: 11, bold: true, color: C.background1, align: "center", valign: "middle" });
  });
  if (d.summary) {
    box(s, MX, 6.0, CW, 0.6, C.text1, "gear-summary");
    txt(s, d.summary, { x: MX + 0.3, y: 6.0, w: CW - 0.6, h: 0.6, fontSize: 13, color: C.background1, valign: "middle", wrap: true });
  } else note(s, d.note, 6.38);
};

R.images = (s, d) => {
  // 1–3 images side by side (or stacked with layout "stack"), each fitted into its slot without distortion.
  let top = 2.1;
  if (d.statement) {
    box(s, MX, 2.05, CW, 0.62, C.text1, "statement");
    txt(s, d.statement, { x: MX + 0.3, y: 2.05, w: CW - 0.6, h: 0.62, fontSize: 14, bold: true, color: C.background1, valign: "middle", wrap: true });
    top = 2.82;
  }
  const imgs = (d.images || []).slice(0, 3), n = Math.max(imgs.length, 1), stack = d.layout === "stack";
  const bottom = d.banner ? 5.85 : 6.3, capH = 0.34, g = 0.25;
  const slotW = stack ? CW : (CW - (n - 1) * g) / n, slotH = stack ? (bottom - top - (n - 1) * 0.12) / n : bottom - top;
  const base = path.dirname(path.resolve(deckPath));
  imgs.forEach((im, i) => {
    const sx = stack ? MX : MX + i * (slotW + g), sy = stack ? top + i * (slotH + 0.12) : top;
    const availH = slotH - (im.caption ? capH : 0), r = im.ratio || 16 / 9;
    let w = slotW, h = w / r;
    if (h > availH) { h = availH; w = h * r; }
    const x = sx + (slotW - w) / 2;
    if (im.caption) txt(s, im.caption, { x: sx, y: sy, w: slotW, h: capH - 0.04, fontSize: 13, bold: true, color: im.accent ? C.accent1 : C.text1, align: stack ? "left" : "center", valign: "middle" });
    s.addImage({ path: path.resolve(base, im.path), x, y: sy + (im.caption ? capH : 0), w, h, objectName: "image-" + (i + 1) });
  });
  if (d.banner) {
    box(s, MX, 5.98, CW, 0.62, d.bg === "alt" ? C.background1 : C.background2, "banner");
    txt(s, d.banner, { x: MX + 0.3, y: 5.98, w: CW - 0.6, h: 0.62, fontSize: 13, color: C.text1, valign: "middle", wrap: true });
  } else note(s, d.note, 6.38);
};

// ---------------------------------------------------------------- build
const hasSections = deck.slides.some((d) => d.section);
let section = null;
deck.slides.forEach((d, i) => {
  slideNo = i + 1;
  if (!R[d.type]) { console.error(`slide ${slideNo}: unknown type "${d.type}" (see references/deck-json.md)`); process.exit(1); }
  if (hasSections && (d.section || !section) && d.section !== section) { section = d.section || "概览"; pres.addSection({ title: section }); }
  const master = d.type === "cover" ? "COVER" : d.bg === "alt" ? "CONTENT_ALT" : "CONTENT_LIGHT";
  const s = pres.addSlide(Object.assign({ masterName: master }, hasSections ? { sectionTitle: section } : {}));
  if (d.type !== "cover") { s.addText(d.eyebrow || "", { placeholder: "eyebrow" }); s.addText(d.title || "", { placeholder: "title" }); if (widthPt(d.title || "", 36) > CW * 72 * 0.98) warnings.push(`slide ${slideNo}: title wraps to two lines`); }
  R[d.type](s, d);
  if (d.notes) s.addNotes(d.notes);
});

(async () => {
  await pres.writeFile({ fileName: outPath });
  // pptxgenjs writes Office's palette and empty East Asian font slots; without this, scheme
  // colours fall back to Office blue and Chinese text to the default CJK font (等线).
  const zip = await JSZip.loadAsync(fs.readFileSync(outPath));
  const p = "ppt/theme/theme1.xml";
  let xml = await zip.file(p).async("string");
  for (const [k, v] of Object.entries(PALETTE)) xml = xml.replace(new RegExp(`<a:${k}>[\\s\\S]*?</a:${k}>`), `<a:${k}><a:srgbClr val="${v}"/></a:${k}>`);
  const fix = (block, face) => block.replace(/<a:ea typeface="[^"]*"\/>/, `<a:ea typeface="${face}"/>`).replace(/<a:font script="Hans" typeface="[^"]*"\/>/, `<a:font script="Hans" typeface="${face}"/>`);
  xml = xml.replace(/<a:majorFont>[\s\S]*?<\/a:majorFont>/, (m) => fix(m, HEAD)).replace(/<a:minorFont>[\s\S]*?<\/a:minorFont>/, (m) => fix(m, BODY));
  zip.file(p, xml);
  fs.writeFileSync(outPath, await zip.generateAsync({ type: "nodebuffer", compression: "DEFLATE" }));
  warnings.forEach((w) => console.warn("WARN " + w));
  console.log(`wrote ${outPath} (${deck.slides.length} slides${warnings.length ? `, ${warnings.length} layout warnings` : ""})`);
})();
