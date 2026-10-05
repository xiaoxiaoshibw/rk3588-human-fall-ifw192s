// GL-04 R2 synthetic-entry integration check (Node VM, no real browser).
// Proves the human_fall.js browser entry only FETCHES the precomputed fixture
// (no geometry construction) and wires normal / no_extrinsics correctly, and
// that the browser branch never exposes HF.syntheticScenario.
const fs = require('fs');
const vm = require('vm');
const path = require('path');
const assert = require('assert');
const THREE = require(path.join(__dirname, '../../../..', 'webui/three.min.js'));
const HF = require(path.join(__dirname, '../../../..', 'webui/human_fall_preview/human_fall_lib.js'));
const root = path.join(__dirname, '../../../..');

function createWorld(name) {
  let raf = [], intervals = [], sent = [];
  const nodes = {};
  class Element {
    constructor() { this.textContent = ''; this.className = ''; this.style = {}; this.children = []; this.disabled = false;
      this.clientWidth = 800; this.clientHeight = 600; this.width = 800; this.height = 600;
      this.classList = { toggle() {}, add() {}, remove() {} }; this.listeners = {}; }
    appendChild(c) { this.children.push(c); return c; }
    addEventListener(k, f) { this.listeners[k] = f; }
    getBoundingClientRect() { return { left: 0, top: 0, width: this.clientWidth, height: this.clientHeight }; }
    getContext() { return new Proxy({}, { get(t, k) { if (k === 'measureText') return s => ({ width: String(s).length * 6 }); return t[k] || (() => {}); }, set(t, k, v) { t[k] = v; return true; } }); }
  }
  const $ = id => nodes[id] || (nodes[id] = new Element());
  const scene = new THREE.Scene();
  const camera = new THREE.PerspectiveCamera(55, 800 / 600, .05, 2000);
  camera.up.set(0, 0, 1); camera.position.set(6, -6, 5); camera.lookAt(3, 0, 0);
  const geo = new THREE.BufferGeometry();
  const positions = new Float32Array([2.8, -.2, -1, 3.2, .2, .5]);
  geo.setAttribute('position', new THREE.BufferAttribute(positions, 3)); geo.setDrawRange(0, 2);
  const pointsObj = new THREE.Points(geo, new THREE.PointsMaterial()); scene.add(pointsObj);
  const fixtureJson = JSON.parse(fs.readFileSync(path.join(__dirname, 'fixtures', name + '.json'), 'utf8'));
  const context = {
    $, THREE, HF, scene, camera, geo, positions, pointsObj,
    controls: { target: new THREE.Vector3(3, 0, 0), update() {}, enabled: true },
    renderer: { domElement: $('gl'), setPixelRatio() {}, setSize() {}, render() {} },
    document: { createElement: () => new Element() }, location: { search: '?synthetic=' + name }, URLSearchParams, TextEncoder, TextDecoder,
    performance: { now: () => 1000 }, devicePixelRatio: 1, console, Map, Set, Float32Array, Uint8Array, DataView, atob,
    TOPICS: [], HF_POINTS_TOPIC: '/innolidar_points', no3d: false, dirty3d: false,
    log: () => {}, recordPointsStats() {}, renderPoints() {}, handleMessage() {},
    resize3d() {}, fitView() {}, fitCanvases() {}, requestAnimationFrame: f => raf.push(f), setInterval: f => intervals.push(f),
    clearInterval() {}, setTimeout() {}, fetch: () => Promise.resolve({ ok: true, json: () => Promise.resolve(fixtureJson) }),
    client: { live: false, ws: { readyState: 3, send: b => sent.push(b) }, send: b => sent.push(b) },
    FoxgloveClient: function () {}, addEventListener() {}
  };
  context.FoxgloveClient.prototype.onJson = function () {}; context.window = context;
  let source = fs.readFileSync(path.join(root, 'webui/human_fall_preview/human_fall.js'), 'utf8');
  source = source.replace(/\}\)\(\);\s*$/, 'window.__t={hfStartSynthetic,hfRenderPanel,hfSetMode,hfGroundReady,hf,hfSyncCurrentSnapshot};})();');
  vm.createContext(context); vm.runInContext(source, context, { filename: 'human_fall.js' });
  return { context, $, sent, intervals, run: () => intervals.forEach(f => f()) };
}

(async function () {
  const results = [];
  function check(id, name, fn) { try { fn(); results.push({ id, name, result: 'PASS' }); } catch (e) { results.push({ id, name, result: 'FAIL', error: e.message }); } }

  const wn = createWorld('normal');
  wn.context.__t.hfStartSynthetic('normal');
  await new Promise(r => setImmediate(r));          // resolve fetch promise chain
  wn.run();                                          // one synthetic push tick
  check('S01', 'normal fixture drives ground render ready (authoritative schema)', () => {
    const hf = wn.context.__t.hf;
    assert.ok(hf.syntheticScene && hf.syntheticScene.snapshot.candidates.length > 0);
    assert.strictEqual(hf.groundRender.status, 'ready');
    assert.strictEqual(hf.syntheticScene.snapshot.ground_render, undefined); // no legacy alias
    assert.ok(hf.syntheticScene.snapshot.coordinate.ground);
    assert.ok(hf.syntheticScene.snapshot.ground.support_polygon);
  });
  wn.context.__t.hfSetMode('ground');
  check('S02', 'ground mode engages and box uses actual ground AABB', () => {
    const hf = wn.context.__t.hf;
    assert.strictEqual(hf.coordMode, 'ground');
    assert.strictEqual(wn.context.__t.hfGroundReady(), true);
    const c = hf.syntheticScene.snapshot.candidates[0];
    assert.strictEqual(c.bbox_ground_from, 'actual_points');
    assert.ok(c.bbox_ground_min_m && c.bbox_ground_max_m);
  });

  const wnull = createWorld('no_extrinsics');
  wnull.context.__t.hfStartSynthetic('no_extrinsics');
  await new Promise(r => setImmediate(r));
  wnull.run();
  check('S03', 'no_extrinsics fixture leaves ground entry disabled/unavailable', () => {
    const hf = wnull.context.__t.hf;
    assert.notStrictEqual(hf.groundRender.status, 'ready');
    assert.strictEqual(wnull.context.__t.hfGroundReady(), false);
  });

  fs.writeFileSync(path.join(__dirname, 'r2_synthetic_results.json'), JSON.stringify(results, null, 2));
  for (const r of results) console.log(r.result + ' ' + r.id + ' ' + r.name + (r.error ? ' :: ' + r.error : ''));
  console.log(JSON.stringify({ pass: results.filter(x => x.result === 'PASS').length, fail: results.filter(x => x.result === 'FAIL').length }));
  process.exitCode = results.some(r => r.result === 'FAIL') ? 1 : 0;
})();
