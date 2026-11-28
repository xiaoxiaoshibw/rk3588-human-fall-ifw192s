/**
 * 2D 径向距离图视图（192×256 原生分辨率，rotate180 显示，preview_rgb 0.1–8.0 m 色标）。
 * - 叠加目标像素掩码、回收新增点掩码、骨架 imageXY 投影（几何区域，非人体关节）
 * - 鼠标悬停读数：显示行列、原生 (ring, col)、径向距离 (m) 与分类
 */

import {
  FLAG_FOREGROUND,
  FLAG_OTHER_TRACK,
  FLAG_RECOVERY_ADDED,
  FLAG_TARGET_CORE,
  buildPreviewLutRgba,
  displayPixelToNative,
} from "./studio_lib.js";

export class View2D {
  constructor(rangeCanvas, overlayCanvas, readoutEl) {
    this.rangeCanvas = rangeCanvas;
    this.overlayCanvas = overlayCanvas;
    this.readoutEl = readoutEl;
    this.ctxRange = rangeCanvas.getContext("2d");
    this.ctxOverlay = overlayCanvas.getContext("2d");

    this.width = 256;
    this.height = 192;
    this.lut = buildPreviewLutRgba();
    this.imageData = this.ctxRange.createImageData(this.width, this.height);

    this.showTargetMask = true;
    this.showRecoveryMask = true;
    this.showSkeleton = true;

    this.lastFrame = null;
    this.hoverPos = null; // { col, row }
    this._previewB64 = null;
    this._previewImg = null;
    this._previewToken = 0;

    this._bindHover();
  }

  _bindHover() {
    this.overlayCanvas.addEventListener("mousemove", (ev) => {
      const rect = this.overlayCanvas.getBoundingClientRect();
      if (rect.width <= 0 || rect.height <= 0) return;
      const col = Math.floor(((ev.clientX - rect.left) / rect.width) * this.width);
      const row = Math.floor(((ev.clientY - rect.top) / rect.height) * this.height);
      if (col >= 0 && col < this.width && row >= 0 && row < this.height) {
        this.hoverPos = { col, row };
      } else {
        this.hoverPos = null;
      }
      this._renderOverlay();
      this._updateReadout();
    });

    this.overlayCanvas.addEventListener("mouseleave", () => {
      this.hoverPos = null;
      this._renderOverlay();
      this._updateReadout();
    });
  }

  setShowTargetMask(v) {
    this.showTargetMask = Boolean(v);
    this._renderPixels();
  }

  setShowRecoveryMask(v) {
    this.showRecoveryMask = Boolean(v);
    this._renderPixels();
  }

  setShowSkeleton(v) {
    this.showSkeleton = Boolean(v);
    this._renderOverlay();
  }

  updateFrame(decoded) {
    this.lastFrame = decoded;
    if (decoded.rangeWidth > 0 && decoded.rangeHeight > 0) {
      if (decoded.rangeWidth !== this.width || decoded.rangeHeight !== this.height) {
        this.width = decoded.rangeWidth;
        this.height = decoded.rangeHeight;
        this.rangeCanvas.width = this.width;
        this.rangeCanvas.height = this.height;
        this.imageData = this.ctxRange.createImageData(this.width, this.height);
      }
    }
    this._renderPixels();
    this._renderOverlay();
    this._updateReadout();
  }

  _renderPixels() {
    if (!this.lastFrame || !this.lastFrame.rangeMm || this.lastFrame.rangeMm.length === 0) {
      const previewB64 = this.lastFrame?.state?.local_range?.preview || null;
      if (previewB64) {
        if (previewB64 !== this._previewB64) {
          this._previewB64 = previewB64;
          const tok = ++this._previewToken;
          const img = new Image();
          img.onload = () => {
            if (tok !== this._previewToken) return;
            this._previewImg = img;
            this.ctxRange.drawImage(img, 0, 0, this.width, this.height);
          };
          img.src = `data:image/png;base64,${previewB64}`;
        } else if (this._previewImg) {
          this.ctxRange.drawImage(this._previewImg, 0, 0, this.width, this.height);
        }
        return;
      }
      this._previewToken += 1;
      this._previewB64 = null;
      this._previewImg = null;
      this.ctxRange.fillStyle = "#05080d";
      this.ctxRange.fillRect(0, 0, this.width, this.height);
      return;
    }
    this._previewToken += 1;
    this._previewB64 = null;
    this._previewImg = null;

    const rmm = this.lastFrame.rangeMm;
    const rmask = this.lastFrame.rangeMask;
    const out = this.imageData.data;
    const total = this.width * this.height;

    for (let i = 0; i < total; i++) {
      const mm = rmm[i];
      const lutOff = mm * 4;
      let r = this.lut[lutOff];
      let g = this.lut[lutOff + 1];
      let b = this.lut[lutOff + 2];

      if (rmask) {
        const fl = rmask[i];
        if (this.showTargetMask && (fl & FLAG_TARGET_CORE)) {
          r = Math.round(r * 0.35 + 48 * 0.65);
          g = Math.round(g * 0.35 + 245 * 0.65);
          b = Math.round(b * 0.35 + 178 * 0.65);
        } else if (this.showRecoveryMask && (fl & FLAG_RECOVERY_ADDED)) {
          r = Math.round(r * 0.3 + 255 * 0.7);
          g = Math.round(g * 0.3 + 195 * 0.7);
          b = Math.round(b * 0.3 + 45 * 0.7);
        } else if (this.showTargetMask && (fl & FLAG_OTHER_TRACK)) {
          r = Math.round(r * 0.55 + 88 * 0.45);
          g = Math.round(g * 0.55 + 180 * 0.45);
          b = Math.round(b * 0.55 + 255 * 0.45);
        }
      }
      const p = i * 4;
      out[p] = r;
      out[p + 1] = g;
      out[p + 2] = b;
      out[p + 3] = 255;
    }
    this.ctxRange.putImageData(this.imageData, 0, 0);
  }

  _renderOverlay() {
    const ctx = this.ctxOverlay;
    const ow = this.overlayCanvas.width;
    const oh = this.overlayCanvas.height;
    const sx = ow / this.width;
    const sy = oh / this.height;
    ctx.clearRect(0, 0, ow, oh);

    if (this.showSkeleton && this.lastFrame) {
      const skel = (this.lastFrame.state?.local_range?.skeleton) || null;
      if (skel && skel.nodes) {
        ctx.save();
        ctx.lineWidth = 2.0;
        ctx.strokeStyle = "rgba(126, 247, 219, 0.9)";
        for (const [a, b] of skel.edges || []) {
          const na = skel.nodes[a];
          const nb = skel.nodes[b];
          if (!na?.imageXY || !nb?.imageXY) continue;
          ctx.beginPath();
          ctx.moveTo(na.imageXY[0] * sx, na.imageXY[1] * sy);
          ctx.lineTo(nb.imageXY[0] * sx, nb.imageXY[1] * sy);
          ctx.stroke();
        }
        ctx.font = "600 10px 'Cascadia Mono', monospace";
        for (const [name, node] of Object.entries(skel.nodes)) {
          if (!node?.imageXY) continue;
          const px = node.imageXY[0] * sx;
          const py = node.imageXY[1] * sy;
          const isSpine = name === "TOP" || name === "UPPER" || name === "CENTER" || name === "BASE";
          ctx.fillStyle = isSpine ? "#38f5b8" : "#58b4ff";
          ctx.beginPath();
          ctx.arc(px, py, isSpine ? 3.5 : 2.6, 0, Math.PI * 2);
          ctx.fill();
          if (isSpine) {
            ctx.fillStyle = "rgba(255,255,255,0.9)";
            ctx.fillText(name, px + 5, py - 3);
          }
        }
        ctx.fillStyle = "rgba(234, 242, 251, 0.72)";
        ctx.font = "10px 'Microsoft YaHei', sans-serif";
        ctx.fillText("骨架投影：几何区域（非关节）", 8, oh - 8);
        ctx.restore();
      }
    }

    if (this.hoverPos) {
      const px = (this.hoverPos.col + 0.5) * sx;
      const py = (this.hoverPos.row + 0.5) * sy;
      ctx.save();
      ctx.strokeStyle = "rgba(255, 255, 255, 0.75)";
      ctx.lineWidth = 1;
      ctx.setLineDash([4, 3]);
      ctx.beginPath();
      ctx.moveTo(px, 0);
      ctx.lineTo(px, oh);
      ctx.moveTo(0, py);
      ctx.lineTo(ow, py);
      ctx.stroke();
      ctx.strokeRect(px - 4, py - 4, 8, 8);
      ctx.restore();
    }
  }

  _updateReadout() {
    if (!this.lastFrame || !this.lastFrame.rangeMm?.length) {
      if (this.lastFrame?.state?.stream_mode === "json_only") {
        const hasPrev = Boolean(this.lastFrame?.state?.local_range?.preview);
        const pairSt = this.lastFrame?.state?.pairing?.status || "matched";
        const msg = hasPrev
          ? "板端纯 JSON 预览图 (192×256 PNG · 低带宽)"
          : pairSt === "invalid_source"
            ? "当前无有效源帧 · 已清空旧预览"
            : "等待当前源帧 2D 预览图 · 不复用旧帧";
        this.readoutEl.innerHTML =
          `<span>${msg}</span>` +
          `<span class="color-scale-mini"><i style="background:#ff3b30"></i>0.1m → <i style="background:#4ade80"></i>4m → <i style="background:#3b82f6"></i>8m</span>`;
        return;
      }
    }
    if (!this.hoverPos || !this.lastFrame || !this.lastFrame.rangeMm?.length) {
      this.readoutEl.innerHTML =
        `<span>悬停距离图查看坐标与距离 (0.1–8.0 m)</span>` +
        `<span class="color-scale-mini"><i style="background:#ff3b30"></i>0.1m → <i style="background:#4ade80"></i>4m → <i style="background:#3b82f6"></i>8m</span>`;
      return;
    }

    const { col, row } = this.hoverPos;
    const nat = displayPixelToNative(col, row, this.width, this.height);
    const idx = row * this.width + col;
    const mm = this.lastFrame.rangeMm[idx] || 0;
    const distTxt = mm > 0 ? `${(mm / 1000).toFixed(3)} m` : "无测量";
    let kindTxt = "背景/无效";
    if (this.lastFrame.rangeMask) {
      const fl = this.lastFrame.rangeMask[idx];
      if (fl & FLAG_TARGET_CORE) kindTxt = "目标核心";
      else if (fl & FLAG_RECOVERY_ADDED) kindTxt = "回收新增";
      else if (fl & FLAG_OTHER_TRACK) kindTxt = "其他轨迹";
      else if (fl & FLAG_FOREGROUND) kindTxt = "前景点";
      else if (mm > 0) kindTxt = "静态背景";
    }
    this.readoutEl.innerHTML =
      `<span>显示(${row},${col}) · 原生(r${nat.nativeRing},c${nat.nativeCol})</span>` +
      `<span>距离 <b>${distTxt}</b> · ${kindTxt}</span>`;
  }
}
