// ui/Toolbar.tsx — 工具栏：全部核心操作有可见按钮；工具三选一（选择/画框/平移），
// 当前模式高亮可见（规范十一）。
import React from "react";
import type { Tool } from "../viewport2d/interaction.ts";
import type { SessionSummary } from "../session/types.ts";

export interface ToolbarProps {
  tool: Tool;
  setTool(t: Tool): void;
  canUndo: boolean;
  canRedo: boolean;
  onUndo(): void;
  onRedo(): void;
  onSave(): void;
  onReload(): void;
  onExport(): void;
  dirty: boolean;
  annotator: string;
  setAnnotator(v: string): void;
  algoEnabled: boolean;
  setAlgoEnabled(v: boolean): void;
  algoRunning: boolean;
  onRunAlgorithm(): void;
  show3d: boolean;
  setShow3d(v: boolean): void;
  status: { msg: string; err: boolean } | null;
  sessions: SessionSummary[];
  sessionId: string;
  onOpenSession(sid: string): void;
}

export function Toolbar(p: ToolbarProps) {
  return (
    <div className="toolbar">
      <span className="title">点云标注台 v2</span>
      <select
        value={p.sessionId}
        onChange={(e) => p.onOpenSession(e.target.value)}
        title="选择会话"
      >
        <option value="">— 选择会话 —</option>
        {p.sessions.map((s) => (
          <option key={s.sessionId} value={s.sessionId}>
            {s.sessionId}（{s.frameCount} 帧{s.durationSec != null ? ` / ${s.durationSec.toFixed(1)}s` : ""}）
          </option>
        ))}
      </select>
      <span className="sep" />
      <div className="group">
        <button className={p.tool === "select" ? "active" : ""} onClick={() => p.setTool("select")} title="选择/编辑工具">选择</button>
        <button className={p.tool === "draw" ? "active" : ""} onClick={() => p.setTool("draw")} title="画框工具（完成自动回到选择）">画框</button>
        <button className={p.tool === "pan" ? "active" : ""} onClick={() => p.setTool("pan")} title="平移工具（或画布中键拖动）">平移</button>
      </div>
      <span className="sep" />
      <div className="group">
        <button disabled={!p.canUndo} onClick={p.onUndo} title="撤销（Ctrl+Z）">撤销</button>
        <button disabled={!p.canRedo} onClick={p.onRedo} title="重做（Ctrl+Shift+Z）">重做</button>
      </div>
      <span className="sep" />
      <div className="group">
        <button className={p.show3d ? "active" : ""} onClick={() => p.setShow3d(!p.show3d)} title="3D 视图（与 2D 共帧）">3D</button>
      </div>
      <span className="sep" />
      <div className="group">
        <label title="算法建议（与人工标注分开存储，显式采用）">
          <input
            type="checkbox"
            checked={p.algoEnabled}
            onChange={(e) => p.setAlgoEnabled(e.target.checked)}
          />{" "}算法
        </label>
        <button disabled={!p.algoEnabled || p.algoRunning} onClick={p.onRunAlgorithm}>
          {p.algoRunning ? "计算中…" : "当前帧建议"}
        </button>
      </div>
      <span className="spacer" />
      <div className="group">
        <label>标注人</label>
        <input type="text" value={p.annotator} placeholder="你的 ID"
          onChange={(e) => p.setAnnotator(e.target.value)} style={{ width: 90 }} />
      </div>
      <span className="sep" />
      <div className="group">
        <button onClick={p.onSave} className={p.dirty ? "active" : ""} title="原子保存到 gt_store_v2（Ctrl+S 也可，见时间轴提示）">
          保存{p.dirty ? "•" : ""}
        </button>
        <button onClick={p.onReload} title="丢弃本地状态，重载服务器草稿">重载草稿</button>
        <button onClick={p.onExport} title="导出 JSON（浏览器下载）">导出</button>
      </div>
      {p.status && (
        <span className={"status-msg" + (p.status.err ? " err" : "")}>{p.status.msg}</span>
      )}
    </div>
  );
}
