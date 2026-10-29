// tests/interaction.test.ts — 规范十五的交互反例验证（DOM 无关状态机层）。
// 反例 6（过期结果）在 loader/algorithm 测试；反例 7（3D）在 threeView 测试；
// 反例 9（算法全关）在 algorithm 测试。
import { describe, expect, it, vi } from "vitest";
import { InteractionController } from "../src/viewport2d/interaction.ts";
import type { InteractionDeps, Tool } from "../src/viewport2d/interaction.ts";
import type { Op } from "../src/annotation/ops.ts";
import type { Box } from "../src/domain/types.ts";
import { mkBox, mkPerson } from "../src/annotation/ops.ts";

// 60px/m 的视图：屏幕 60px = 世界 1m；canvas 800×600。
const SCALE = 60;

function mkHarness(opts: { boxes?: Box[] } = {}) {
  let tool: Tool = "select";
  let selection: string | null = null;
  const committed: Op[] = [];
  const pauses: number[] = [];
  const pans: Array<[number, number]> = [];
  const redraws: number[] = [];
  let targetPerson: string | null = "P1";
  let frameIndex = 7;
  const boxes = opts.boxes ?? [];

  const deps: InteractionDeps = {
    tool: () => tool,
    setTool: (t) => { tool = t; },
    selection: () => selection,
    setSelection: (id) => { selection = id; },
    hitTest: (x, y) => {
      // 世界坐标换算与 App 相同
      const wx = (x - 400) / SCALE;
      const wy = -(y - 300) / SCALE;
      for (let i = boxes.length - 1; i >= 0; i--) {
        const b = boxes[i]!;
        const hx = Math.abs(wx - b.x) <= b.w / 2 + 8 / SCALE;
        const hy = Math.abs(wy - b.y) <= b.h / 2 + 8 / SCALE;
        if (!hx || !hy) continue;
        // 柄命中：接近边线（±8px）
        const nearL = Math.abs(wx - (b.x - b.w / 2)) <= 8 / SCALE;
        const nearR = Math.abs(wx - (b.x + b.w / 2)) <= 8 / SCALE;
        const nearT = Math.abs(wy - (b.y + b.h / 2)) <= 8 / SCALE;
        const nearB = Math.abs(wy - (b.y - b.h / 2)) <= 8 / SCALE;
        if (nearL && nearT) return { boxId: b.boxId, handle: "nw" };
        if (nearR && nearT) return { boxId: b.boxId, handle: "ne" };
        if (nearL && nearB) return { boxId: b.boxId, handle: "sw" };
        if (nearR && nearB) return { boxId: b.boxId, handle: "se" };
        if (nearT || nearB || nearL || nearR) return { boxId: b.boxId, handle: "n" };
        return { boxId: b.boxId, handle: null };
      }
      return null;
    },
    getBox: (id) => boxes.find((b) => b.boxId === id),
    toWorld: (sx, sy) => ({ x: (sx - 400) / SCALE, y: -(sy - 300) / SCALE }),
    drawTargetPersonId: () => targetPerson,
    currentFrameIndex: () => frameIndex,
    metersPerPx: () => 1 / SCALE,
    commitOp: (op) => committed.push(op),
    panBy: (dx, dy) => pans.push([dx, dy]),
    pausePlayback: () => pauses.push(Date.now()),
    requestRedraw: () => redraws.push(Date.now()),
  };
  const c = new InteractionController(deps, 6, 8);
  return {
    c, deps,
    get tool() { return tool; },
    setTool(t: Tool) { tool = t; },
    get selection() { return selection; },
    set selectionSet(v: string | null) { selection = v; },
    get selectionSet() { return selection; },
    committed, pauses, pans, boxes,
    set targetPerson(v: string | null) { targetPerson = v; },
    get frameIndex() { return frameIndex; },
    set frameIndexSet(v: number) { frameIndex = v; },
  };
}

const pd = (x: number, y: number, button = 0) => ({ x, y, button, pointerType: "mouse" });

// 中心 (2, 1)m → 屏幕 (400 + 2*60, 300 - 1*60) = (520, 240)；w=1m=60px, h=0.8m=48px
function centerBox(): Box {
  return mkBox(7, "P1", { x: 2, y: 1, w: 1, h: 0.8 }, { kind: "human" });
}

describe("反例 1：连续画框，每次松手停止并回到选择模式", () => {
  it("两次画框：每次 up 都提交一个框且 tool 回 select", () => {
    const h = mkHarness();
    h.setTool("draw");
    // 第一框
    h.c.pointerDown(pd(200, 200));
    h.c.pointerMove(pd(320, 260)); // 拖出 120×60px = 2×1m
    h.c.pointerUp(pd(320, 260));
    expect(h.committed).toHaveLength(1);
    expect(h.committed[0]!.t).toBe("addBox");
    expect(h.tool).toBe("select"); // 自动回选择
    // 第二框
    h.setTool("draw");
    h.c.pointerDown(pd(400, 300));
    h.c.pointerMove(pd(460, 330));
    h.c.pointerUp(pd(460, 330));
    expect(h.committed).toHaveLength(2);
    expect(h.tool).toBe("select");
    // 松手后继续移动鼠标：无预览、无新提交
    h.c.pointerMove(pd(700, 500));
    h.c.pointerMove(pd(100, 100));
    expect(h.committed).toHaveLength(2);
    expect(h.c.getPreview()).toBeNull();
    expect(h.c.isBusy()).toBe(false);
  });

  it("小于最小拖动距离不创建框（停在画框模式）", () => {
    const h = mkHarness();
    h.setTool("draw");
    h.c.pointerDown(pd(200, 200));
    h.c.pointerMove(pd(203, 202)); // 3px < 6px
    h.c.pointerUp(pd(203, 202));
    expect(h.committed).toHaveLength(0);
    expect(h.tool).toBe("draw"); // 未完成：不切换
    expect(h.c.isBusy()).toBe(false);
  });
});

describe("反例 2：画布外松手，框不跟随鼠标", () => {
  it("移动框拖到画布外坐标松手 → 提交并结束；之后移动无效", () => {
    const box = centerBox();
    const h = mkHarness({ boxes: [box] });
    h.c.pointerDown(pd(520, 240)); // 框体
    h.c.pointerMove(pd(900, -50)); // 拖出画布（捕获保证仍收到 up）
    expect(h.c.getPreview()?.kind).toBe("moveBox");
    h.c.pointerUp(pd(900, -50));
    expect(h.committed).toHaveLength(1);
    expect(h.committed[0]).toMatchObject({ t: "updateBox", boxId: box.boxId });
    // 移回画布再动：不跟随
    h.c.pointerMove(pd(100, 100));
    h.c.pointerMove(pd(520, 240));
    expect(h.committed).toHaveLength(1);
    expect(h.c.isBusy()).toBe(false);
  });
});

describe("反例 3：拖动中切帧/失焦/取消 → 状态清理", () => {
  it.each([
    ["切帧 interrupt", (h: ReturnType<typeof mkHarness>) => h.c.interrupt()],
    ["失焦 externalCancel", (h: ReturnType<typeof mkHarness>) => h.c.externalCancel()],
    ["pointercancel", (h: ReturnType<typeof mkHarness>) => h.c.pointerCancel()],
    ["lostpointercapture", (h: ReturnType<typeof mkHarness>) => h.c.lostPointerCapture()],
  ])("%s：移动中打断 → 无提交、无预览、非编辑态", (_name, interrupt) => {
    const box = centerBox();
    const h = mkHarness({ boxes: [box] });
    h.c.pointerDown(pd(520, 240));
    expect(h.pauses).toHaveLength(1); // 编辑开始即暂停（反例 8 前半）
    h.c.pointerMove(pd(600, 300));
    expect(h.c.getPreview()).not.toBeNull();
    interrupt(h);
    expect(h.committed).toHaveLength(0); // 不提交半途编辑
    expect(h.c.getPreview()).toBeNull();
    expect(h.c.editingActive).toBe(false);
    expect(h.c.isBusy()).toBe(false);
  });

  it("画框中切帧 → 取消，不建框", () => {
    const h = mkHarness();
    h.setTool("draw");
    h.c.pointerDown(pd(200, 200));
    h.c.pointerMove(pd(300, 300));
    h.c.interrupt();
    expect(h.committed).toHaveLength(0);
    expect(h.tool).toBe("draw"); // 工具本身不因切帧切换
    expect(h.c.isBusy()).toBe(false);
  });
});

describe("反例 4：调柄只改大小，不同时移动或平移", () => {
  it("se 柄拖动：对侧边固定、无 pan、几何按新尺寸重定中心", () => {
    const box = centerBox(); // (2,1) 1×0.8m：x∈[1.5,2.5], y∈[0.6,1.4]
    const h = mkHarness({ boxes: [box] });
    const seX = 400 + 2.5 * SCALE;   // 550
    const seY = 300 - 0.6 * SCALE;   // 264
    h.c.pointerDown(pd(seX, seY)); // se 柄
    expect(h.selection).toBe(box.boxId);
    // 拖到世界 (2.0, 1.1)：屏幕 (520, 234) → 宽 1.5→2.0 = 0.5，高 0.6→1.4 = 0.8？y0=1.1 → h=0.3
    h.c.pointerMove(pd(seX - 30, seY - 30));
    const preview = h.c.getPreview();
    expect(preview?.kind).toBe("resizeBox");
    if (preview?.kind === "resizeBox") {
      // 左/上边固定：x0=1.5, y1=1.4
      expect(preview.geom.w).toBeCloseTo(0.5, 5);
      expect(preview.geom.h).toBeCloseTo(0.3, 5);
      expect(preview.geom.x).toBeCloseTo(1.75, 5);
      expect(preview.geom.y).toBeCloseTo(1.25, 5);
    }
    expect(h.pans).toHaveLength(0); // 不平移画布
    h.c.pointerUp(pd(seX - 30, seY - 30));
    expect(h.committed).toHaveLength(1);
    expect(h.committed[0]).toMatchObject({ t: "updateBox" });
    if (h.committed[0]!.t === "updateBox") {
      expect(h.committed[0]!.patch.w).toBeCloseTo(0.5, 5);
      expect(h.committed[0]!.patch.h).toBeCloseTo(0.3, 5);
    }
    expect(h.pans).toHaveLength(0);
  });

  it("柄优先于框体：点框角命中柄而非体", () => {
    const box = centerBox();
    const h = mkHarness({ boxes: [box] });
    const hit = h.deps.hitTest(400 + 2.5 * SCALE, 300 - 1.4 * SCALE);
    expect(hit).toEqual({ boxId: box.boxId, handle: "ne" });
  });
});

describe("反例 5：非画布区域/无效输入不产生 2D 框", () => {
  it("右键不启动手势", () => {
    const h = mkHarness();
    h.setTool("draw");
    h.c.pointerDown(pd(200, 200, 2));
    h.c.pointerMove(pd(400, 400, 2));
    h.c.pointerUp(pd(400, 400, 2));
    expect(h.committed).toHaveLength(0);
  });

  it("画框无目标人物：拒绝起笔", () => {
    const h = mkHarness();
    h.targetPerson = null;
    h.setTool("draw");
    h.c.pointerDown(pd(200, 200));
    h.c.pointerMove(pd(400, 400));
    h.c.pointerUp(pd(400, 400));
    expect(h.committed).toHaveLength(0);
    expect(h.pauses).toHaveLength(0); // 没进入编辑
  });

  it("控制器只由画布事件驱动：状态机本身不监听任何全局输入（结构性）", () => {
    // InteractionController 无 addEventListener/DOM 依赖——若未来引入全局监听，
    // 该构造测试在 node 下会因缺 DOM 而失败，天然拦截。
    const h = mkHarness();
    expect(() => new InteractionController(h.deps)).not.toThrow();
  });
});

describe("反例 8：编辑暂停播放 + 拖动单次提交", () => {
  it("拖动开始即暂停；整个拖动只产生一次提交（一条撤销记录）", () => {
    const box = centerBox();
    const h = mkHarness({ boxes: [box] });
    h.c.pointerDown(pd(520, 240));
    for (let i = 1; i <= 50; i++) h.c.pointerMove(pd(520 + i * 3, 240 + i * 2));
    h.c.pointerUp(pd(520 + 150, 240 + 100));
    expect(h.pauses).toHaveLength(1);
    expect(h.committed).toHaveLength(1); // 50 次 move 只换一次提交
    if (h.committed[0]!.t === "updateBox") {
      expect(h.committed[0]!.patch.x).toBeCloseTo(2 + 150 / SCALE, 5);
      expect(h.committed[0]!.patch.y).toBeCloseTo(1 - 100 / SCALE, 5);
    }
  });

  it("调柄同样单次提交、单次暂停", () => {
    const box = centerBox();
    const h = mkHarness({ boxes: [box] });
    const nwX = 400 + 1.5 * SCALE, nwY = 300 - 1.4 * SCALE;
    h.c.pointerDown(pd(nwX, nwY));
    for (let i = 1; i <= 30; i++) h.c.pointerMove(pd(nwX - i, nwY - i));
    h.c.pointerUp(pd(nwX - 30, nwY - 30));
    expect(h.pauses).toHaveLength(1);
    expect(h.committed).toHaveLength(1);
  });
});

describe("选择语义", () => {
  it("空白单击清除选择；单击框体选中", () => {
    const box = centerBox();
    const h = mkHarness({ boxes: [box] });
    h.selectionSet = box.boxId;
    h.c.pointerDown(pd(100, 100));
    h.c.pointerUp(pd(100, 100));
    expect(h.selection).toBeNull();
    h.c.pointerDown(pd(520, 240));
    h.c.pointerUp(pd(520, 240));
    expect(h.selection).toBe(box.boxId);
    expect(h.committed).toHaveLength(0); // 单击不产生编辑
  });

  it("中键随时平移（与画框/选择互斥：同一时刻一个手势）", () => {
    const h = mkHarness();
    h.setTool("draw");
    h.c.pointerDown(pd(200, 200, 1)); // 中键
    h.c.pointerMove(pd(260, 240, 1));
    expect(h.pans).toEqual([[60, 40]]);
    expect(h.c.getPreview()).toBeNull(); // 不是画框
    h.c.pointerUp(pd(260, 240, 1));
    expect(h.committed).toHaveLength(0);
  });

  it("平移工具左键拖动 → pan；不产生框", () => {
    const h = mkHarness();
    h.setTool("pan");
    h.c.pointerDown(pd(300, 300));
    h.c.pointerMove(pd(340, 320));
    h.c.pointerUp(pd(340, 320));
    expect(h.pans).toEqual([[40, 20]]);
    expect(h.committed).toHaveLength(0);
  });

  it("拖动框未超最小距离 → 不提交位移", () => {
    const box = centerBox();
    const h = mkHarness({ boxes: [box] });
    h.c.pointerDown(pd(520, 240));
    h.c.pointerMove(pd(523, 242)); // 3px
    h.c.pointerUp(pd(523, 242));
    expect(h.committed).toHaveLength(0); // 微动不算编辑
  });
});
