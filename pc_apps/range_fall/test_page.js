/* 页面逻辑冒烟测试：用最小 DOM 桩跑 template.html 内联脚本（run: node test_page.js）。
 * 只验证“不抛异常 / 会绘制 / 状态与报警联动 / 相机缺失降级”，不验证像素外观。 */
'use strict';
const assert = require('assert');
const fs = require('fs');
const path = require('path');

let passed = 0;
function test(name, fn) {
  try { fn(); passed++; console.log('ok   ' + name); }
  catch (err) { console.error('FAIL ' + name + ': ' + err.stack); process.exitCode = 1; }
}

function makeContext() {
  const calls = { fillRect: 0, stroke: 0, fillText: 0, arc: 0, lineTo: 0, fill: 0, setLineDash: 0 };
  const ctx = {
    calls,
    clearRect() {}, fillRect() { calls.fillRect++; }, beginPath() {}, moveTo() {},
    lineTo() { calls.lineTo++; }, stroke() { calls.stroke++; }, fill() { calls.fill++; },
    arc() { calls.arc++; }, fillText() { calls.fillText++; }, setLineDash() { calls.setLineDash++; },
    save() {}, restore() {}, closePath() {},
    fillStyle: '#000', strokeStyle: '#000', lineWidth: 1, font: '', shadowColor: '', shadowBlur: 0
  };
  return ctx;
}

function makeElement(id, tag) {
  const listeners = {};
  const attrs = {};
  const el = {
    id, tagName: tag || 'div', textContent: '', innerHTML: '', className: '', value: '0',
    max: '0', width: 960, height: 640, style: {},
    classList: { add() {}, remove() {} },
    _listeners: listeners,
    addEventListener(type, fn) { (listeners[type] = listeners[type] || []).push(fn); },
    emit(type, event) { (listeners[type] || []).forEach(fn => fn(event || {})); },
    setAttribute(name, value) { attrs[name] = String(value); },
    getAttribute(name) { return attrs[name] === undefined ? null : attrs[name]; },
    removeAttribute(name) { delete attrs[name]; },
    setPointerCapture() {},
    getBoundingClientRect() { return { left: 0, top: 0, width: 1400, height: 150 }; },
    getContext() { return el._ctx || (el._ctx = makeContext()); },
    _attrs: attrs
  };
  return el;
}

function buildDom() {
  const ids = ['cloud', 'chart', 'cam', 'camNote', 'camMeta', 'slider', 'tlabel', 'play',
    'jump', 'reset', 'alarm', 'alarmTitle', 'alarmText', 'metrics', 'sTrack', 'sState', 'sBase'];
  const elements = {};
  ids.forEach(id => { elements[id] = makeElement(id, id === 'cloud' || id === 'chart' ? 'canvas' : 'div'); });
  elements.cloud.width = 960; elements.cloud.height = 640;
  elements.chart.width = 1400; elements.chart.height = 150;
  const document = {
    getElementById(id) { return elements[id] || null; },
    querySelector() { return makeElement('__q'); },
    addEventListener() {}
  };
  const intervals = [];
  const window = {
    FRAMES: [],
    addEventListener(type, fn) { (window._listeners = window._listeners || {}); (window._listeners[type] = window._listeners[type] || []).push(fn); }
  };
  return { document, window, elements, intervals };
}

function loadScript() {
  const html = fs.readFileSync(path.join(__dirname, 'template.html'), 'utf8');
  const blocks = html.match(/<script>([\s\S]*?)<\/script>/g) || [];
  assert.strictEqual(blocks.length, 1, '模板应有且只有一个内联脚本');
  let code = blocks[0].replace(/^<script>/, '').replace(/<\/script>$/, '');
  for (const [name, value] of Object.entries({
    '@@MAX_INDEX@@': '3',
    '@@VIEW@@': JSON.stringify({ yaw: -1.08, pitch: 0.42, dist: 4.8, tx: 1.2, ty: 0.4, tz: 0.9 })
  })) {
    code = code.split(name).join(value);
  }
  assert.ok(!code.includes('@@'), '占位符必须替换完');
  return code;
}

function makeFrames(options) {
  const opts = options || {};
  const frames = [];
  const states = ['unknown', 'descending', 'suspected', 'recovering'];
  for (let i = 0; i < 4; i++) {
    const hasTarget = !opts.empty && i > 0;
    frames.push({
      i, t: i * 0.1, st: states[i],
      rs: i === 0 ? ['target_not_locked'] : (i === 1 ? ['height_dropping'] : ['sustained_low_posture']),
      tid: hasTarget ? 'g0_t0001' : null,
      n: hasTarget ? 12 : 0,
      hm: hasTarget ? 1.1 - i * 0.2 : null,
      ht: hasTarget ? 1.6 : null,
      sp: hasTarget ? 0.8 : null,
      rt: hasTarget ? 0.4 : null,
      vt: hasTarget ? 0.9 : null,
      bb: hasTarget ? [80, 40, 0, 140, 100, 170] : null,
      c: hasTarget ? [110, 70] : null,
      cam: opts.noCamera ? null : [i, -0.02],
      bl: null,
      bg: [0, 0, 0, 100, 0, 100, 200, 50, 150, 150, -50, 20],
      tg: hasTarget ? [90, 50, 30, 110, 70, 120, 130, 90, 60] : []
    });
  }
  return frames;
}

function run(frames) {
  const dom = buildDom();
  dom.window.FRAMES = frames;
  const code = loadScript();
  const runner = new Function('window', 'document', 'setInterval', 'clearInterval', 'console', code);
  const timers = [];
  runner(dom.window, dom.document, (fn) => { timers.push(fn); return timers.length; },
    () => {}, console);
  return { dom, timers };
}

test('脚本加载后停在第 1 个有目标的帧，并写入状态/指标', () => {
  const { dom } = run(makeFrames());
  const cloud = dom.elements.cloud;
  assert.ok(cloud._ctx, '点云画布应拿到 2d 上下文');
  assert.ok(cloud._ctx.calls.fillRect > 0, '点云应有绘制调用');
  assert.ok(cloud._ctx.calls.fillText > 0, '点云 HUD 应有文字');
  assert.ok(dom.elements.chart._ctx.calls.stroke > 0, '时间轴应绘制曲线');
  assert.strictEqual(dom.elements.slider.value, '1', '应停在首个有目标帧');
  assert.strictEqual(dom.elements.sTrack.textContent, 'g0_t0001');
  assert.ok(dom.elements.metrics.innerHTML.includes('目标点数'), '指标卡应有目标点数');
  assert.strictEqual(dom.elements.cam.getAttribute('src'), 'camera/c001.jpg');
  assert.ok(dom.elements.camNote.textContent.includes('接收时刻'));
  assert.ok(!dom.elements.camNote.textContent.includes('无硬件同步'),
    '相机时间差一行不应再带旧括注');
  dom.elements.reset.emit('click');
  assert.strictEqual(dom.elements.slider.value, '0');
  assert.strictEqual(dom.elements.sTrack.textContent, '未锁定');
});

test('第 3 帧（suspected）触发红色报警条与原因码', () => {
  const { dom } = run(makeFrames());
  dom.elements.slider.emit('input', { target: { value: '2' } });
  assert.strictEqual(dom.elements.slider.value, '2');
  assert.ok(dom.elements.alarm.className.includes('hot'), '嫌疑帧应为 hot');
  assert.ok(dom.elements.alarmTitle.textContent.includes('跌倒嫌疑'));
  assert.ok(dom.elements.alarmText.innerHTML.includes('sustained_low_posture'));
  assert.strictEqual(dom.elements.sTrack.textContent, 'g0_t0001');
});

test('“跳到报警”、键盘与播放按钮可用且不越界', () => {
  const { dom, timers } = run(makeFrames());
  dom.elements.jump.emit('click');
  assert.strictEqual(dom.elements.slider.value, '2', '跳到报警应停在首个 suspected 帧');
  dom.window._listeners.keydown.forEach(fn => fn({ key: 'ArrowRight', preventDefault() {} }));
  assert.strictEqual(dom.elements.slider.value, '3');
  dom.window._listeners.keydown.forEach(fn => fn({ key: 'ArrowRight', preventDefault() {} }));
  assert.strictEqual(dom.elements.slider.value, '3', '末帧不应越界');
  dom.window._listeners.keydown.forEach(fn => fn({ key: 'ArrowLeft', preventDefault() {} }));
  assert.strictEqual(dom.elements.slider.value, '2');
  dom.elements.play.emit('click');
  assert.strictEqual(dom.elements.play.textContent, '暂停');
  dom.elements.play.emit('click');
  assert.strictEqual(dom.elements.play.textContent, '播放');
  assert.ok(timers.length >= 1);
});

test('无相机帧时降级为隐藏图片并给出提示', () => {
  const { dom } = run(makeFrames({ noCamera: true }));
  assert.strictEqual(dom.elements.cam.getAttribute('src'), null);
  assert.strictEqual(dom.elements.cam.style.visibility, 'hidden');
  assert.ok(dom.elements.camNote.textContent.includes('没有相机'));
  assert.strictEqual(dom.elements.camMeta.textContent, '无相机');
});

test('全帧无目标时不崩溃，状态显示未知', () => {
  const { dom } = run(makeFrames({ empty: true }));
  assert.ok(dom.elements.sTrack.textContent.includes('未锁定'));
  assert.ok(dom.elements.sState.textContent.includes('未知'));
  assert.strictEqual(dom.elements.jump.emit('click'), undefined);
});

test('滚轮缩放与指针拖拽改变视图后仍可绘制', () => {
  const { dom } = run(makeFrames());
  const cloud = dom.elements.cloud;
  const before = cloud._ctx.calls.lineTo;
  cloud.emit('pointerdown', { clientX: 10, clientY: 10, pointerId: 1 });
  cloud.emit('pointermove', { clientX: 90, clientY: 40 });
  cloud.emit('pointerup', {});
  cloud.emit('wheel', { deltaY: -100, preventDefault() {} });
  cloud.emit('dblclick', {});
  assert.ok(cloud._ctx.calls.lineTo >= before, '拖拽后仍应继续绘制');
  assert.ok(cloud._ctx.calls.stroke > 0);
});

test('点击时间轴按比例跳帧', () => {
  const { dom } = run(makeFrames());
  const chart = dom.elements.chart;
  chart.emit('click', { clientX: 1400, clientY: 20 });
  assert.strictEqual(dom.elements.slider.value, '3');
  chart.emit('click', { clientX: 0, clientY: 20 });
  assert.strictEqual(dom.elements.slider.value, '0');
});

console.log(passed + ' page tests passed');