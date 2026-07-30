/* Pull the candidate-scoring functions straight out of room-studio.html and diff them
   against the Python in imgscore.py on identical pixel buffers. Verifies what actually
   ships, not a copy of it. Driven by `python eval_imgscore.py <cache> --parity`.

     node parity.js <path/to/room-studio.html> <parity-dir> */
const fs = require('fs'), path = require('path');

const html = fs.readFileSync(process.argv[2], 'utf8');
const start = html.indexOf('const CAND_S=256;');
const end = html.indexOf('function scoreCandidate(cv)');
if (start < 0 || end < 0) {
  console.error('scoring block not found in room-studio.html — did the markers move?');
  process.exit(2);
}
const src = html.slice(start, end);
for (const fn of ['candGray', 'candPercentile', 'candTextScore', 'candGutterScore', 'candVividScore', 'candSeamScore', 'candPlaceFeat', 'candSelScore', 'candPlaceScore']) {
  if (!src.includes('function ' + fn)) { console.error('missing ' + fn); process.exit(2); }
}
const m = new Function(src + '; return {candTextScore, candGutterScore, candVividScore, candSeamScore, candPlaceFeat, candSelScore, candPlaceScore};')();

const dir = process.argv[3];
const exp = JSON.parse(fs.readFileSync(path.join(dir, 'expected.json'), 'utf8'));
let bad = 0;
for (const e of exp) {
  const d = new Uint8ClampedArray(fs.readFileSync(path.join(dir, e.file)));
  const t = m.candTextScore(d), g = m.candGutterScore(d), v = m.candVividScore(d);
  const s = m.candSeamScore(d), p = m.candPlaceFeat(d);
  // …and the two scores end to end: this is what catches a weight edited in only one file.
  const sel = m.candSelScore(d, t), place = m.candPlaceScore(d, sel, t);
  const ok = t.glyphs === e.glyphs && Math.abs(t.textPx - e.text_px) < 1e-6
    && g === e.gutter && Math.abs(v - e.vivid) < 1e-6
    && s.seams === e.seams && Math.abs(s.seamMax - e.seam_max) < 1e-6
    && Math.abs(p.ringPure - e.ring_pure) < 1e-6 && Math.abs(p.ringEdge - e.ring_edge) < 1e-6
    && Math.abs(p.fgBorder - e.fg_border) < 1e-6
    && Math.abs(sel - e.sel) < 1e-6 && Math.abs(place - e.place) < 1e-6;
  if (!ok) {
    bad++;
    console.log(`MISMATCH ${e.file} glyphs ${t.glyphs}/${e.glyphs} ` +
      `textPx ${t.textPx}/${e.text_px} gutter ${g}/${e.gutter} vivid ${v}/${e.vivid} ` +
      `seams ${s.seams}/${e.seams} seamMax ${s.seamMax}/${e.seam_max} ` +
      `ringPure ${p.ringPure}/${e.ring_pure} ringEdge ${p.ringEdge}/${e.ring_edge} ` +
      `fgBorder ${p.fgBorder}/${e.fg_border} sel ${sel}/${e.sel} place ${place}/${e.place}`);
  }
}
console.log(bad === 0 ? `parity OK — room-studio.html matches imgscore.py on ${exp.length} images`
  : `${bad}/${exp.length} mismatched`);
process.exit(bad ? 1 : 0);
