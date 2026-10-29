// viewport2d/interaction.ts — 指针交互状态机（DOM 无关，可脱离浏览器测试）。
//
// 规范十一的落点：
// - 画框：按下拖动创建、松手完成并回到选择模式；小于最小拖动距离不建框；
//   pointercancel / lostpointercapture / 失焦 / 切帧 / 切工具 → 取消当前操作。
// - 编辑：柄优先于框体、框体优先于背景；只有按住拖动才改框，松手立即停止；
//   拖动期间只出预览，松手一次提交（单条撤销记录）。
// - 平移：平移工具或中键；画框/移动/缩放/平移互斥（同一时刻一个 gesture）。
import type { HandleKind } from "../domain/geometry.ts";
import { dragToBox, resizeBox } from "../domain/geometry.ts";
import type { Box } from "../domain/types.ts";
import type { Op } from "../annotation/ops.ts";
import { mkBox } from "../annotation/ops.ts";

export type Tool = "select" | "draw" | "pan";

export interface PointerEvt {
  x: number; // 画布 CSS 像素
  y: number;
  button: number; // 0 左 1 中 2 右
  pointerType: string; // mouse / pen / touch
}

export interface HitResult {
  boxId: string;
  handle: HandleKind | null;
}

export interface InteractionDeps {
  tool(): Tool;
  setTool(tool: Tool): void;
  selection(): string | null;
  setSelection(boxId: string | null): void;
  /** 供命中与几何换算（柄半径按画布 CSS 像素给）。 */
  hitTest(x: number, y: number): HitResult | null;
  getBox(boxId: string): Box | undefined;
  toWorld(sx: number, sy: number): { x: number; y: number };
  /** 画框的目标人物（当前选中人物或唯一人物）；为空则拒绝起笔。 */
  drawTargetPersonId(): string | null;
  /** 画框落到哪一帧（当前源帧）。 */
  currentFrameIndex(): number;
  /** 当前缩放的米/像素（拖动换算用）。 */
  metersPerPx(): number;
  commitOp(op: Op): void;
  panBy(dxPx: number, dyPx: number): void;
  pausePlayback(): void;
  requestRedraw(): void;
}

export type Preview =
  | { kind: "drawRect"; rectPx: { x: number; y: number; w: number; h: number } }
  | { kind: "moveBox"; boxId: string; geom: { x: number; y: number } }
  | { kind: "resizeBox"; boxId: string; geom: { x: number; y: number; w: number; h: number } }
  | null;

type Gesture =
  | { t: "none" }
  | { t: "drawPending"; startPx: { x: number; y: number }; moved: boolean }
  | { t: "drawing"; startPx: { x: number; y: number }; curPx: { x: number; y: number } }
  | { t: "moving"; boxId: string; startPx: { x: number; y: number }; startGeom: { x: number; y: number }; curPx: { x: number; y: number } }
  | { t: "resizing"; boxId: string; handle: HandleKind; startGeom: Box }
  | { t: "panning"; lastPx: { x: number; y: number } }
  | { t: "maybeEmptyClick"; startPx: { x: number; y: number } };

const MIN_DRAG_PX = 6; // 小于此视为单击，不建框/不移动
const HANDLE_HIT_PX = 8;

export class InteractionController {
  private gesture: Gesture = { t: "none" };
  private preview: Preview = null;
  /** 处于活动 gesture 时为 true：外部据此锁定源帧（规范十一：编辑前暂停）。 */
  editingActive = false;

  constructor(private deps: InteractionDeps, public minDragPx = MIN_DRAG_PX, public handleHitPx = HANDLE_HIT_PX) {}

  getPreview(): Preview { return this.preview; }
  isBusy(): boolean { return this.gesture.t !== "none"; }

  // ---------- 指针事件（由 DOM 层转调） ----------
  pointerDown(e: PointerEvt): void {
    if (this.gesture.t !== "none") return; // 已有 gesture：忽略（互斥）
    // 中键任意工具 → 平移
    if (e.button === 1 || this.deps.tool() === "pan") {
      this.gesture = { t: "panning", lastPx: { x: e.x, y: e.y } };
      this.deps.requestRedraw();
      return;
    }
    if (e.button !== 0) return; // 右键等不启动 gesture
    if (this.deps.tool() === "draw") {
      const personId = this.deps.drawTargetPersonId();
      if (!personId) return; // 无目标人物：不起笔（不产生粘连的半成品）
      this.deps.pausePlayback();
      this.editingActive = true;
      this.gesture = { t: "drawPending", startPx: { x: e.x, y: e.y }, moved: false };
      return;
    }
    // select：命中柄 → resize；命中体 → move；背景 → 记录待空点（用于点击清除选择）
    const hit = this.deps.hitTest(e.x, e.y);
    if (hit && hit.handle) {
      const box = this.deps.getBox(hit.boxId);
      if (!box) return;
      this.deps.pausePlayback();
      this.editingActive = true;
      this.deps.setSelection(hit.boxId);
      this.gesture = { t: "resizing", boxId: hit.boxId, handle: hit.handle, startGeom: { ...box } };
      return;
    }
    if (hit && !hit.handle) {
      const box = this.deps.getBox(hit.boxId);
      if (!box) return;
      this.deps.pausePlayback();
      this.editingActive = true;
      this.deps.setSelection(hit.boxId);
      this.gesture = {
        t: "moving", boxId: hit.boxId,
        startPx: { x: e.x, y: e.y }, startGeom: { x: box.x, y: box.y }, curPx: { x: e.x, y: e.y },
      };
      return;
    }
    this.gesture = { t: "maybeEmptyClick", startPx: { x: e.x, y: e.y } };
  }

  pointerMove(e: PointerEvt): void {
    switch (this.gesture.t) {
      case "drawPending": {
        const d = Math.hypot(e.x - this.gesture.startPx.x, e.y - this.gesture.startPx.y);
        if (d >= this.minDragPx) {
          this.gesture = { t: "drawing", startPx: this.gesture.startPx, curPx: { x: e.x, y: e.y } };
          this.updateDrawPreview(e);
        }
        return;
      }
      case "drawing": {
        this.gesture.curPx = { x: e.x, y: e.y };
        this.updateDrawPreview(e);
        return;
      }
      case "moving": {
        this.gesture.curPx = { x: e.x, y: e.y };
        this.updateMovePreview();
        return;
      }
      case "resizing": {
        this.updateResizePreview(e);
        return;
      }
      case "panning": {
        const dx = e.x - this.gesture.lastPx.x;
        const dy = e.y - this.gesture.lastPx.y;
        this.gesture.lastPx = { x: e.x, y: e.y };
        this.deps.panBy(dx, dy);
        return;
      }
      case "maybeEmptyClick":
      case "none":
        return;
    }
  }

  pointerUp(e: PointerEvt): void {
    switch (this.gesture.t) {
      case "drawing": {
        const geom = dragToBox(this.gesture.startPx, { x: e.x, y: e.y }, this.deps.toWorld);
        if (geom) {
          const personId = this.deps.drawTargetPersonId();
          const box = mkBox(this.deps.currentFrameIndex(), personId ?? "P?", geom, { kind: "human" });
          this.deps.commitOp({ t: "addBox", box });
          this.deps.setSelection(box.boxId);
        }
        // 完成或取消都回到选择模式（规范十一：松开后不继续跟随鼠标）
        this.endGesture();
        this.deps.setTool("select");
        return;
      }
      case "moving": {
        const g = this.gesture;
        const distPx = Math.hypot(e.x - g.startPx.x, e.y - g.startPx.y);
        if (distPx >= this.minDragPx && (g.startGeom.x !== this.moveGeom().x || g.startGeom.y !== this.moveGeom().y)) {
          this.deps.commitOp({ t: "updateBox", boxId: g.boxId, patch: this.moveGeom() });
        }
        this.endGesture();
        return;
      }
      case "resizing": {
        const g = this.gesture;
        const cur = this.deps.getBox(g.boxId);
        const finalGeom = this.preview?.kind === "resizeBox" ? this.preview.geom : null;
        if (finalGeom && cur && geomChanged(g.startGeom, finalGeom)) {
          this.deps.commitOp({ t: "updateBox", boxId: g.boxId, patch: finalGeom });
        }
        this.endGesture();
        return;
      }
      case "panning":
        this.endGesture();
        return;
      case "maybeEmptyClick": {
        // 未拖动且未命中：空白点击清除选择
        const d = Math.hypot(e.x - this.gesture.startPx.x, e.y - this.gesture.startPx.y);
        if (d < this.minDragPx) this.deps.setSelection(null);
        this.endGesture();
        return;
      }
      case "drawPending":
        // 未达到最小拖动距离：不创建无效框；停在画框模式等待下一次拖动
        this.endGesture();
        return;
      case "none":
        return;
    }
  }

  /** pointercancel：浏览器接管/手势被打断 → 丢弃预览，不提交。 */
  pointerCancel(): void {
    this.cancelGesture();
  }

  /** lostpointercapture（非正常 up 路径）→ 取消。 */
  lostPointerCapture(): void {
    this.cancelGesture();
  }

  /** 窗口失焦 / 画布 pointerleave（无捕获时）→ 取消当前操作，不留拖动态。 */
  externalCancel(): void {
    this.cancelGesture();
  }

  /** 切帧 / 切工具由外部调用：任何活动 gesture 立即取消。 */
  interrupt(): void {
    this.cancelGesture();
  }

  private cancelGesture(): void {
    if (this.gesture.t === "none") return;
    this.endGesture();
  }

  private endGesture(): void {
    this.gesture = { t: "none" };
    this.preview = null;
    this.editingActive = false;
    this.deps.requestRedraw();
  }

  private updateDrawPreview(e: PointerEvt): void {
    const g = this.gesture as Extract<Gesture, { t: "drawing" }>;
    const a = this.deps.toWorld(g.startPx.x, g.startPx.y);
    const b = this.deps.toWorld(e.x, e.y);
    const x0 = Math.min(a.x, b.x), x1 = Math.max(a.x, b.x);
    const y0 = Math.min(a.y, b.y), y1 = Math.max(a.y, b.y);
    this.preview = { kind: "drawRect", rectPx: { x: x0, y: y0, w: x1 - x0, h: y1 - y0 } }; // 世界系矩形，由视图换算像素
    this.deps.requestRedraw();
  }

  private moveGeom(): { x: number; y: number } {
    const g = this.gesture as Extract<Gesture, { t: "moving" }>;
    const dxPx = g.curPx.x - g.startPx.x;
    const dyPx = g.curPx.y - g.startPx.y;
    const mPerPx = this.deps.metersPerPx();
    // 屏幕 y 向下 = 世界 y 减小
    return {
      x: g.startGeom.x + dxPx * mPerPx,
      y: g.startGeom.y - dyPx * mPerPx,
    };
  }

  private updateMovePreview(): void {
    const g = this.gesture as Extract<Gesture, { t: "moving" }>;
    this.preview = { kind: "moveBox", boxId: g.boxId, geom: this.moveGeom() };
    this.deps.requestRedraw();
  }

  private updateResizePreview(e: PointerEvt): void {
    const g = this.gesture as Extract<Gesture, { t: "resizing" }>;
    const world = this.deps.toWorld(e.x, e.y);
    const geom = resizeBox(g.startGeom, g.handle, world);
    this.preview = { kind: "resizeBox", boxId: g.boxId, geom };
    this.deps.requestRedraw();
  }
}

function geomChanged(a: { x: number; y: number; w: number; h: number }, b: { x: number; y: number; w: number; h: number }): boolean {
  return a.x !== b.x || a.y !== b.y || a.w !== b.w || a.h !== b.h;
}

/** DOM 绑定层用：把 PointerEvent 翻译成 PointerEvt（clientX/Y → 画布局部坐标）。 */
export function evtFromDom(ev: PointerEvent, rect: DOMRect): PointerEvt {
  return {
    x: ev.clientX - rect.left,
    y: ev.clientY - rect.top,
    button: ev.button,
    pointerType: ev.pointerType,
  };
}

export const HANDLE_HIT_PX_DEFAULT = HANDLE_HIT_PX;
