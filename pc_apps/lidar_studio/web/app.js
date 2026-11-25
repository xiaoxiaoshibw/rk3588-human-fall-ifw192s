/**
 * 雷达体态工作台（LiDAR Studio）前端主控制器：
 * - WebSocket 二进制帧接收与控制指令（open/play/pause/seek/step/rate/decimation/mode）
 * - 三屏联动（View3D + View2D + CameraPanel + 右侧分析与时间轴）
 * - 快捷键（Space 播放/暂停、← → 逐帧、1–5 切视角）
 */

import {
  CameraPanel,
  TimelinePanel,
  updateFallAndPosturePanels,
  updateHealthBar,
  updatePhysicalAndTracksPanels,
} from "./panels.js";
import { decodeFramePacket } from "./studio_lib.js";
import { View2D } from "./view2d.js";
import { View3D } from "./view3d.js";

const $ = (id) => document.getElementById(id);

class LidarStudioApp {
  constructor() {
    this.view3d = new View3D($("view3dMount"), $("axisHud"));
    this.view2d = new View2D($("rangeCanvas"), $("rangeOverlay"), $("hoverReadout"));
    this.cameraPanel = new CameraPanel();
    this.timelinePanel = new TimelinePanel(
      $("timelineSlider"),
      $("timelineBands"),
      $("frameReadout"),
      $("tlHoverTip"),
      (frameIdx) => this.seekFrame(frameIdx)
    );

    this.ws = null;
    this.mode = "replay";
    this.sessions = [];
    this.currentSid = null;
    this.playing = false;
    this.lastDecoded = null;
    this.reconnectTimer = null;

    this._bindControls();
    this._bindKeyboard();
    this._init();
  }

  async _init() {
    await this.refreshSessions();
    this.connectWs();
  }

  _bindControls() {
    // 模式切换
    $("modeGroup").addEventListener("click", (ev) => {
      const btn = ev.target.closest("[data-mode]");
      if (!btn) return;
      const targetMode = btn.dataset.mode;
      this.setMode(targetMode);
    });

    $("sessionSelect").addEventListener("change", () => {
      const sid = $("sessionSelect").value;
      if (sid) {
        if (this.mode !== "replay") {
          this.setMode("replay", false);
        }
        this.openSession(sid, 0);
      }
    });

    $("liveStreamSelect").addEventListener("change", () => {
      if (this.mode === "live") {
        const sm = $("liveStreamSelect").value || "json_only";
        this.sendCmd({ cmd: "live_stream_mode", stream_mode: sm });
      }
    });

    $("reloadBtn").addEventListener("click", async () => {
      if (this.mode === "live") {
        this.sendCmd({ cmd: "live_probe" });
      } else {
        await this.refreshSessions();
      }
    });

    $("overlayRetryBtn").addEventListener("click", () => {
      if (this.mode === "live") {
        this.sendCmd({
          cmd: "mode",
          mode: "live",
          stream_mode: $("liveStreamSelect").value || "json_only",
        });
      }
    });

    $("toggleInspectorBtn").addEventListener("click", () => {
      $("inspectorCol").classList.toggle("collapsed");
    });

    // 3D 视角预设
    $("presetGroup").addEventListener("click", (ev) => {
      const btn = ev.target.closest("[data-preset]");
      if (!btn) return;
      this.activatePreset(btn.dataset.preset);
    });

    // 3D 着色模式
    $("colorGroup").addEventListener("click", (ev) => {
      const btn = ev.target.closest("[data-color]");
      if (!btn) return;
      for (const b of $("colorGroup").querySelectorAll(".hud-btn")) {
        b.classList.toggle("active", b === btn);
      }
      const meta = this.view3d.setColorMode(btn.dataset.color);
      $("colorLegendTitle").textContent = meta.title;
      $("colorLegendRange").textContent = meta.range;
      $("colorLegendBar").style.background = meta.bg;
    });

    // 3D 开关
    const bindToggle = (id, fn) => {
      $(id).addEventListener("click", () => {
        const active = $(id).classList.toggle("active");
        fn(active);
      });
    };
    bindToggle("btnFollow", (v) => this.view3d.setFollowTarget(v));
    bindToggle("btnLevel", (v) => {
      this.view3d.setLeveling(v);
      this._updateCoordNote();
    });
    bindToggle("btnSkeleton", (v) => this.view3d.setShowSkeleton(v));
    bindToggle("btnBbox", (v) => this.view3d.setShowBbox(v));
    bindToggle("btnTrail", (v) => this.view3d.setShowTrail(v));

    // 2D 开关
    bindToggle("btnMaskTarget", (v) => this.view2d.setShowTargetMask(v));
    bindToggle("btnMaskRec", (v) => this.view2d.setShowRecoveryMask(v));
    bindToggle("btnMaskSkel", (v) => this.view2d.setShowSkeleton(v));

    // 时间轴播放控制
    $("btnPlay").addEventListener("click", () => this.togglePlay());
    $("btnPrev").addEventListener("click", () => this.stepFrame(-1));
    $("btnNext").addEventListener("click", () => this.stepFrame(1));
    $("rateSelect").addEventListener("change", () => {
      this.sendCmd({ cmd: "rate", rate: Number($("rateSelect").value) });
    });
    $("decimSelect").addEventListener("change", () => {
      this.sendCmd({ cmd: "decimation", decimation: Number($("decimSelect").value) });
    });
  }

  _bindKeyboard() {
    window.addEventListener("keydown", (ev) => {
      const tag = ev.target?.tagName;
      if (tag === "SELECT" || tag === "TEXTAREA") return;
      if (tag === "INPUT" && ev.target.type !== "range") return;

      if (ev.code === "Space") {
        ev.preventDefault();
        if (this.mode === "replay") this.togglePlay();
      } else if (ev.code === "ArrowLeft") {
        ev.preventDefault();
        if (this.mode === "replay") this.stepFrame(-1);
      } else if (ev.code === "ArrowRight") {
        ev.preventDefault();
        if (this.mode === "replay") this.stepFrame(1);
      } else if (ev.key === "1") {
        this.activatePreset("front");
      } else if (ev.key === "2") {
        this.activatePreset("side");
      } else if (ev.key === "3") {
        this.activatePreset("top");
      } else if (ev.key === "4") {
        this.activatePreset("sensor");
      } else if (ev.key === "5") {
        this.activatePreset("free");
      }
    });
  }

  activatePreset(preset) {
    for (const b of $("presetGroup").querySelectorAll(".hud-btn")) {
      b.classList.toggle("active", b.dataset.preset === preset);
    }
    this.view3d.setPreset(preset);
  }

  _updateCoordNote() {
    const plane = this.lastDecoded?.state?.local_range?.ground?.displayPlane;
    if (this.view3d.useLeveling && plane) {
      $("coordNote").textContent = "配平视图（几何拟合 · 非真值）";
    } else {
      $("coordNote").textContent = "原始传感器坐标 / m（未配平）";
    }
  }

  showOverlay({ title, desc, pct = 0, meta = "", showSpinner = true, showRetry = false, showProgress = true }) {
    $("stageOverlay").classList.remove("hidden");
    $("overlayTitle").textContent = title;
    $("overlayDesc").textContent = desc;
    $("overlayMeta").textContent = meta;
    $("overlaySpinner").classList.toggle("hidden", !showSpinner);
    $("overlayRetryBtn").classList.toggle("hidden", !showRetry);
    $("overlayProgressWrap").classList.toggle("hidden", !showProgress);
    $("overlayProgressFill").style.width = `${Math.max(0, Math.min(100, pct))}%`;
  }

  hideOverlay() {
    $("stageOverlay").classList.add("hidden");
  }

  async refreshSessions() {
    try {
      const resp = await fetch("/api/sessions");
      const data = await resp.json();
      this.sessions = data.sessions || [];
      const sel = $("sessionSelect");
      if (!this.sessions.length) {
        sel.innerHTML = `<option value="">未发现可用回放会话</option>`;
        return;
      }
      // 优先把带相机的会话排到显眼位置但保持全量
      sel.innerHTML = this.sessions
        .map((s) => {
          const camTag = s.has_camera ? "📷 " : "";
          const cacheTag = s.cached ? " [缓存]" : "";
          return `<option value="${s.sid}">${camTag}${s.title} · ${s.sid} (${s.frames}帧${cacheTag})</option>`;
        })
        .join("");

      if (!this.currentSid) {
        const preferred =
          this.sessions.find((s) => s.sid === "cap_20261028_houdao") ||
          this.sessions.find((s) => s.has_camera) ||
          this.sessions[0];
        if (preferred) {
          this.currentSid = preferred.sid;
          sel.value = preferred.sid;
        }
      } else {
        sel.value = this.currentSid;
      }
    } catch (err) {
      this.showOverlay({
        title: "会话列表获取失败",
        desc: err.message,
        showSpinner: false,
        showProgress: false,
      });
    }
  }

  connectWs() {
    const proto = location.protocol === "https:" ? "wss:" : "ws:";
    const ws = new WebSocket(`${proto}//${location.host}/ws`);
    ws.binaryType = "arraybuffer";
    this.ws = ws;

    ws.onopen = () => {
      if (this.mode === "replay" && this.currentSid) {
        this.openSession(this.currentSid, 0);
      } else if (this.mode === "live") {
        this.sendCmd({
          cmd: "mode",
          mode: "live",
          stream_mode: $("liveStreamSelect").value || "json_only",
        });
      }
    };

    ws.onmessage = (ev) => {
      if (typeof ev.data === "string") {
        this._handleJsonMsg(JSON.parse(ev.data));
      } else if (ev.data instanceof ArrayBuffer) {
        this._handleBinaryFrame(ev.data);
      }
    };

    ws.onclose = () => {
      clearTimeout(this.reconnectTimer);
      this.reconnectTimer = setTimeout(() => this.connectWs(), 2000);
    };
  }

  sendCmd(obj) {
    if (this.ws && this.ws.readyState === WebSocket.OPEN) {
      this.ws.send(JSON.stringify(obj));
    }
  }

  setMode(targetMode, triggerServer = true) {
    this.mode = targetMode;
    for (const b of $("modeGroup").querySelectorAll(".seg-btn")) {
      b.classList.toggle("active", b.dataset.mode === targetMode);
    }
    const isLive = targetMode === "live";
    $("timelineDock").classList.toggle("hidden", isLive);
    $("sessionSelect").classList.toggle("hidden", isLive);
    $("liveStreamSelect").classList.toggle("hidden", !isLive);

    if (isLive) {
      this.playing = false;
      this.view3d.setTimeline([]);
      this.cameraPanel.startLive();
      if (triggerServer) {
        const streamMode = $("liveStreamSelect").value || "json_only";
        this.showOverlay({
          title: "正在探测板端实时流…",
          desc:
            streamMode === "json_only"
              ? "低带宽纯 JSON 模式：连接 192.168.31.58:8765 (/single_target_live/state) 与相机 :8081"
              : "只读连接 192.168.31.58:8765 与相机 :8081/stream",
          showProgress: false,
        });
        this.sendCmd({ cmd: "mode", mode: "live", stream_mode: streamMode });
      }
    } else {
      this.cameraPanel.stopLive();
      this.hideOverlay();
      if (triggerServer) {
        if (this.currentSid) {
          this.openSession(this.currentSid, 0);
        }
      }
    }
  }

  openSession(sid, initialFrame = 0) {
    this.currentSid = sid;
    this.playing = false;
    this._updatePlayBtn();
    this.cameraPanel.clearCache();
    this.showOverlay({
      title: `正在准备 ${sid}`,
      desc: "首次打开将运行整段背景与 human_physical_v1 推理并写入本地缓存…",
      pct: 5,
      meta: "连接后端…",
    });
    this.sendCmd({
      cmd: "open",
      sid,
      frame: initialFrame,
      decimation: Number($("decimSelect").value || 2),
    });
  }

  togglePlay() {
    if (this.playing) {
      this.sendCmd({ cmd: "pause" });
    } else {
      this.sendCmd({ cmd: "play" });
    }
  }

  stepFrame(delta) {
    this.sendCmd({ cmd: "step", delta });
  }

  seekFrame(frame) {
    this.sendCmd({ cmd: "seek", frame });
  }

  _updatePlayBtn() {
    $("playIcon").textContent = this.playing ? "⏸" : "▶";
    $("btnPlay").innerHTML = `<span id="playIcon">${this.playing ? "⏸" : "▶"}</span> ${this.playing ? "暂停" : "播放"}`;
  }

  _handleJsonMsg(msg) {
    switch (msg.type) {
      case "loading": {
        const pct = msg.total > 0 ? Math.round((msg.current / msg.total) * 100) : 15;
        this.showOverlay({
          title: `正在分析 ${msg.sid}`,
          desc: msg.message || "正在处理…",
          pct,
          meta: `${msg.stage} · ${msg.current} / ${msg.total}`,
        });
        break;
      }
      case "session_ready": {
        this.hideOverlay();
        const summary = msg.summary || {};
        this.view3d.setTimeline(summary.timeline || []);
        this.timelinePanel.setTimeline(summary.timeline || []);
        this.refreshSessions(); // 更新 [缓存] 标记
        break;
      }
      case "playback_state": {
        this.playing = Boolean(msg.playing);
        this._updatePlayBtn();
        break;
      }
      case "live_status": {
        if (this.mode !== "live") break;
        if (!msg.reachable) {
          this.showOverlay({
            title: "板端不可达",
            desc: msg.reason || "192.168.31.58:8765 无响应，实时模式已停止且不造假数据。",
            showSpinner: false,
            showProgress: false,
            showRetry: true,
            meta: `WS: ${msg.board_ws || "ws://192.168.31.58:8765"}`,
          });
        } else if (msg.status === "streaming") {
          this.hideOverlay();
        } else {
          this.showOverlay({
            title: "板端已连接，等待点云帧…",
            desc: msg.reason || "只读订阅 /innolidar_points 中",
            showProgress: false,
          });
        }
        break;
      }
      case "error": {
        this.showOverlay({
          title: "发生错误",
          desc: msg.message || msg.code || "未知错误",
          showSpinner: false,
          showProgress: false,
        });
        break;
      }
    }
  }

  _handleBinaryFrame(buf) {
    try {
      const decoded = decodeFramePacket(buf);
      this.lastDecoded = decoded;
      const st = decoded.state || {};

      if (this.mode === "live") {
        this.hideOverlay();
      }

      this.view3d.updateFrame(decoded);
      this.view2d.updateFrame(decoded);
      this._updateCoordNote();

      $("pointStats").textContent =
        st.stream_mode === "json_only"
          ? `板端纯 JSON（目标 ${st.local_range?.depth?.metadata?.targetPixels ?? 0} 点 · 低带宽）`
          : `${decoded.pointCount} 点 (降采样 1/${decoded.decimation})`;
      updateHealthBar(decoded, this.view3d.currentFps);
      updateFallAndPosturePanels(decoded);
      updatePhysicalAndTracksPanels(decoded);

      if (st.mode === "replay") {
        this.timelinePanel.setFrame(st.frame_index ?? 0, st.relative_time_sec ?? 0);
        this.cameraPanel.updateReplayFrame(st.session_id, st.frame_index ?? 0, st.camera);
      }
    } catch (err) {
      console.error("Failed to decode LDSF frame:", err);
    }
  }
}

window.addEventListener("DOMContentLoaded", () => {
  window.__lidarStudio = new LidarStudioApp();
});
