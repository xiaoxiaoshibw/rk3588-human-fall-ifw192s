// tests/domain.test.ts — 几何纯函数与文档校验（固定样例即契约样例）。
import { describe, expect, it } from "vitest";
import {
  dragToBox, hitBox, hitHandle, resizeBox, countPointsInBox, displayStride,
  boxToRectPx,
} from "../src/domain/geometry.ts";
import { validateDoc, hasErrors } from "../src/domain/validation.ts";
import { emptyDoc, newId } from "../src/domain/types.ts";
import type { Box } from "../src/domain/types.ts";
import { mkBox, mkPerson, mkInterval } from "../src/annotation/ops.ts";
import { worldToScreen, screenToWorld, zoomAt, panByPx } from "../src/viewport2d/transform.ts";

function boxAt(x: number, y: number, w: number, h: number): Box {
  return mkBox(0, "P1", { x, y, w, h }, { kind: "human" });
}

describe("dragToBox", () => {
  const toWorld = (sx: number, sy: number) => screenToWorld({ cx: 0, cy: 0, scalePxPerM: 60, canvasW: 800, canvasH: 600 }, sx, sy);
  it("规范成正矩形；小于最小尺寸返回 null", () => {
    const g = dragToBox({ x: 400, y: 300 }, { x: 460, y: 240 }, toWorld, 0.1, 0.1);
    expect(g).toEqual({ x: 0.5, y: 0.5, w: 1, h: 1 });
    expect(dragToBox({ x: 400, y: 300 }, { x: 403, y: 300 }, toWorld, 0.1, 0.1)).toBeNull();
  });
});

describe("命中优先级：柄 > 框体 > 背景；后画在上层", () => {
  const t = { cx: 0, cy: 0, scalePxPerM: 60, canvasW: 800, canvasH: 600 };
  const b1 = boxAt(0, 0, 1, 1); // 屏幕 (400±30, 300±30)
  const b2 = boxAt(0.5, 0.5, 1, 1); // 部分覆盖 b1，后画
  const mk = (b: Box) => ({ box: b, rect: boxToRectPx(b, (x, y) => worldToScreen(t, x, y), 1 / 60) });
  it("角点命中柄", () => {
    expect(hitHandle(370, 270, mk(b1).rect, 8)).toBe("nw");
    expect(hitHandle(430, 330, mk(b1).rect, 8)).toBe("se");
    expect(hitHandle(400, 300, mk(b1).rect, 8)).toBeNull(); // 中心不是柄
  });
  it("重叠区返回上层框（b2），柄优先于体", () => {
    const hit = hitBox(400, 300, [mk(b1), mk(b2)], 8);
    expect(hit?.boxId).toBe(b2.boxId);
    // (460,240) = b2 的右上角（世界 (1,1)）：命中 b2 的 ne 柄，不被 b2 体抢走
    const hitHandleRes = hitBox(460, 240, [mk(b1), mk(b2)], 8);
    expect(hitHandleRes?.boxId).toBe(b2.boxId);
    expect(hitHandleRes?.handle).toBe("ne");
  });
  it("空白返回 null", () => {
    expect(hitBox(100, 100, [mk(b1), mk(b2)], 8)).toBeNull();
  });
});

describe("resizeBox", () => {
  it("对侧边固定；最小尺寸钳制", () => {
    const b = boxAt(1, 1, 1, 1); // x∈[0.5,1.5]
    const r = resizeBox(b, "e", { x: 0.6, y: 1 }, 0.1, 0.1); // 向左拉过对侧 → 钳到最小宽
    expect(r.w).toBeCloseTo(0.1, 5);
    expect(r.x).toBeCloseTo(0.55, 5); // 左边 0.5 保持
    const r2 = resizeBox(b, "w", { x: -1, y: 1 }, 0.1, 0.1);
    expect(r2.w).toBeCloseTo(2.5, 5); // 右边 1.5 保持
    expect(r2.x).toBeCloseTo(0.25, 5);
  });
});

describe("统计与抽稀", () => {
  it("countPointsInBox 用完整数组（含 z 过滤）；displayStride 只影响显示", () => {
    const x = new Float32Array([0, 0.1, 5, 0.2, 0.3]);
    const y = new Float32Array([0, 0, 0, 0.1, 0.2]);
    const z = new Float32Array([0.5, 1.5, 1.0, 2.6, 0.9]);
    const box = { x: 0.15, y: 0.1, w: 1, h: 1, zMin: 0, zMax: 2 };
    // 界内点：(0,0,0.5)、(0.1,0,1.5)、(0.3,0.2,0.9)；排除：x=5 越界、z=2.6 超 zMax
    const n = countPointsInBox({ x, y, z }, box);
    expect(n).toBe(3);
  });
  it("displayStride 上限行为", () => {
    expect(displayStride(1000, 5000)).toBe(1);
    expect(displayStride(100000, 12000)).toBe(9);
  });
});

describe("validateDoc", () => {
  it("合法文档 0 error", () => {
    const d = emptyDoc("s", 100, "a");
    d.persons = [mkPerson("P1")];
    d.boxes = [mkBox(3, "P1", { x: 1, y: 1, w: 0.8, h: 0.8 }, { kind: "human" })];
    d.intervals = [mkInterval("P1", "action", "walk", 0, 5)];
    expect(hasErrors(validateDoc(d))).toBe(false);
  });
  it("未知人物 / 帧越界 / 同人同帧双框 / z 倒置均为 error", () => {
    const d = emptyDoc("s", 10, "a");
    d.persons = [mkPerson("P1")];
    const good = mkBox(0, "P1", { x: 0, y: 0, w: 1, h: 1 }, { kind: "human" });
    const dupFrame = mkBox(0, "P1", { x: 1, y: 1, w: 1, h: 1 }, { kind: "human" });
    const outOfRange = mkBox(99, "P1", { x: 0, y: 0, w: 1, h: 1 }, { kind: "human" });
    outOfRange.frameIndex = 10;
    const ghost = mkBox(1, "GHOST", { x: 0, y: 0, w: 1, h: 1 }, { kind: "human" });
    const zBad = mkBox(1, "P1", { x: 0, y: 0, w: 1, h: 1 }, { kind: "human" });
    zBad.zMin = 2; zBad.zMax = 1;
    d.boxes = [good, dupFrame, outOfRange, ghost, zBad];
    const issues = validateDoc(d);
    const codes = issues.filter((i) => i.level === "error").map((i) => i.code);
    expect(codes).toContain("box.person-frame-duplicate");
    expect(codes).toContain("box.frame-range");
    expect(codes).toContain("box.unknown-person");
    expect(codes).toContain("box.z-range");
  });
});

describe("newId", () => {
  it("唯一且带前缀", () => {
    const ids = new Set<string>();
    for (let i = 0; i < 200; i++) ids.add(newId("box"));
    expect(ids.size).toBe(200);
    expect([...ids][0]!.startsWith("box_")).toBe(true);
  });
});

describe("视图变换", () => {
  it("world↔screen 互逆；北向上", () => {
    const t = { cx: 1, cy: 2, scalePxPerM: 60, canvasW: 800, canvasH: 600 };
    const s = worldToScreen(t, 1, 2);
    expect(s).toEqual({ sx: 400, sy: 300 });
    const s2 = worldToScreen(t, 2, 3); // x+1 → 右 60px；y+1 → 上 60px
    expect(s2.sx).toBe(460);
    expect(s2.sy).toBe(240);
    const w = screenToWorld(t, 460, 240);
    expect(w).toEqual({ x: 2, y: 3 });
  });
  it("zoomAt 锚点不动；panByPx 反向", () => {
    const t = { cx: 1, cy: 1, scalePxPerM: 60, canvasW: 800, canvasH: 600 };
    const anchor = screenToWorld(t, 400, 300);
    const z = zoomAt(t, 400, 300, 2);
    expect(screenToWorld(z, 400, 300)).toEqual(anchor);
    expect(z.scalePxPerM).toBe(120);
    const p = panByPx(t, 60, 60); // 右拖 60px → 视野左移 1m
    expect(p.cx).toBeCloseTo(0, 5);
    expect(p.cy).toBeCloseTo(2, 5);
  });
});
