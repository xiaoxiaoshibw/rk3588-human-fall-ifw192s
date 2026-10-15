// console.html 内联脚本逻辑测试（node 环境，最小 DOM 替身，无 jsdom 依赖）
// 运行：node console_html.test.js
'use strict';
const fs = require('fs');
const path = require('path');
const vm = require('vm');

const html = fs.readFileSync(path.join(__dirname, 'console.html'), 'utf8');
const m = html.match(/<script>([\s\S]*)<\/script>/);
if (!m) throw new Error('console.html 缺 <script> 块');
const SRC = m[1];

// 回归（2026-10-14）：USB 摄像头必须 iframe 内嵌，不得再 mode:"tab" 弹窗——
// pywebview/WebView2 会吞顶层 window.open，卡片点了"打不开"（其根因）。
// 用 indexOf 而非正则，避免转义/注释坑；卡片定义需在一行内（APPS 各卡本来就单行）。
{
  const l = html.split('\n').find(x => x.includes('USB 摄像头'));
  if (!l) throw new Error('找不到 USB 摄像头 卡片行');
  const ci = l.indexOf('//', l.indexOf('/stream'));  // 行内注释起点（跳过 URL 里的 http://）
  const code = ci === -1 ? l : l.slice(0, ci);
  if (code.indexOf('mode:"tab"') !== -1 || code.indexOf("mode:'tab'") !== -1)
    throw new Error('USB 摄像头禁用 mode:"tab"（pywebview 吞 window.open），必须 iframe 内嵌');
  if (code.indexOf('/stream') === -1) throw new Error('USB 摄像头卡片缺 /stream URL');
}

// ---- 最小 DOM 替身：脚本用到的只有 querySelector / classList / innerHTML / onclick ----
function el(id) {
  return {
    id,
    hidden: false,
    textContent: '',
    innerHTML: '',
    src: '',
    onclick: null,
    classList: {
      _s: new Set(id === 'home' ? ['view', 'on'] : ['view']),
      add(c) { this._s.add(c); },
      remove(c) { this._s.delete(c); },
      contains(c) { return this._s.has(c); },
    },
    contentWindow: null,   // 用例注入
    children: [],                                  // 记录分组渲染结果（分栏测试用）
    appendChild(c) { this.children.push(c); },
    querySelector(sel) { return registry[sel.slice(1)]; },
  };
}

const registry = {};
for (const id of ['home', 'app', 'f', 'err', 'appname', 'back', 'pop', 'retry', 'errmsg', 'errurl', 'grid']) {
  registry[id] = el(id);
}

function makeWindow(locationHref) {
  const loc = new URL(locationHref);
  const win = {
    location: loc,
    listeners: {},
    addEventListener(type, fn) { (this.listeners[type] = this.listeners[type] || []).push(fn); },
    history: { replaceState(_, __, u) { const x = new URL(u, loc); registry.__hash = x.hash; loc.hash = x.hash; } },
    document: {
      querySelector(sel) {
        if (sel.startsWith('#')) return registry[sel.slice(1)];
        throw new Error('替身不支持选择器 ' + sel);
      },
      createElement() { return { className: '', innerHTML: '', onclick: null, children: [], appendChild(c) { this.children.push(c); } }; },
    },
    open() { throw new Error('不应弹窗'); },
  };
  win.window = win;   // 页内脚本用 window.addEventListener，vm 里补 window 自引用
  return win;
}

function loadShell(href, fetchImpl) {
  const win = makeWindow(href || 'http://127.0.0.1/console.html?replay_port=8901');
  win.URLSearchParams = URLSearchParams;
  win.Number = Number;
  win.URL = URL;
  win.fetch = () => fetchImpl || okFetch;
  registry.grid.children.length = 0;   // 每次装载重渲染：清掉上一用例的卡片树
  vm.createContext(win);
  vm.runInContext(SRC, win, { filename: 'console.html<script>' });
  if (typeof win.open !== 'function') {
    throw new Error('脚本未把 open(i) 挂到 window（vm context 需 function 声明或全局赋值）');
  }
  return win;
}

let passed = 0, failed = 0;
function t(name, fn) {
  try { fn(); passed++; console.log('ok  ' + name); }
  catch (e) { failed++; console.log('FAIL ' + name + '\n  ' + e.message); }
}
function eq(a, b, msg) { if (a !== b) throw new Error(`${msg || '不等'}: ${JSON.stringify(a)} != ${JSON.stringify(b)}`); }

// 探活替身：同步 thenable，用例保持同步；真 Promise 的 resolve/reject 等价
const okFetch = { then(onOk) { onOk({ type: 'opaque' }); } };
const failFetch = { then(_, onErr) { onErr(new TypeError('Failed to fetch')); } };

t('内联脚本能 parse 并转移出 <script> 块', () => {
  if (SRC.length < 500) throw new Error('脚本太短，疑似正则不匹配');
});

t('板端 WebUI 带 fail 文案且本地应用不带', () => {
  const win = loadShell();
  const APPS = vm.runInContext('APPS', win);
  if (!APPS[1].fail) throw new Error('板端 WebUI 缺 fail 文案');
  if (APPS[0].fail || APPS[2].fail || APPS[3].fail) throw new Error('本地应用不应有 fail');
});

t('APPS[1] fail 文案 = 当前不在内网', () => {
  const win = loadShell();
  const APPS = vm.runInContext('APPS', win);
  eq(APPS[1].fail, '当前不在内网，无法连接板端 WebUI');
  eq(APPS[0].fail, undefined);
  eq(APPS[2].fail, undefined);
  eq(APPS[3].fail, undefined);
});

t('探活成功 → 直接嵌 iframe，不弹提示', () => {
  const win = loadShell(null, okFetch);
  vm.runInContext('open(1)', win);
  eq(registry.err.hidden, true, '应无提示');
  eq(registry.f.hidden, false, 'iframe 应可见');
  eq(registry.f.src, 'http://192.168.31.58:8090/', '探活成功后才设 src');
});

t('探活失败（不在内网）→ 弹提示并隐藏 iframe', () => {
  const win = loadShell(null, failFetch);
  vm.runInContext('open(1)', win);
  eq(registry.err.hidden, false, '应弹提示');
  eq(registry.f.hidden, true, 'iframe 应隐藏');
  eq(registry.errmsg.textContent, '当前不在内网，无法连接板端 WebUI');
  eq(registry.errurl.textContent, 'http://192.168.31.58:8090');
});

t('无 fail 文案的本地应用不探活，直接嵌', () => {
  const win = loadShell(null, { then() { throw new Error('本地应用不应探活'); } });
  vm.runInContext('open(0)', win);  // 会话回放（本地服务）
  eq(registry.err.hidden, true, '本地应用永不弹提示');
  eq(registry.f.src, 'http://127.0.0.1:8901/');
});

t('重进同应用不重载（保留页内状态）', () => {
  let probes = 0;
  const win = loadShell(null, { then(onOk) { probes++; onOk({}); } });
  vm.runInContext('open(1)', win);
  vm.runInContext('open(1)', win);
  eq(probes, 1, '同应用只探活一次');
});

t('「重试」重新探活：先失败后成功 → 收起提示并嵌板端', () => {
  let n = 0;
  const win = loadShell(null, { then(onOk, onErr) { (n++ ? onOk : onErr)({}); } });
  vm.runInContext('open(1)', win);
  eq(registry.err.hidden, false, '首次应弹提示');
  if (typeof registry.retry.onclick !== 'function') throw new Error('retry.onclick 未挂');
  registry.retry.onclick.call({});
  eq(registry.err.hidden, true);
  eq(registry.f.hidden, false);
  eq(registry.f.src, 'http://192.168.31.58:8090/', '重试成功后应嵌板端');
});

t('CSS 回归：#err 在 hidden 时必须 display:none（防 #err{display:flex} 盖掉 [hidden]）', () => {
  const css = html.match(/<style>([\s\S]*?)<\/style>/)[1];
  // 简化规则匹配：必须同时存在 #err{...} 和 #err[hidden]{display:none}
  if (!/#err\{[^}]*display:flex/.test(css)) throw new Error('应有 #err{display:flex}');
  if (!/#err\[hidden\]\{display:none/.test(css)) throw new Error('缺 #err[hidden]{display:none}，错误视图会永远盖住 iframe');
});

t('回归：不再靠读 iframe location 判断（跨域必抛 SecurityError，成功/失败无法区分）', () => {
  if (/contentWindow\.location/.test(SRC)) throw new Error('又读回了跨域 location，板端在线时也会误报「不在内网」');
});

t('骨架倒地入口使用本实例端口，缺端口时显示说明而不误连临时服务', () => {
  const win = loadShell('http://127.0.0.1/console.html?replay_port=49001&fall_port=49002');
  const APPS = vm.runInContext('APPS', win);
  const i = APPS.findIndex(a => a.name === '骨架与倒地检测');
  if (i < 0) throw new Error('缺少骨架倒地入口');
  vm.runInContext(`open(${i})`, win);
  eq(registry.f.src, 'http://127.0.0.1:49002/');
  const missing = loadShell();
  vm.runInContext(`open(${i})`, missing);
  eq(registry.f.hidden, true);
  if (!registry.errmsg.textContent.includes('未就绪')) throw new Error('缺数据说明未显示');
});

t('联合录制入口使用本实例端口，缺端口时提示重新打开', () => {
  const win = loadShell('http://127.0.0.1/console.html?replay_port=49001&capture_port=49003');
  const apps = vm.runInContext('APPS', win);
  const i = apps.findIndex(a => a.name === 'USB＋雷达联合录制');
  if (i < 0) throw new Error('缺联合录制入口');
  vm.runInContext(`open(${i})`, win);
  eq(registry.f.src, 'http://127.0.0.1:49003/');
  const missing = loadShell();
  vm.runInContext(`open(${i})`, missing);
  eq(registry.f.hidden, true);
  if (!registry.errmsg.textContent.includes('重新打开')) throw new Error('缺启动提示');
});

t('小目标跟踪入口使用本实例端口，缺端口时提示用仓库内控制台', () => {
  const win = loadShell('http://127.0.0.1/console.html?replay_port=49001&plane_port=49005');
  const apps = vm.runInContext('APPS', win);
  const i = apps.findIndex(a => a.name === '小目标跟踪');
  if (i < 0) throw new Error('缺小目标跟踪入口');
  vm.runInContext(`open(${i})`, win);
  eq(registry.f.src, 'http://127.0.0.1:49005/index.html');
  const missing = loadShell();
  vm.runInContext(`open(${i})`, missing);
  eq(registry.f.hidden, true);
  if (!registry.errmsg.textContent.includes('plane01_pages')) throw new Error('缺 plane01_pages 提示');
});

t('联合录制拉回完成消息 → 强制打开会话回放并带 ?sid', () => {
  const win = loadShell('http://127.0.0.1/console.html?replay_port=49001&capture_port=49003');
  const fire = win.listeners.message[0];
  fire({ origin: 'http://127.0.0.1:49003', data: { type: 'joint-completed', sid: 'cap_20261014_164522' } });
  eq(registry.f.src, 'http://127.0.0.1:49001/?sid=cap_20261014_164522');
  eq(registry.home.classList.contains('on'), false, '应切到应用视图');
  fire({ origin: 'http://127.0.0.1:49003', data: { type: 'joint-completed', sid: 'cap_20261015_010203' } });
  eq(registry.f.src, 'http://127.0.0.1:49001/?sid=cap_20261015_010203', '重复完成消息应重载换到新会话');
});

t('联合录制完成消息：来源/类型/sid 非法一律忽略', () => {
  const win = loadShell('http://127.0.0.1/console.html?replay_port=49001&capture_port=49003');
  const fire = win.listeners.message[0];
  const src0 = registry.f.src, home0 = registry.home.classList.contains('on');
  fire({ origin: 'http://evil.example', data: { type: 'joint-completed', sid: 'joint_x' } });
  fire({ origin: 'http://127.0.0.1:49003', data: { type: 'other', sid: 'joint_x' } });
  fire({ origin: 'http://127.0.0.1:49003', data: { type: 'joint-completed', sid: '../etc' } });
  fire({ origin: 'http://127.0.0.1:49003', data: { type: 'joint-completed', sid: 'a b' } });
  eq(registry.f.src, src0, '不应改 iframe');
  eq(registry.home.classList.contains('on'), home0, '不应切视图');
});

t('“拉回完成→自动打开回放”三处合同一致', () => {
  const jc = fs.readFileSync(path.join(__dirname, 'joint_capture.html'), 'utf8');
  if (!/window\.parent\.postMessage/.test(jc)) throw new Error('联合录制页未向父窗口发消息');
  if (!jc.includes("'joint-completed'")) throw new Error('联合录制页缺 joint-completed 字面量');
  if (!jc.includes('window.parent === window')) throw new Error('联合录制页应仅在控制台内嵌时发送');
  if (!SRC.includes('"joint-completed"')) throw new Error('壳页未监听 joint-completed');
  const replay = fs.readFileSync(path.join(__dirname, '..', 'human_replay', 'index.html'), 'utf8');
  if (!replay.includes('__load_session_sid')) throw new Error('回放页未接 ?sid 自动载入');
  if (!replay.includes('get("sid")')) throw new Error('回放页未读 ?sid');
});

t('学习标注入口使用同实例fall端口和冻结run，缺版本或非法路径不展示', () => {
  const win = loadShell('http://127.0.0.1/console.html?fall_port=49002&learn_run=2026-10-15_hfus_learn_dev_r2');
  const apps = vm.runInContext('APPS', win);
  const i = apps.findIndex(a => a.name === '逐源标注与学习对照');
  if (i < 0) throw new Error('缺版本学习入口');
  vm.runInContext(`open(${i})`, win);
  eq(registry.f.src, 'http://127.0.0.1:49002/learn/2026-10-15_hfus_learn_dev_r2/');
  for (const search of ['fall_port=49002', 'learn_run=valid_run', 'fall_port=49002&learn_run=..%2Fbad']) {
    const missing = loadShell('http://127.0.0.1/console.html?' + search);
    eq(vm.runInContext('APPS.some(a => a.name === "逐源标注与学习对照")', missing), false);
  }
});

t('首页分栏分组：每张卡都有已知 group，卡片不丢不重，栏序 = GROUPS（归档另计）', () => {
  const win = loadShell('http://127.0.0.1/console.html?replay_port=49001&fall_port=49002&capture_port=49003&plane_port=49005&real_fall_port=49006&learn_run=2026-10-15_hfus_learn_dev_r2');
  const APPS = vm.runInContext('APPS', win);
  const GROUPS = vm.runInContext('GROUPS', win);
  for (const a of APPS) {
    if (GROUPS.indexOf(a.group) === -1) throw new Error(a.name + ' 缺合法 group（会从首页消失）');
  }
  const secs = registry.grid.children;
  const visibleSecs = secs.filter(s => s.className === 'group');
  const titles = visibleSecs.map(s => (s.innerHTML.match(/gtitle">([^<]+)</) || [])[1]);
  const expect = GROUPS.filter(g => APPS.some(a => !a.archived && a.group === g));
  eq(titles.join(','), expect.join(','), '可见栏 = 有可见卡片的组，栏序同 GROUPS，空栏不渲染');
  for (const s of visibleSecs) {
    if (s.children[0].className !== 'cards') throw new Error('分组内应是 cards 网格');
    for (const card of s.children[0].children) {
      if (card.className !== 'card' || typeof card.onclick !== 'function') throw new Error('卡片结构/点击未挂');
    }
  }
});

t('归档区：archived 卡片默认折叠、可展开收起，索引/页面/URL 都不变', () => {
  const win = loadShell('http://127.0.0.1/console.html?replay_port=49001&fall_port=49002&real_fall_port=49006&capture_port=49003&plane_port=49005');
  const APPS = vm.runInContext('APPS', win);
  const secs = registry.grid.children;
  const archSec = secs[secs.length - 1];
  eq(archSec.className, 'group archived', '归档区应是最后一栏');
  const toggle = archSec.children[0], cards = archSec.children[1];
  const flagged = APPS.filter(a => a.archived).length;
  if (!flagged) throw new Error('应有归档条目（现在用不到的算法页）');
  eq(cards.children.length, flagged, '归档卡数应等于 archived 标记数');
  eq(cards.hidden, true, '归档区默认折叠');
  if (typeof toggle.onclick !== 'function') throw new Error('归档标题未挂点击');
  toggle.onclick();
  eq(cards.hidden, false, '点标题应展开');
  toggle.onclick();
  eq(cards.hidden, true, '再点应收起');
  const visible = secs.slice(0, -1).reduce((n, s) => n + s.children[0].children.length, 0);
  eq(visible + cards.children.length, APPS.length, '可见 + 归档 = 全部，卡片一个都不能丢');
  // 在用入口不在归档里
  for (const name of ['USB＋雷达联合录制', '会话回放', 'GT 标注', '会话数据库', 'USB 摄像头']) {
    const a = APPS.find(x => x.name === name);
    if (a.archived) throw new Error(name + ' 不该被归档');
  }
  // 归档卡点击仍进对应页（索引未变）
  const i = APPS.findIndex(a => a.name === '算法验证');
  vm.runInContext(`open(${i})`, win);
  eq(registry.f.src, 'http://127.0.0.1:49001/validation.html');
});

t('会话数据库入口指向本实例回放服务的 sessions_db.html，且不影响会话回放=0', () => {
  const win = loadShell('http://127.0.0.1/console.html?replay_port=49001');
  const apps = vm.runInContext('APPS', win);
  eq(apps[0].name, '会话回放', '索引 0 必须仍是会话回放（联合录制 ?sid 自动载入依赖它）');
  const i = apps.findIndex(a => a.name === '会话数据库');
  if (i < 0) throw new Error('缺会话数据库入口');
  eq(apps[i].group, '数据管理');
  vm.runInContext(`open(${i})`, win);
  eq(registry.f.src, 'http://127.0.0.1:49001/sessions_db.html');
});

console.log(`\n${passed} passed, ${failed} failed`);
process.exit(failed ? 1 : 0);
