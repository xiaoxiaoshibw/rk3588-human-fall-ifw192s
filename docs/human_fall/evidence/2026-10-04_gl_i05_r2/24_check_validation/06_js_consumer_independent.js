// Independent second-review DOM/canvas consumer of the ACTUAL generated page.
// Exercises selected-plane residual, index lookup, click, frame/box switch and
// display budget against the real embedded payload. Not a real DPR run.
const fs = require('fs'), vm = require('vm'), assert = require('assert');
const path = require('path');
const html = fs.readFileSync(path.join(__dirname, '..', 'research_01', 'spatial_02', 'source_review.html'), 'utf8');
const elements = {}, marks = [];
function element(id) {
  if (elements[id]) return elements[id];
  return elements[id] = {
    value: '', textContent: '', width: 980, height: 600, options: [],
    add(o) { this.options.push(o); if (this.options.length === 1) this.value = String(o.value); },
    getBoundingClientRect() { return { left: 0, top: 0, width: 980, height: 600 }; },
    getContext() { return { clearRect() { marks.length = 0; }, fillRect(x, y) { marks.push([x + 2, y + 2]); } }; }
  };
}
const context = vm.createContext({ document: { getElementById: element }, Option: function (t, v) { this.text = t; this.value = v; }, console });
for (const match of html.matchAll(/<script>([\s\S]*?)<\/script>/g)) vm.runInContext(match[1], context);
const evaluate = c => vm.runInContext(c, context);

const out = { status: 'FAIL', actual_js: true };
const first = evaluate('D.records[key()][0]');
out.first_row = first[0];

// hand residual from payload for each plane, compare against page readPoint
const labels = evaluate('Object.keys(D.planes)');
const resid = {};
for (const label of labels) {
  element('plane').value = label; element('plane').onchange();
  element('row').value = String(first[0]); element('lookup').onclick();
  const p = JSON.parse(element('point').textContent);
  const plane = evaluate('D.planes[P.value]');
  const hand = first[2].reduce((s, v, i) => s + v * plane.normal[i], plane.offset_m);
  assert(Math.abs(p.residual_m - hand) < 1e-12, 'residual mismatch ' + label);
  assert.equal(p.pooled_row, first[0]);
  assert.strictEqual(typeof p.seq, 'number');
  assert.strictEqual(typeof p.ordinal, 'number');
  assert(p.origin.includes('not_physical'));
  resid[label] = p.residual_m;
}
out.residuals = resid;
out.residuals_differ = new Set(Object.values(resid)).size > 1;

// index lookup for a different row returns matching xyz
element('plane').value = 'WHAT_IF_FIT_PCA_normal'; element('plane').onchange();
const rows = evaluate("D.records[key()]");
const target = rows[Math.floor(rows.length / 2)];
element('row').value = String(target[0]); element('lookup').onclick();
const p2 = JSON.parse(element('point').textContent);
out.index_lookup_ok = p2.pooled_row === target[0] && JSON.stringify(p2.source_xyz_m) === JSON.stringify(target[2]);

// click on first drawn mark maps back to first row
element('budget').value = '1'; element('budget').onchange();
assert.equal(JSON.parse(element('meta').textContent).shown, 1);
const click = marks[0];
element('c').onclick({ clientX: click[0], clientY: click[1] });
out.click_lookup_ok = JSON.parse(element('point').textContent).pooled_row === first[0];

// display budget 0 hides drawn rows but preserves full stats count
element('budget').value = '0'; element('budget').onchange();
const meta0 = JSON.parse(element('meta').textContent);
element('budget').value = '100000'; element('budget').onchange();
const metaAll = JSON.parse(element('meta').textContent);
out.display_cap_only_visual = meta0.shown === 0 && meta0.full_count === metaAll.full_count;

// frame switch changes the underlying record key and reported ordinal
const firstKey = evaluate('key()');
element('frame').value = '88'; element('frame').onchange();
const lastKey = evaluate('key()');
const metaFrame = JSON.parse(element('meta').textContent);
out.frame_switch_ok = lastKey !== firstKey && metaFrame.frame.ordinal === D_frames_last(context);
function D_frames_last(ctx) { return vm.runInContext('D.frames[D.frames.length-1].ordinal', ctx); }

element('box').value = 'v3'; element('box').onchange();
out.box_switch_ok = JSON.parse(element('meta').textContent).box === 'v3';

out.status = (out.residuals_differ && out.index_lookup_ok && out.click_lookup_ok &&
  out.display_cap_only_visual && out.frame_switch_ok && out.box_switch_ok) ? 'PASS' : 'FAIL';
out.actual_browser_DPR = 'NOT_RUN';
fs.writeFileSync(path.join(__dirname, '06_js_consumer_independent.json'), JSON.stringify(out, null, 2));
console.log(JSON.stringify(out));
