'use strict';
const assert = require('assert');
const fs = require('fs');
const path = require('path');
const vm = require('vm');
const root = path.resolve(__dirname, '../..');
for (const name of ['houdao', 'qiandao', 'huanmandiedao', 'jixiedaiwanyao']) {
  const html = fs.readFileSync(path.join(__dirname, name + '.html'), 'utf8');
  const src = path.join(root, 'docs/evidence/2026-10-28_demo_four_sessions', 'replay_' + name);
  const window = {addEventListener() {}};
  vm.runInNewContext(fs.readFileSync(path.join(src, 'data/frames.js'), 'utf8'), {window});
  const frames = window.FRAMES;
  const context = {clearRect(){},fillRect(){},beginPath(){},moveTo(){},lineTo(){},stroke(){},fill(){},arc(){},fillText(){},setLineDash(){}};
  const elements = {};
  function element(id) {
    if (!elements[id]) elements[id] = {style:{}, classList:{add(){},remove(){}}, attrs:{}, listeners:{}, width:960,height:640,
      addEventListener(k,f){this.listeners[k]=f}, getContext(){return context},
      getAttribute(k){return this.attrs[k]},setAttribute(k,v){this.attrs[k]=v},removeAttribute(k){delete this.attrs[k]},
      getBoundingClientRect(){return {left:0,width:960}}, setPointerCapture(){}};
    return elements[id];
  }
  const document = {getElementById:element, querySelector:element};
  const code = html.match(/<script>\s*([\s\S]*?)<\/script>/)[1];
  vm.runInNewContext(code, {window,document,Float32Array,Math,String,Number,parseInt,setInterval(){},clearInterval(){}});
  assert.strictEqual(frames.length, JSON.parse(fs.readFileSync(path.join(src,'SUMMARY.json'))).source.frames);
  for (const id of ['view-default','view-front','view-side','view-top']) element(id).listeners.click();
  for (let i=0; i<frames.length; i++) {
    const frame=frames[i];
    element('slider').listeners.input({target:{value:String(i)}});
    assert.strictEqual(element('sState').textContent, frame.st === 'unknown' ? '动作未知' : ({upright:'直立',descending:'下降中',low_posture_unclassified:'低位（未分类）',suspected:'跌倒嫌疑',confirmed:'确认跌倒',recovering:'恢复中'})[frame.st]);
    assert.strictEqual(element('alarm').className.includes('hot'), ['suspected','confirmed'].includes(frame.st));
    if (frame.cam) {
      const camera = 'camera/c' + String(frame.cam[0]).padStart(3,'0') + '.jpg';
      assert.ok(fs.existsSync(path.join(src,camera)), name + ' frame ' + i);
      assert.ok(element('cam').getAttribute('src').endsWith(camera));
    }
  }
  console.log(name + ': ' + frames.length + ' frames verified');
}
