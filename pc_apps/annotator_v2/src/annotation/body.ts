export const PART_LABELS: Record<string, string> = {
  head: '头部', torso: '躯干', upper_arm_1: '上臂 1', forearm_1: '前臂 1',
  upper_arm_2: '上臂 2', forearm_2: '前臂 2', thigh_1: '大腿 1', shin_1: '小腿 1', thigh_2: '大腿 2', shin_2: '小腿 2',
  foot_1: '脚部 1', foot_2: '脚部 2',
};
export const PART_COLORS: Record<string, string> = {
  head: '#ff55cc', torso: '#36ddff', upper_arm_1: '#ff9955', forearm_1: '#ffff55',
  upper_arm_2: '#aa88ff', forearm_2: '#5588ff', thigh_1: '#55ee88', shin_1: '#bbff55', thigh_2: '#ee5555', shin_2: '#dddddd',
  foot_1: '#ff6633', foot_2: '#55bbff',
};
export interface BodyBinding {
  sessionId: string; frameIndex: number; personId: string; rawSha256: string;
  metaSha256: string; pointsSha256: string; calibration: unknown; orientation: string; coordinateFrame: string; units: string;
}
export interface BodyContext {
  binding: BodyBinding; width: number; height: number; sourceIndices: number[]; targetRows: number[];
  trackId: string | null; generation: number; duplicateReturnRows: number[];
}
export interface BodyPart {
  part: string; state: 'visible' | 'occluded' | 'invisible' | 'uncertain'; rect: number[] | null; pixels?: number[];
  origin: { kind: 'human' | 'automatic' | 'propagated'; method: string; uncertainty: string[]; fromBinding?: BodyBinding; derivedFrom?: unknown;
    evidence?: { reason?: string; arcLengthM?: number; terminalTurnDeg?: number; segmentBoundary?: string; [key: string]: unknown } };
  mapping?: { sourceRows: number[]; imagePixels: number[][]; xyz: number[][]; invalidPixels: number; excludedOutsideScope: number;
    representativePoint: number[] | null };
  reasons?: string[];
}
export interface BodyDoc {
  format: 'body_parts_v1'; binding: BodyBinding; scope: Record<string, unknown>; parts: BodyPart[];
  geometry?: { headTorso: { deltaSensorM: number[]; distanceM: number } | null;
    parts: Record<string, { principalAxis: number[] | null; reason: string }>;
    segmentAxisAnglesDeg: Record<string, number>; reason: string };
}
export interface BodyColorSet { part: string; sourceRows: number[]; color: string }

/** Suggestions cannot silently replace manual or propagated labels. Server remaps this union. */
export function mergeBodySuggestions(existing: BodyDoc, suggestion: BodyDoc): BodyDoc {
  if (JSON.stringify(existing.binding) !== JSON.stringify(suggestion.binding)) throw new Error('建议与标注来源不匹配');
  const preserved = existing.parts.filter(part => part.origin.kind !== 'automatic');
  const names = new Set(preserved.map(part => part.part));
  return { ...existing, parts: [...preserved, ...suggestion.parts.filter(part => !names.has(part.part))] };
}

/** Exact source ownership; no XYZ projection, no depth filling. */
export function bodyColors(doc: BodyDoc | null, selected: string): BodyColorSet[] {
  return doc?.parts.filter(p => p.mapping?.sourceRows.length).map(p => ({ part: p.part, sourceRows: p.mapping!.sourceRows,
    color: p.part === selected ? '#ffffff' : PART_COLORS[p.part] ?? '#888888' })) ?? [];
}
export function displayRect(a: number[], b: number[], width: number, height: number): number[] {
  const x0 = Math.max(0, Math.min(width-1, Math.floor(Math.min(a[0]!, b[0]!))));
  const y0 = Math.max(0, Math.min(height-1, Math.floor(Math.min(a[1]!, b[1]!))));
  return [x0, y0, Math.min(width, Math.floor(Math.max(a[0]!, b[0]!))+1), Math.min(height, Math.floor(Math.max(a[1]!, b[1]!))+1)];
}
export function checkBodyBinding(context: BodyContext, sid: string, frame: number, person: string, sha: string | undefined): void {
  const b = context.binding;
  if (b.sessionId !== sid || b.frameIndex !== frame || b.personId !== person || b.rawSha256 !== sha
      || b.orientation !== 'native_grid_rotated_180_for_view' || b.coordinateFrame !== 'sensor-IFW192S-raw' || b.units !== 'm'
      || context.sourceIndices.length !== context.width*context.height) throw new Error('部位距离图绑定不匹配');
}
