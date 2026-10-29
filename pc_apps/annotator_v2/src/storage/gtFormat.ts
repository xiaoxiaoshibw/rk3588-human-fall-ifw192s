// storage/gtFormat.ts — 标注文档的序列化边界：外部输入在此校验；
// 旧格式（gt_workbench/1，来自 human_replay/gt_annotator）显式迁移导入，
// 不静默改写字段含义（规范十四）。
import type { AnnotationDoc, Box, Interval, Person, Suggestion } from "../domain/types.ts";
import { emptyDoc } from "../domain/types.ts";
import { validateDoc, hasErrors } from "../domain/validation.ts";

export class FormatError extends Error {
  constructor(message: string) {
    super(message);
    this.name = "FormatError";
  }
}

/** 服务器信封 {version, saved_at, doc} 的解析（GET /api/gt 返回）。 */
export function parseDraftEnvelope(raw: unknown): { version: number; doc: AnnotationDoc | null } {
  if (raw === null || raw === undefined) return { version: 0, doc: null };
  if (typeof raw !== "object") throw new FormatError("draft envelope: not an object");
  const env = raw as Record<string, unknown>;
  const docRaw = env["doc"];
  if (docRaw === null || docRaw === undefined) {
    const v = env["version"];
    return { version: typeof v === "number" ? v : 0, doc: null };
  }
  return { version: num(env["version"], 0), doc: parseV2Doc(docRaw) };
}

/** v2 文档解析：字段级校验，越界/类型错直接抛 FormatError。 */
export function parseV2Doc(raw: unknown): AnnotationDoc {
  if (typeof raw !== "object" || raw === null) throw new FormatError("doc: not an object");
  const r = raw as Record<string, unknown>;
  if (r["format"] !== "gt_annotate") throw new FormatError(`doc.format 应为 gt_annotate，得到 ${String(r["format"])}`);
  const ver = r["formatVersion"];
  if (ver !== 2) throw new FormatError(`不支持的 formatVersion：${String(ver)}（需迁移逻辑）`);
  if (r['coordinateFrame'] !== 'sensor-IFW192S-raw' || r['units'] !== 'm') {
    throw new FormatError('标注文档坐标系或单位不匹配');
  }
  const sessionId = str(r["sessionId"]);
  const frameCount = num(r["frameCount"]);
  const doc: AnnotationDoc = {
    format: "gt_annotate",
    formatVersion: 2,
    sessionId,
    coordinateFrame: "sensor-IFW192S-raw",
    units: "m",
    frameCount,
    annotator: str(r["annotator"], ""),
    persons: arr(r["persons"]).map(parsePerson),
    boxes: arr(r["boxes"]).map(parseBox),
    intervals: arr(r["intervals"]).map(parseInterval),
    suggestions: arr(r["suggestions"]).map(parseSuggestion),
    sampleFrames: arr(r["sampleFrames"])
      .map((v) => num(v, -1))
      .filter((v) => Number.isInteger(v) && v >= 0),
    savedAtMs: r["savedAtMs"] === null || r["savedAtMs"] === undefined ? null : num(r["savedAtMs"]),
  };
  const issues = validateDoc(doc);
  if (hasErrors(issues)) {
    throw new FormatError(`文档校验失败：${issues.filter((i) => i.level === "error").map((i) => i.message).join("；")}`);
  }
  return doc;
}

export function serializeDoc(doc: AnnotationDoc): string {
  return JSON.stringify({ ...doc, savedAtMs: doc.savedAtMs ?? Date.now() });
}

// ---------- v1 (gt_workbench/1) 迁移 ----------
// v1 对象：polygon_xy（俯瞰多边形，米，旧 leveling 坐标）+ class_name + track_id?
// + frame_idx + source(human/model/propagated) + reviewed。迁移为只读导入：
// PERSON 且有 track_id → Person + 外接矩形 Box（origin 保留来源映射）；
// 非 PERSON 对象跳过并计入报告。注意：v1 为 leveled 坐标系，v2 为传感器原始
// 坐标系——坐标含义不同，导入结果标记 warning，由用户人工确认。

export interface V1ImportReport {
  persons: number;
  boxes: number;
  skippedNonPerson: number;
  skippedNoTrack: number;
  warnings: string[];
}

export function importV1Doc(raw: unknown, frameCount: number): { doc: AnnotationDoc; report: V1ImportReport } {
  if (typeof raw !== "object" || raw === null) throw new FormatError("v1: not an object");
  const r = raw as Record<string, unknown>;
  if (r["schema_version"] !== "gt_workbench/1") {
    throw new FormatError(`v1: schema_version 应为 gt_workbench/1，得到 ${String(r["schema_version"])}`);
  }
  const report: V1ImportReport = { persons: 0, boxes: 0, skippedNonPerson: 0, skippedNoTrack: 0, warnings: [] };
  const doc = emptyDoc(str(r["session_id"], "imported-v1"), frameCount, str(r["annotator"], ""));
  const objects = r["objects"];
  if (objects !== undefined && typeof objects === "object" && objects !== null) {
    for (const [objId, ov] of Object.entries(objects as Record<string, unknown>)) {
      if (typeof ov !== "object" || ov === null) continue;
      const o = ov as Record<string, unknown>;
      if (o["class_name"] !== "PERSON") { report.skippedNonPerson += 1; continue; }
      const track = o["track_id"];
      if (typeof track !== "string" || !track) { report.skippedNoTrack += 1; continue; }
      if (!doc.persons.some((p) => p.personId === track)) {
        doc.persons.push({ personId: track, label: null, color: null });
        report.persons += 1;
      }
      const poly = o["polygon_xy"];
      if (!Array.isArray(poly) || poly.length < 3) continue;
      let x0 = Infinity, x1 = -Infinity, y0 = Infinity, y1 = -Infinity;
      let ok = true;
      for (const pt of poly) {
        if (!Array.isArray(pt) || pt.length !== 2 || typeof pt[0] !== "number" || typeof pt[1] !== "number") { ok = false; break; }
        x0 = Math.min(x0, pt[0]); x1 = Math.max(x1, pt[0]);
        y0 = Math.min(y0, pt[1]); y1 = Math.max(y1, pt[1]);
      }
      if (!ok || x1 <= x0 || y1 <= y0) continue;
      const frameIdx = num(o["frame_idx"], 0);
      if (frameIdx < 0 || frameIdx >= frameCount) continue;
      const source = str(o["source"], "human");
      const origin: Box["origin"] = source === "propagated"
        ? { kind: "propagated", fromBoxId: objId }
        : { kind: "human" };
      const box: Box = {
        boxId: newImportedId("box", objId),
        frameIndex: frameIdx,
        personId: track,
        x: (x0 + x1) / 2, y: (y0 + y1) / 2, w: x1 - x0, h: y1 - y0,
        zMin: 0, zMax: 2.5,
        visibility: "visible",
        origin,
        reviewed: o["reviewed"] === true,
        note: `v1 导入 ${objId}`,
        updatedAtMs: 0,
      };
      doc.boxes.push(box);
      report.boxes += 1;
    }
  }
  report.warnings.push("v1 为 leveled 坐标系，v2 为传感器原始坐标系：导入的框位置需要人工核对");
  if (report.skippedNonPerson > 0) report.warnings.push(`跳过非 PERSON 对象 ${report.skippedNonPerson} 个`);
  if (report.skippedNoTrack > 0) report.warnings.push(`跳过无 track_id 的 PERSON 对象 ${report.skippedNoTrack} 个`);
  return { doc, report };
}

function newImportedId(prefix: string, v1Id: string): string {
  return `${prefix}_v1_${v1Id.replace(/[^A-Za-z0-9_.-]/g, "_")}`;
}

// ---------- 原始字段解析 ----------
function str(v: unknown, dflt = ""): string { return typeof v === "string" ? v : dflt; }
function num(v: unknown, dflt = 0): number { return typeof v === "number" && Number.isFinite(v) ? v : dflt; }
function numOrNull(v: unknown): number | null { return typeof v === "number" && Number.isFinite(v) ? v : null; }
function arr(v: unknown): unknown[] { return Array.isArray(v) ? v : []; }
function bool(v: unknown): boolean { return v === true; }

function parsePerson(raw: unknown): Person {
  const r = raw as Record<string, unknown>;
  return {
    personId: str(r["personId"]),
    label: r["label"] === null ? null : str(r["label"], null as unknown as string) || null,
    color: r["color"] === null || r["color"] === undefined ? null : str(r["color"], null as unknown as string) || null,
  };
}

function parseBox(raw: unknown): Box {
  const r = raw as Record<string, unknown>;
  return {
    boxId: str(r["boxId"]),
    frameIndex: num(r["frameIndex"]),
    personId: str(r["personId"]),
    x: num(r["x"]), y: num(r["y"]), w: num(r["w"]), h: num(r["h"]),
    zMin: num(r["zMin"]), zMax: num(r["zMax"]),
    visibility: parseVisibility(r["visibility"]),
    origin: parseOrigin(r["origin"]),
    reviewed: bool(r["reviewed"]),
    note: r["note"] === null ? null : str(r["note"], null as unknown as string) || null,
    updatedAtMs: num(r["updatedAtMs"]),
  };
}

function parseInterval(raw: unknown): Interval {
  const r = raw as Record<string, unknown>;
  return {
    intervalId: str(r["intervalId"]),
    personId: str(r["personId"]),
    kind: r["kind"] === "event" ? "event" : "action",
    label: str(r["label"]),
    startFrame: num(r["startFrame"]),
    endFrame: num(r["endFrame"]),
    origin: parseOrigin(r["origin"]),
    reviewed: bool(r["reviewed"]),
    note: r["note"] === null ? null : str(r["note"], null as unknown as string) || null,
  };
}

function parseSuggestion(raw: unknown): Suggestion {
  const r = raw as Record<string, unknown>;
  const boxRaw = r["box"];
  const intervalRaw = r["interval"];
  return {
    suggestionId: str(r["suggestionId"]),
    algorithm: str(r["algorithm"]),
    paramsHash: str(r["paramsHash"]),
    frameIndex: num(r["frameIndex"]),
    box: (boxRaw && typeof boxRaw === "object") ? {
      x: num((boxRaw as Record<string, unknown>)["x"]),
      y: num((boxRaw as Record<string, unknown>)["y"]),
      w: num((boxRaw as Record<string, unknown>)["w"]),
      h: num((boxRaw as Record<string, unknown>)["h"]),
      zMin: num((boxRaw as Record<string, unknown>)["zMin"]),
      zMax: num((boxRaw as Record<string, unknown>)["zMax"]),
    } : null,
    interval: (intervalRaw && typeof intervalRaw === "object") ? {
      kind: (intervalRaw as Record<string, unknown>)["kind"] === "event" ? "event" : "action",
      label: str((intervalRaw as Record<string, unknown>)["label"]),
      endFrame: num((intervalRaw as Record<string, unknown>)["endFrame"]),
    } : null,
    reason: r["reason"] === null ? null : str(r["reason"], null as unknown as string) || null,
    status: r["status"] === "accepted" ? "accepted" : r["status"] === "rejected" ? "rejected" : "pending",
    adoptedRef: r["adoptedRef"] === null || r["adoptedRef"] === undefined ? null : str(r["adoptedRef"]),
    createdAtMs: num(r["createdAtMs"]),
  };
}

function parseVisibility(v: unknown): Box["visibility"] {
  return v === "partial" || v === "occluded" ? v : "visible";
}

function parseOrigin(v: unknown): Box["origin"] {
  if (typeof v !== "object" || v === null) return { kind: "human" };
  const r = v as Record<string, unknown>;
  if (r["kind"] === "propagated") return { kind: "propagated", fromBoxId: str(r["fromBoxId"]) };
  if (r["kind"] === "adopted") return { kind: "adopted", fromSuggestionId: str(r["fromSuggestionId"]), algorithm: str(r["algorithm"]) };
  return { kind: "human" };
}

export { numOrNull };
