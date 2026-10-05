'use strict';
/* R3 报告页 Node 逻辑检查：解析 07_REPORT.html 内嵌渲染函数 + 真实 JSON 源，
   用最小 DOM 桩驱动 render()/charts()；另测 boot() 缺文件→显式「加载失败」，坏数据→显式抛错。 */
const fs = require('fs');
const path = require('path');
const vm = require('vm');
const DIR = __dirname;
const src = fs.readFileSync(path.join(DIR, '07_REPORT.html'), 'utf8');
const m = src.match(/<script>([\s\S]*?)<\/script>/);
if (!m) throw new Error('script block not found');
const codeNoBoot = m[1].replace(/^boot\(\)\.catch[\s\S]*$/m, '');

// 最小 DOM 桩（每个 test 独立）
function makeDom() {
  const store = new Map();
  const ctx = () => ({ strokeStyle: '', fillStyle: '', font: '', beginPath() {}, moveTo() {}, lineTo() {}, stroke() {}, strokeRect() {}, fillText() {}, measureText: () => ({ width: 0 }) });
  const make = () => ({ innerHTML: '', children: [], insertAdjacentHTML(_, h) { this.children.push(h); }, appendChild(c) { this.children.push(c); }, getContext: ctx, width: 0, height: 0, style: {} });
  return {
    store,
    document: {
      getElementById: id => { if (!store.has(id)) store.set(id, make()); return store.get(id); },
      createElement: () => make(),
    },
  };
}
const load = n => JSON.parse(fs.readFileSync(path.join(DIR, n), 'utf8'));

function runRender(dom, DATA) {
  const sb = { document: dom.document, console };
  vm.createContext(sb);
  vm.runInContext(codeNoBoot, sb, { filename: '07<script>' });
  vm.runInContext(`DIAG=JSON.parse(arguments[0]);FRAMES=JSON.parse(arguments[1]);M1=JSON.parse(arguments[2]);M2=JSON.parse(arguments[3]);render();`,
    Object.assign(sb, { arguments: [JSON.stringify(DATA[0]), JSON.stringify(DATA[1]), JSON.stringify(DATA[2]), JSON.stringify(DATA[3])] }));
  return dom.store.get('m').innerHTML;
}

(async () => {
  // 1) 真实数据 → 关键数值/FAIL/图数
  const dom = makeDom();
  const html = runRender(dom, [load('01_REGION_DIAG.json'), load('02_FRAME_SEQUENCE.json'), load('04_MODEL_I.json'), load('05_MODEL_II.json')]);
  const must = ['badge bC', '9.3960°', '0.23283', '0.01335', '0.01892', 'FAIL', 'SUBMITTED', '772=193×4'];
  const miss = must.filter(s => !html.includes(s));
  if (miss.length) throw new Error('missing strings: ' + JSON.stringify(miss));
  const failCount = (html.match(/class="fail">FAIL/g) || []).length;
  if (failCount < 6) throw new Error('cross-region FAIL rows not preserved: ' + failCount);
  const canvases = dom.store.get('charts').children.filter(c => c.getContext).length;
  if (canvases !== 8) throw new Error('expect 8 canvases got ' + canvases);
  console.log('HTML_LOGIC_OK fail_rows=' + failCount + ' canvases=' + canvases);

  // 2) boot() 404 → 显式「加载失败」
  {
    const dom404 = makeDom();
    const sb404 = {
      document: dom404.document, console,
      fetch: async () => ({ ok: false, status: 404, json: async () => ({}) }),
    };
    vm.createContext(sb404);
    await vm.runInContext(m[1], sb404, { filename: '07<script>' });
    const h = dom404.store.get('m').innerHTML;
    if (!h.includes('加载失败')) throw new Error('404 path no explicit error: ' + h.slice(0, 120));
    console.log('BAD_INPUT_404_OK explicit error shown');
  }

  // 3) 坏数据 → 明确抛错（不静默渲染 undefined）
  const badSets = [
    [{}, load('02_FRAME_SEQUENCE.json'), load('04_MODEL_I.json'), load('05_MODEL_II.json')],                    // 空 DIAG
    [load('01_REGION_DIAG.json'), { frames: [], five_mad_outlier_frames_by_cell: {} }, load('04_MODEL_I.json'), { npz: {}, series: {}, covariance_method: '', consumer_api_draft: { options: [], recommendation: '' } }],  // 空 series→图表 NaN
    [load('01_REGION_DIAG.json'), load('02_FRAME_SEQUENCE.json'), load('04_MODEL_I.json'), null],              // 缺 M2
  ];
  for (const [i, bad] of badSets.entries()) {
    let threw = false;
    try { runRender(makeDom(), bad); } catch (e) { threw = true; }
    if (!threw) throw new Error('bad set ' + i + ' did not throw');
    console.log('BAD_INPUT_REJECT_' + i + '_OK');
  }
})().catch(e => { console.error('HTML_CHECK_FAIL', e); process.exit(1); });
