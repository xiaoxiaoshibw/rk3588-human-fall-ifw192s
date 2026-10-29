// storage/client.ts — GT 草稿保存/加载（server.py /api/gt）。
// 保存冲突（他人先写）→ SaveConflictError，由 UI 提示后重载；不静默覆盖。
import type { AnnotationDoc } from "../domain/types.ts";
import { parseDraftEnvelope, parseV2Doc } from "./gtFormat.ts";

export class SaveConflictError extends Error {
  currentVersion: number;
  constructor(currentVersion: number) {
    super(`保存冲突：服务器版本已到 ${currentVersion}`);
    this.name = "SaveConflictError";
    this.currentVersion = currentVersion;
  }
}

export class GtClient {
  private version = 0;

  getVersion(): number { return this.version; }

  async load(sessionId: string): Promise<AnnotationDoc | null> {
    const res = await fetch(`/api/gt?sid=${encodeURIComponent(sessionId)}`);
    if (!res.ok) throw new Error(`GET /api/gt → ${res.status}`);
    const env = parseDraftEnvelope(await res.json());
    this.version = env.version;
    return env.doc;
  }

  /** 原子保存：带 baseVersion，409 时抛 SaveConflictError。 */
  async save(doc: AnnotationDoc): Promise<number> {
    const body = JSON.stringify({ baseVersion: this.version, doc: JSON.parse(JSON.stringify(doc)) });
    const res = await fetch(`/api/gt?sid=${encodeURIComponent(doc.sessionId)}`, {
      method: "PUT",
      headers: { "Content-Type": "application/json" },
      body,
    });
    if (res.status === 409) {
      const data = (await res.json()) as { currentVersion?: number };
      throw new SaveConflictError(typeof data.currentVersion === "number" ? data.currentVersion : this.version);
    }
    if (!res.ok) throw new Error(`PUT /api/gt → ${res.status}`);
    const data = (await res.json()) as { version: number };
    this.version = data.version;
    return data.version;
  }

  /** 导出：浏览器下载 JSON（不经服务器）。 */
  exportDownload(doc: AnnotationDoc): void {
    const blob = new Blob([JSON.stringify(doc, null, 2)], { type: "application/json" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = `gt_${doc.sessionId}.json`;
    a.click();
    URL.revokeObjectURL(url);
  }

  /** 从本地 JSON 文件导入（v2 直读；v1 走 importV1Doc 由 UI 处理）。 */
  async importFile(file: File): Promise<AnnotationDoc> {
    const text = await file.text();
    return parseV2Doc(JSON.parse(text));
  }
}
