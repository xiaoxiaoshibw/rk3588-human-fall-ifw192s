import { describe, expect, it } from 'vitest';
import { bodyColors, checkBodyBinding, displayRect, mergeBodySuggestions } from '../src/annotation/body.ts';
import type { BodyContext, BodyDoc } from '../src/annotation/body.ts';
import { ThreeView } from '../src/viewport3d/threeView.ts';
import type { Points } from 'three';

describe('body range mapping view contract', () => {
  it('reuses color GPU attributes across region selections and frames', () => {
    const attributes: unknown[] = [];
    const view = new ThreeView({ clientWidth: 200, clientHeight: 300 } as HTMLCanvasElement,
      { makeRenderer: () => ({ render(scene) { attributes.push((scene.children.find(p => p.type === 'Points') as Points).geometry.getAttribute('color')); }, setSize() {}, dispose() {} }) });
    const frame = { sessionId: 's', frameIndex: 0, count: 2, x: new Float32Array([2, 2]), y: new Float32Array(2),
      z: new Float32Array([1.6, 0]), intensity: null, stampSec: 0, generation: 0 };
    view.setFrame(frame); view.renderOnce();
    view.setBodyColors([{ part: 'foot_1', sourceRows: [1], color: '#ffffff' }]); view.renderOnce();
    view.setFrame({ ...frame, frameIndex: 1 }); view.renderOnce();
    expect(attributes[1]).toBe(attributes[0]); expect(attributes[2]).toBe(attributes[0]); view.dispose();
  });
  it('refits when new foot support extends the body, preserves camera on selection alone', () => {
    const positions: number[][] = [];
    const view = new ThreeView({ clientWidth: 200, clientHeight: 300 } as HTMLCanvasElement,
      { makeRenderer: () => ({ render(_scene, camera) { positions.push(camera.position.toArray()); }, setSize() {}, dispose() {} }) });
    view.setFrame({ sessionId: 's', frameIndex: 0, count: 2, x: new Float32Array([2, 2]), y: new Float32Array(2),
      z: new Float32Array([1.6, 0]), intensity: null, stampSec: 0, generation: 0 });
    view.setBodyColors([{ part: 'head', sourceRows: [0], color: '#ff55cc' }], true); view.renderOnce();
    const full = [{ part: 'head', sourceRows: [0], color: '#ff55cc' }, { part: 'foot_1', sourceRows: [1], color: '#ff6633' }];
    view.setBodyColors(full, true); view.renderOnce();
    view.setBodyColors(full.map(p => ({ ...p, color: '#ffffff' })), true); view.renderOnce();
    expect(positions[1]).not.toEqual(positions[0]);
    expect(positions[2]).toEqual(positions[1]); view.dispose();
  });
  it('keeps manual and propagated semantics when refreshing automatic suggestions', () => {
    const binding = { sessionId: 's', frameIndex: 453 };
    const existing = { binding, parts: [{ part: 'head', origin: { kind: 'human' } }, { part: 'shin_1', origin: { kind: 'propagated' } }] } as BodyDoc;
    const suggestion = { binding, parts: [{ part: 'head', origin: { kind: 'automatic' } }, { part: 'torso', origin: { kind: 'automatic' } }] } as BodyDoc;
    const merged = mergeBodySuggestions(existing, suggestion);
    expect(merged.parts.map(p => [p.part, p.origin.kind])).toEqual([['head', 'human'], ['shin_1', 'propagated'], ['torso', 'automatic']]);
    expect(() => mergeBodySuggestions(existing, { ...suggestion, binding: { ...suggestion.binding, frameIndex: 454 } })).toThrow();
  });
  it('clamps zoomed drags to exact half-open image pixels', () => {
    expect(displayRect([20.9, 9.2], [10.1, 2.9], 256, 192)).toEqual([10, 2, 21, 10]);
    expect(displayRect([-10, -20], [300, 300], 256, 192)).toEqual([0, 0, 256, 192]);
  });
  it('rejects old frame, source, orientation, person and dimensions', () => {
    const c = { binding: { sessionId: 's', frameIndex: 453, personId: 'P1', rawSha256: 'abc', orientation: 'native_grid_rotated_180_for_view', coordinateFrame: 'sensor-IFW192S-raw', units: 'm' },
      width: 2, height: 2, sourceIndices: [0, -1, 1, 2] } as BodyContext;
    expect(() => checkBodyBinding(c, 's', 453, 'P1', 'abc')).not.toThrow();
    for (const patch of [{ frameIndex: 454 }, { rawSha256: 'old' }, { orientation: 'native' }, { personId: 'P2' }]) {
      expect(() => checkBodyBinding({ ...c, binding: { ...c.binding, ...patch } }, 's', 453, 'P1', 'abc')).toThrow();
    }
  });
  it('shares exact source rows and selection colors, clears on missing frame', () => {
    const doc = { parts: [{ part: 'head', mapping: { sourceRows: [0] } }, { part: 'torso', mapping: { sourceRows: [1] } }] } as BodyDoc;
    const groups = bodyColors(doc, 'head');
    expect(groups[0]).toEqual({ part: 'head', sourceRows: [0], color: '#ffffff' });
    expect(groups[1]!.sourceRows).toBe(doc.parts[1]!.mapping!.sourceRows);
    const view = new ThreeView({ clientWidth: 100, clientHeight: 100 } as HTMLCanvasElement,
      { makeRenderer: () => ({ render() {}, setSize() {}, dispose() {} }) });
    view.setFrame({ sessionId: 's', frameIndex: 0, count: 2, x: new Float32Array([0, 1]), y: new Float32Array(2), z: new Float32Array(2), intensity: null, stampSec: 0, generation: 0 });
    view.setBodyColors(groups, true);
    expect(() => view.setBodyColors([{ part: 'head', color: '#fff', sourceRows: [2] }])).toThrow();
    view.setFrame(null); expect(view.stats().pointsDrawn).toBe(0);
    expect(bodyColors(null, 'head')).toEqual([]); view.dispose();
  });
});
