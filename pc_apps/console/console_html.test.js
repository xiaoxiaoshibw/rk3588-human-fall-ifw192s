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
    appendChild() {},
    querySelector(sel) { return registry[sel.slice(1)]; },
  };
}
const registry = {};
for (const id of ['home', 'app', 'f', 'err', 'appname', 'back', 'pop', 'retry', 'errmsg', 'errurl', 'grid']) {
  registry[id] = el(id);
}

function makeWindow(locationHref) {
  const loc = new URL(locationHref);
  return {
    location: loc,
    history: { replaceState(_, __, u) { const x = new URL(u, loc); registry.__hash = x.hash; loc.hash = x.hash; } },
    document: {
      querySelector(sel) {
        if (sel.startsWith('#')) return registry[sel.slice(1)];
        throw new Error('替身不支持选择器 ' + sel);
      },
      createElement() { return { className: '', innerHTML: '', onclick: null }; },
    },
    open() { throw new Error('不应弹窗'); },
  };
}

function loadShell(href, fetchImpl) {
  const win = makeWindow(href || 'http://127.0.0.1/console.html?replay_port=8901');
  win.URLSearchParams = URLSearchParams;
  win.Number = Number;
  win.URL = URL;
  win.fetch = () => fetchImpl || okFetch;
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

console.log(`\n${passed} passed, ${failed} failed`);
process.exit(failed ? 1 : 0);
