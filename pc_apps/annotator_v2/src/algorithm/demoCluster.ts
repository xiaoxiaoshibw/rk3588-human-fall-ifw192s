// algorithm/demoCluster.ts — 最小可替换算法适配器：俯瞰网格连通域聚成候选框。
// 纯函数 + 确定性参数；结果只是建议，不自动写入人工标注。
import type { AlgorithmAdapter, AlgorithmContext, RawSuggestion } from "./types.ts";

export interface ClusterParams {
  cellSizeM: number;
  minPoints: number;
  maxExtentM: number;
  zMin: number;
  zMax: number;
}

export const DEFAULT_CLUSTER_PARAMS: ClusterParams = {
  cellSizeM: 0.15,
  minPoints: 40,
  maxExtentM: 2.2,
  zMin: 0.1,
  zMax: 2.3,
};

export function paramsHashOf(p: ClusterParams): string {
  return `cell${p.cellSizeM}-min${p.minPoints}-max${p.maxExtentM}-z${p.zMin}-${p.zMax}`;
}

/** 网格连通域（typed array，无对象逐点）。返回外接矩形（世界米）。 */
export function clusterBoxes(
  x: Float32Array, y: Float32Array, z: Float32Array,
  params: ClusterParams = DEFAULT_CLUSTER_PARAMS,
): Array<{ x: number; y: number; w: number; h: number; zMin: number; zMax: number; points: number }> {
  const n = x.length;
  if (n === 0) return [];
  // 1. 高度过滤后的包围盒
  let minX = Infinity, maxX = -Infinity, minY = Infinity, maxY = -Infinity;
  for (let i = 0; i < n; i++) {
    if (z[i]! < params.zMin || z[i]! > params.zMax) continue;
    if (x[i]! < minX) minX = x[i]!;
    if (x[i]! > maxX) maxX = x[i]!;
    if (y[i]! < minY) minY = y[i]!;
    if (y[i]! > maxY) maxY = y[i]!;
  }
  if (!Number.isFinite(minX)) return [];
  const cell = params.cellSizeM;
  const cols = Math.floor((maxX - minX) / cell) + 1;
  const rows = Math.floor((maxY - minY) / cell) + 1;
  if (cols <= 0 || rows <= 0) return [];
  // 2. 网格计数（Int32，避免 Map）
  const grid = new Int32Array(cols * rows);
  for (let i = 0; i < n; i++) {
    if (z[i]! < params.zMin || z[i]! > params.zMax) continue;
    const c = Math.floor((x[i]! - minX) / cell);
    const r = Math.floor((y[i]! - minY) / cell);
    const cellIdx = r * cols + c;
    grid[cellIdx] = (grid[cellIdx] ?? 0) + 1;
  }
  // 3. BFS 连通域（4 邻域，格子数远小于点数）
  const visited = new Uint8Array(cols * rows);
  const queue = new Int32Array(cols * rows);
  const out: ReturnType<typeof clusterBoxes> = [];
  for (let start = 0; start < grid.length; start++) {
    if (visited[start] || grid[start] === 0) continue;
    let head = 0, tail = 0;
    queue[tail++] = start;
    visited[start] = 1;
    let pts = 0, c0 = cols, c1 = -1, r0 = rows, r1 = -1;
    while (head < tail) {
      const cellIdx = queue[head++]!;
      const c = cellIdx % cols, r = (cellIdx - c) / cols;
      pts += grid[cellIdx]!;
      if (c < c0) c0 = c; if (c > c1) c1 = c;
      if (r < r0) r0 = r; if (r > r1) r1 = r;
      // 邻居
      if (c > 0 && !visited[cellIdx - 1] && grid[cellIdx - 1]! > 0) { visited[cellIdx - 1] = 1; queue[tail++] = cellIdx - 1; }
      if (c < cols - 1 && !visited[cellIdx + 1] && grid[cellIdx + 1]! > 0) { visited[cellIdx + 1] = 1; queue[tail++] = cellIdx + 1; }
      if (r > 0 && !visited[cellIdx - cols] && grid[cellIdx - cols]! > 0) { visited[cellIdx - cols] = 1; queue[tail++] = cellIdx - cols; }
      if (r < rows - 1 && !visited[cellIdx + cols] && grid[cellIdx + cols]! > 0) { visited[cellIdx + cols] = 1; queue[tail++] = cellIdx + cols; }
    }
    if (pts < params.minPoints) continue;
    const wx0 = minX + c0 * cell, wx1 = minX + (c1 + 1) * cell;
    const wy0 = minY + r0 * cell, wy1 = minY + (r1 + 1) * cell;
    const w = wx1 - wx0, h = wy1 - wy0;
    if (w > params.maxExtentM || h > params.maxExtentM) continue; // 墙面/大结构不提
    out.push({ x: (wx0 + wx1) / 2, y: (wy0 + wy1) / 2, w, h, zMin: params.zMin, zMax: params.zMax, points: pts });
  }
  out.sort((a, b) => b.points - a.points);
  return out.slice(0, 8);
}

export function makeDemoClusterAdapter(params: ClusterParams = DEFAULT_CLUSTER_PARAMS): AlgorithmAdapter {
  return {
    id: "demo-cluster",
    version: "0.1.0",
    paramsHash: paramsHashOf(params),
    displayName: "演示：俯瞰聚类候选框",
    async run(ctx: AlgorithmContext): Promise<RawSuggestion[]> {
      if (!ctx.frame) return [];
      const clusters = clusterBoxes(ctx.frame.x, ctx.frame.y, ctx.frame.z, params);
      return clusters.map((c) => ({
        kind: "box" as const,
        x: c.x, y: c.y, w: c.w, h: c.h, zMin: c.zMin, zMax: c.zMax,
        reason: `连通域 ${c.points} 点`,
      }));
    },
  };
}
