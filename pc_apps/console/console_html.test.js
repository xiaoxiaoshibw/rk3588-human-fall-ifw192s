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

function loadShell(href) {
  const win = makeWindow(href || 'http://127.0.0.1/console.html?replay_port=8901');
  win.URLSearchParams = URLSearchParams;
  win.Number = Number;
  win.URL = URL;
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

t('内联脚本能 parse 并转移出 <script> 块', () => {
  if (SRC.length < 500) throw new Error('脚本太短，疑似正则不匹配');
});

t('板端 WebUI 带 fail 文案且本地应用不带', () => {
  const win = loadShell();
  const APPS = vm.runInContext('APPS', win);
  if (!APPS[2].fail) throw new Error('板端 WebUI 缺 fail 文案');
  if (APPS[0].fail || APPS[1].fail || APPS[3].fail) throw new Error('本地应用不应有 fail');
});

t('APPS[2] fail 文案 = 当前不在内网', () => {
  const win = loadShell();
  const APPS = vm.runInContext('APPS', win);
  eq(APPS[2].fail, '当前不在内网，无法连接板端 WebUI');
  eq(APPS[0].fail, undefined);
  eq(APPS[1].fail, undefined);
  eq(APPS[3].fail, undefined);
});

t('onload 时若 iframe 有可读 location.host → 视为加载成功，不弹提示', () => {
  const win = loadShell();
  registry.f.contentWindow = { location: { host: '192.168.3.125:8090' } };
  vm.runInContext('open(2)', win);
  eq(registry.err.hidden, true, '应无提示');
  eq(registry.f.hidden, false, 'iframe 应可见');
});

t('onload 时 iframe location 不可读（跨域错误页）→ showErr 弹提示', () => {
  const win = loadShell();
  registry.f.contentWindow = { get location() { throw new Error('cross-origin'); } };
  registry.err.hidden = true;
  vm.runInContext('open(2)', win);
  if (typeof registry.f.onload !== 'function') throw new Error('f.onload 未挂（src 赋值前应先挂 onload）');
  registry.f.onload();
  eq(registry.err.hidden, false, '应弹提示');
  eq(registry.f.hidden, true, 'iframe 应隐藏');
  eq(registry.errmsg.textContent, '当前不在内网，无法连接板端 WebUI');
  eq(registry.errurl.textContent, 'http://192.168.3.125:8090');
});

t('同一导航 onload 重入 → navBan 防重入，不重复弹', () => {
  const win = loadShell();
  registry.f.contentWindow = { get location() { throw new Error('cross-origin'); } };
  registry.err.hidden = true;
  vm.runInContext('open(2)', win);
  registry.f.onload();
  eq(registry.err.hidden, false);        // 首次 fail 已弹
  registry.err.hidden = false;           // 保持触发态可观察（f.onload 已挂，再点也不会再写）
  registry.errmsg.textContent = '';      // 清手动状态，再触发一次看是否被二次写
  registry.f.onload();
  eq(registry.err.hidden, false, '重入不重复弹');
  eq(registry.errmsg.textContent, '', '重入不重写文案');
});

t('无 fail 文案的本地应用即使 location 抛错也不弹提示', () => {
  const win = loadShell();
  registry.f.contentWindow = { get location() { throw new Error('cross-origin'); } };
  registry.err.hidden = true;
  vm.runInContext('open(0)', win);  // 数据标注（本地服务）
  eq(registry.err.hidden, true, '本地应用永不弹提示');
});

t('同一导航内 fail 后再 load 成功页（host 可读）→ 自动收起提示', () => {
  const win = loadShell();
  registry.f.contentWindow = { get location() { throw new Error('cross-origin'); } };
  registry.err.hidden = true;
  vm.runInContext('open(2)', win);
  registry.f.onload();
  eq(registry.err.hidden, false, '已弹提示');
  // 用户点重试/或重新点卡片 → open(i) 里 err.hidden=true f.hidden=false
  // 恢复内网后 load 成功 → host 可读 → 不弹
  registry.err.hidden = true; registry.f.hidden = false;
  registry.f.contentWindow = { location: { host: '192.168.3.125:8090' } };
  registry.f.onload();
  eq(registry.err.hidden, true, '恢复内网后 onload 自动收起');
  eq(registry.f.hidden, false, 'iframe 恢复可见');
});

t('点击「重试」→ 清 navBan + 复位 iframe src', () => {
  const win = loadShell();
  registry.f.contentWindow = { get location() { throw new Error('cross-origin'); } };
  registry.err.hidden = true;
  vm.runInContext('open(2)', win);
  registry.f.src = '';           // 假设错误后 src 被清空
  if (typeof registry.retry.onclick !== 'function') throw new Error('retry.onclick 未挂');
  registry.retry.onclick.call({});
  eq(registry.err.hidden, true);
  eq(registry.f.hidden, false);
  eq(registry.f.src, 'http://192.168.3.125:8090/', '重试应重新指向板端');
});

t('CSS 回归：#err 在 hidden 时必须 display:none（防 #err{display:flex} 盖掉 [hidden]）', () => {
  const css = html.match(/<style>([\s\S]*?)<\/style>/)[1];
  // 简化规则匹配：必须同时存在 #err{...} 和 #err[hidden]{display:none}
  if (!/#err\{[^}]*display:flex/.test(css)) throw new Error('应有 #err{display:flex}');
  if (!/#err\[hidden\]\{display:none/.test(css)) throw new Error('缺 #err[hidden]{display:none}，错误视图会永远盖住 iframe');
});

t('location.host 可读但为空字符串（错误页特征）→ 也弹提示', () => {
  const win = loadShell();
  registry.f.contentWindow = { location: { host: '' } };
  registry.err.hidden = true;
  vm.runInContext('open(2)', win);
  registry.f.onload();
  eq(registry.err.hidden, false, '空 host 应视为错误页');
  eq(registry.f.hidden, true);
  eq(registry.errmsg.textContent, '当前不在内网，无法连接板端 WebUI');
});

console.log(`\n${passed} passed, ${failed} failed`);
process.exit(failed ? 1 : 0);
