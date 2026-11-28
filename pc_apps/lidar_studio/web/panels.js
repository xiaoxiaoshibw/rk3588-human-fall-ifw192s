/**
 * 右侧体态/状态/置信面板、顶部健康条、USB 摄像头对照与底部双层时间轴控制器。
 */

import {
  BELIEF_STATE_MAP,
  FALL_STATE_MAP,
  PRIOR_CLASS_MAP,
  clamp,
  translateBeliefState,
  translateFallState,
  translatePairingStatus,
  translatePosture,
  translateReasonCode,
} from "./studio_lib.js";

const $ = (id) => document.getElementById(id);

function fmtM(v) {
  return typeof v === "number" && Number.isFinite(v) ? `${v.toFixed(2)} m` : "—";
}

function fmtNum(v, digits = 2, suffix = "") {
  return typeof v === "number" && Number.isFinite(v) ? `${v.toFixed(digits)}${suffix}` : "—";
}

function setPill(el, text, tone) {
  el.textContent = text;
  el.className = `state-pill ${tone || "muted"}`;
}

function renderChips(container, codes, toneClass) {
  if (!codes || codes.length === 0) {
    container.innerHTML = `<span class="chip">无</span>`;
    return;
  }
  container.innerHTML = codes
    .map((c) => {
      const zh = translateReasonCode(c);
      const isVeto = c.includes("planar") || c.includes("fragment") || c.includes("hanging") || c.includes("veto");
      const isSoft = c.startsWith("soft_");
      const cls = toneClass || (isVeto ? "danger" : isSoft ? "warn" : "ok");
      return `<span class="chip ${cls}" title="${c}">${zh}</span>`;
    })
    .join("");
}

export function updateHealthBar(decoded, fps) {
  const st = decoded.state || {};
  const lr = st.local_range || {};
  const perf = st.performance || {};
  const rt = perf.runtime || {};
  const phys = st.human_physical_v1 || null;

  $("hFps").textContent = fps > 0 ? `${fps.toFixed(1)}` : "—";

  const procMs = perf.process_ms;
  const physMs = rt.physical_total_ms;
  const timingEl = $("hTiming");
  timingEl.textContent = typeof procMs === "number" ? `${procMs.toFixed(1)} ms` : "—";
  const trkMs = rt.instant_tracker_ms ?? rt.tracking_ms;
  timingEl.title = `decode:${fmtNum(rt.decode_ms, 1)}ms · track:${fmtNum(trkMs, 1)}ms · refine:${fmtNum(rt.silent_refine_ms, 1)}ms · phys:${fmtNum(physMs, 1)}ms`;

  const bg = lr.background || {};
  const bgEl = $("hBg");
  if (bg.status === "ready") {
    bgEl.textContent = bg.declaration === "offline_whole_recording_quantile" ? "离线整段(非因果)" : "已就绪";
    bgEl.className = "hc-v ok";
  } else if (bg.status === "adaptive_ready") {
    bgEl.textContent = "免空场自适应";
    bgEl.className = "hc-v ok";
  } else if (bg.status === "prefix_warmup") {
    bgEl.textContent = "空场学习中…";
    bgEl.className = "hc-v warn";
  } else {
    bgEl.textContent = bg.status === "background_not_declared"
      ? "未声明(只读)"
      : bg.status === "awaiting_board_state"
      ? "等待同帧结果"
      : (bg.status || "未声明");
    bgEl.className = "hc-v warn";
  }

  const gr = lr.ground || {};
  const grEl = $("hGround");
  grEl.title = gr.reason || "";
  if (gr.refinementStage === "refined_plane") {
    grEl.textContent = "后台精修(非真值)";
    grEl.className = "hc-v ok";
  } else if (gr.refinementStage === "foot_anchored") {
    grEl.textContent = "脚底锚定(非真值)";
    grEl.className = "hc-v ok";
  } else if (gr.refinementStage === "gravity_only") {
    grEl.textContent = gr.gravitySource === "imu_static_gravity" ? "IMU重力配平(精修中…)" : "标称重力配平(精修中…)";
    grEl.className = "hc-v warn";
  } else if (gr.available) {
    grEl.textContent = "几何已拟合(非真值)";
    grEl.className = "hc-v ok";
  } else {
    grEl.textContent = gr.reason === "not_declared_in_readonly_live_mode" ? "未声明" : (gr.displayPlane ? "遮挡(配平保留)" : "不可用");
    grEl.className = "hc-v warn";
  }

  const evalEl = $("hEval");
  if (!phys) {
    evalEl.textContent = "未启用";
    evalEl.className = "hc-v";
  } else if (phys.status === "awaiting_ground_offset") {
    evalEl.textContent = "等待精修零点";
    evalEl.className = "hc-v warn";
  } else {
    const errs = phys.error_codes || [];
    evalEl.textContent = errs.length ? `${phys.status} (${errs.join(",")})` : `${phys.status}`;
    evalEl.className = `hc-v ${phys.status === "ok" ? "ok" : phys.status === "degraded" ? "warn" : "danger"}`;
  }

  const srcEl = $("hSource");
  if (st.mode === "live") {
    const modeTxt = st.stream_mode === "json_only" ? "板端纯JSON" : "板端JSON+点云";
    const pairInfo = translatePairingStatus(st.pairing);
    srcEl.textContent = `${modeTxt} · ${pairInfo.label}`;
  } else if (st.replay_mode === "board_causal") {
    const rmeta = st.replay_metadata || {};
    const imuTag = rmeta.imu_available ? "含IMU" : `无IMU·标称${rmeta.mount_pitch_deg ?? 26}°`;
    srcEl.textContent = `板端因果回放 (${imuTag})`;
  } else {
    srcEl.textContent = "离线整段研究回放";
  }
}

export function updateFallAndPosturePanels(decoded) {
  const st = decoded.state || {};
  const lr = st.local_range || {};
  const fe = lr.fallEvidence || {};
  const demo = lr.demoFallCandidate || {};
  const post = lr.posture || {};
  const meas = lr.measurement || {};

  // 跌倒状态机（显式区分“上次疑似·当前缺测 / 疑似后失联 / 实测直立恢复”）
  const fallInfo = translateFallState(st.fall_status);
  const obsStatus = fe.observation_status || lr.kinematics?.observation_status || null;
  const lastObsFall = fe.last_observed_fall_state || lr.kinematics?.last_observed_fall_state || null;
  if (st.fall_status === "suspected" && obsStatus === "last_suspected_missing_echo") {
    setPill($("fallStateBadge"), "上次疑似 · 当前缺测", "warn");
  } else if (st.fall_status === "unknown" && (obsStatus === "lost_after_suspected" || lastObsFall === "suspected")) {
    setPill($("fallStateBadge"), "上次疑似 · 当前失联/缺测", "warn");
  } else {
    setPill($("fallStateBadge"), fallInfo.label, fallInfo.tone);
  }

  const demoMap = {
    unavailable: "不可用",
    not_matched: "未匹配",
    pending: `观察累积中 (${fmtNum(demo.durationSec, 2, " s")})`,
    suspected: `持续水平低位 ≥1.5s (${fmtNum(demo.durationSec, 2, " s")})`,
    sustained: `持续水平低位 ≥3.0s (${fmtNum(demo.durationSec, 2, " s")})`,
  };
  $("demoAlertText").textContent = demoMap[demo.state] || demo.state || "—";
  renderChips($("fallReasonChips"), fe.reason_codes || [], fallInfo.tone === "danger" ? "danger" : fallInfo.tone === "warn" ? "warn" : "");

  // 体态卡
  const postInfo = translatePosture(post.state);
  const durTxt = post.durationSec > 0 ? ` · ${post.durationSec.toFixed(1)}s` : "";
  setPill($("postureBadge"), postInfo.label + durTxt, postInfo.tone);

  const hm = lr.heightMedianM;
  const ht = meas.topHeightM;
  const ex = meas.horizontalExtentM;
  const vert = meas.axisVerticality;
  const dr = meas.descentRateMps;

  $("mHeightMed").textContent = fmtM(hm);
  $("gHeightMed").style.width = `${typeof hm === "number" ? clamp((hm / 2.0) * 100, 0, 100) : 0}%`;

  $("mTopHeight").textContent = fmtM(ht);
  $("gTopHeight").style.width = `${typeof ht === "number" ? clamp((ht / 2.2) * 100, 0, 100) : 0}%`;

  $("mHorizExtent").textContent = fmtM(ex);
  $("gHorizExtent").style.width = `${typeof ex === "number" ? clamp((ex / 2.0) * 100, 0, 100) : 0}%`;

  $("mVerticality").textContent = fmtNum(vert, 2);
  $("gVerticality").style.width = `${typeof vert === "number" ? clamp(vert * 100, 0, 100) : 0}%`;

  $("mDescentRate").textContent = typeof dr === "number" ? `${dr >= 0 ? "+" : ""}${dr.toFixed(2)} m/s` : "—";
  const biEl = $("gDescentRate");
  if (typeof dr === "number" && Number.isFinite(dr)) {
    const mag = clamp(Math.abs(dr) / 1.5, 0, 1) * 50;
    if (dr >= 0) {
      biEl.style.left = "50%";
      biEl.style.width = `${mag}%`;
      biEl.style.background = "#38d9a9";
    } else {
      biEl.style.left = `${50 - mag}%`;
      biEl.style.width = `${mag}%`;
      biEl.style.background = dr <= -0.35 ? "#ff5c6c" : "#f5b942";
    }
  } else {
    biEl.style.width = "0%";
  }
}

export function updatePhysicalAndTracksPanels(decoded) {
  const st = decoded.state || {};
  const phys = st.human_physical_v1;
  const tracks = st.diagnostics?.tracking?.tracks || [];
  const targetTid = st.track_id;

  if (!phys) {
    setPill($("beliefBadge"), "未启用", "muted");
    $("loValueText").textContent = "—";
    $("loPointer").style.left = "54.54%";
    $("loFill").style.width = "0%";
    $("loDeltas").textContent = "Δ几何 — · Δ法向 — · Δ运动 —";
    $("kinFloorText").textContent = "未启用";
    $("recoveryText").textContent = "未启用";
    renderChips($("physEvidenceChips"), [], "ok");
    renderChips($("physRejectChips"), [], "danger");
  } else {
    const tb = phys.target_belief;
    const targetDetail = targetTid ? phys.tracks?.[targetTid] : null;
    const bState = tb ? tb.belief_state : "NONE";
    const bInfo = translateBeliefState(bState);
    setPill($("beliefBadge"), bInfo.label, bInfo.tone);

    if (tb) {
      const lo = clamp(Number(tb.log_odds || 0), -6.0, 5.0);
      const pct = ((lo + 6.0) / 11.0) * 100;
      const zeroPct = (6.0 / 11.0) * 100;
      $("loValueText").textContent = `${lo.toFixed(2)} (p=${(tb.belief_score ?? 0.5).toFixed(2)})${tb.veto_active ? " · 否决封顶" : ""}`;
      $("loPointer").style.left = `${pct}%`;

      const fillEl = $("loFill");
      if (pct >= zeroPct) {
        fillEl.style.left = `${zeroPct}%`;
        fillEl.style.width = `${pct - zeroPct}%`;
        fillEl.style.background = bInfo.color;
      } else {
        fillEl.style.left = `${pct}%`;
        fillEl.style.width = `${zeroPct - pct}%`;
        fillEl.style.background = "#ff5c6c";
      }

      const d = tb.deltas || {};
      $("loDeltas").textContent =
        `Δ几何 ${d.geom >= 0 ? "+" : ""}${fmtNum(d.geom, 2)} · Δ法向 ${d.normal >= 0 ? "+" : ""}${fmtNum(d.normal, 2)} · Δ运动 ${d.kin >= 0 ? "+" : ""}${fmtNum(d.kin, 2)}`;

      const evCodes = [...(tb.evidence_codes || [])];
      if (targetDetail?.prior?.class) {
        const pCls = targetDetail.prior.class;
        if (pCls in PRIOR_CLASS_MAP && !evCodes.length) {
          evCodes.push(pCls);
        }
      }
      renderChips($("physEvidenceChips"), tb.evidence_codes || [], "ok");

      const rejList = [...(tb.rejection_reasons || [])];
      for (const prRej of targetDetail?.prior?.rejection_reasons || []) {
        if (!rejList.includes(prRej)) rejList.push(prRej);
      }
      renderChips($("physRejectChips"), rejList);
    } else {
      $("loValueText").textContent = "当前无目标";
      $("loPointer").style.left = "54.54%";
      $("loFill").style.width = "0%";
      $("loDeltas").textContent = "Δ几何 — · Δ法向 — · Δ运动 —";
      renderChips($("physEvidenceChips"), [], "ok");
      renderChips($("physRejectChips"), [], "danger");
    }

    // 运动学噪声底
    const nf = phys.kinematics_noise_floor || {};
    if (nf.calibrated) {
      $("kinFloorText").textContent = `已标定 (${nf.source || "online"}) · ${fmtNum(nf.ivel_floor_mps, 3)} m/s`;
    } else {
      $("kinFloorText").textContent = `未标定 (样本 ${nf.samples || 0}) · 刚体/非刚体关闭`;
    }

    // 局部回收状态
    const rec = phys.recovery;
    if (!rec) {
      $("recoveryText").textContent = "无目标";
    } else if (rec.status === "recovered") {
      const ng = rec.breakdown?.added_near_ground_count ?? 0;
      $("recoveryText").textContent = `已回收 +${rec.added_count} 点 (近地 ${ng}) · 总 ${rec.recovered_count}`;
    } else if (rec.status === "rejected") {
      $("recoveryText").textContent = translateReasonCode(rec.recovery_rejected_reason || "rejected");
    } else {
      $("recoveryText").textContent = translateReasonCode(rec.recovery_rejected_reason || rec.status);
    }
  }

  // 多轨迹表
  $("trackCountTag").textContent = `${tracks.length} 条`;
  const tbody = $("trackTableBody");
  if (!tracks.length) {
    tbody.innerHTML = `<tr><td colspan="5" class="muted-cell">当前帧无活跃轨迹</td></tr>`;
  } else {
    tbody.innerHTML = tracks
      .map((tr) => {
        const tid = tr.track_id;
        const isTgt = tid === targetTid;
        const b = phys?.tracks?.[tid]?.belief;
        const bInfo = b ? translateBeliefState(b.belief_state) : { short: "—", tone: "muted" };
        const ptsTxt =
          typeof tr.point_count === "number"
            ? String(tr.point_count)
            : isTgt && phys?.recovery
            ? String(phys.recovery.core_count)
            : tr.status === "predicted"
            ? "0"
            : "实测";
        const loTxt = b ? fmtNum(b.log_odds, 2) : "—";
        const stMap = {
          tracked: "实测",
          locked: "已锁实测",
          held: tr.missed_echo_state === "last_suspected_missing_echo"
            ? "上次疑似·缺测"
            : tr.missed_echo_state === "lost_after_suspected"
            ? "疑似后失联"
            : "缺测保持",
          tentative: "暂态",
          predicted: "缺测保持",
        };
        return `<tr class="${isTgt ? "is-target" : ""}">
          <td class="mono">${isTgt ? "★ " : ""}${tid}</td>
          <td>${stMap[tr.status] || tr.status}</td>
          <td class="mono">${ptsTxt}</td>
          <td class="mono">${fmtNum(tr.selection_score, 2)}</td>
          <td><span class="state-pill ${bInfo.tone}">${bInfo.short} ${loTxt}</span></td>
        </tr>`;
      })
      .join("");
  }
}

export class CameraPanel {
  constructor() {
    this.img = $("camImg");
    this.emptyWrap = $("camEmpty");
    this.emptyTitle = $("camEmptyTitle");
    this.emptySub = $("camEmptySub");
    this.deltaBadge = $("camDeltaBadge");
    this.syncNote = $("camSyncNote");
    this.frameTag = $("camFrameTag");

    this.mode = "replay";
    this.reqSeq = 0;
    this.blobCache = new Map(); // key -> objectUrl
    this.maxCache = 24;

    this.liveActive = false;
    this.liveRetry = 0;
    this.liveTimer = null;
  }

  _showEmpty(title, sub) {
    this.img.classList.add("hidden");
    this.emptyWrap.classList.remove("hidden");
    this.emptyTitle.textContent = title;
    this.emptySub.textContent = sub;
  }

  _showImage(src) {
    this.img.src = src;
    this.img.classList.remove("hidden");
    this.emptyWrap.classList.add("hidden");
  }

  clearCache() {
    for (const url of this.blobCache.values()) {
      URL.revokeObjectURL(url);
    }
    this.blobCache.clear();
  }

  stopLive() {
    this.liveActive = false;
    clearTimeout(this.liveTimer);
    this.liveTimer = null;
    this.img.onload = null;
    this.img.onerror = null;
    if (this.mode === "live") {
      this.img.removeAttribute("src");
    }
  }

  startLive() {
    this.mode = "live";
    this.liveActive = true;
    this.liveRetry = 0;
    this.syncNote.textContent = "板端实时 MJPEG（单连接扇出 · 非硬件同步）";
    this.frameTag.textContent = ":8081/stream";
    this.deltaBadge.textContent = "连接中…";
    this._connectLive();
  }

  _connectLive() {
    if (!this.liveActive || this.mode !== "live") return;
    this.img.onload = () => {
      if (!this.liveActive || this.mode !== "live") return;
      this.liveRetry = 0;
      this.deltaBadge.textContent = "LIVE MJPEG";
      this.img.classList.remove("hidden");
      this.emptyWrap.classList.add("hidden");
    };
    this.img.onerror = () => {
      if (!this.liveActive || this.mode !== "live") return;
      this._showEmpty("板端相机不可达", "等待 :8081/stream 自动退避重连 (2s → 10s)…");
      this.deltaBadge.textContent = "离线";
      const delay = Math.min(2000 * Math.pow(2, this.liveRetry++), 10000);
      clearTimeout(this.liveTimer);
      this.liveTimer = setTimeout(() => this._connectLive(), delay);
    };
    this.img.src = `/api/live/camera?t=${Date.now()}`;
  }

  async updateReplayFrame(sid, frameIndex, camMeta) {
    this.mode = "replay";
    this.stopLive();
    this.syncNote.textContent = "接收时间对齐 ±250 ms，非硬件同步";

    if (!camMeta || !camMeta.available) {
      this.deltaBadge.textContent = "无相机";
      this.frameTag.textContent = "100% 纯雷达";
      this._showEmpty("该会话未录制摄像头画面", "当前为 100% 纯雷达离线回放模式");
      return;
    }

    if (camMeta.state !== "ready") {
      this.deltaBadge.textContent = camMeta.deltaMs !== null ? `Δt ${camMeta.deltaMs.toFixed(1)} ms` : "超窗";
      this.frameTag.textContent = "无匹配帧";
      this._showEmpty("当前时刻无 ±250 ms 内相近相机帧", camMeta.reason || "超出接收时间对齐窗口");
      return;
    }

    const deltaTxt = `${camMeta.deltaMs >= 0 ? "+" : ""}${Number(camMeta.deltaMs).toFixed(1)} ms`;
    this.deltaBadge.textContent = `Δt = ${deltaTxt}`;
    this.frameTag.textContent = `相机帧 #${camMeta.videoFrameIndex}`;

    const cacheKey = `${sid}:${frameIndex}`;
    const cachedUrl = this.blobCache.get(cacheKey);
    if (cachedUrl) {
      this.blobCache.delete(cacheKey);
      this.blobCache.set(cacheKey, cachedUrl);
      this._showImage(cachedUrl);
      return;
    }

    const token = ++this.reqSeq;
    try {
      const resp = await fetch(`/api/camera/${encodeURIComponent(sid)}/${frameIndex}`);
      if (token !== this.reqSeq || this.mode !== "replay") return;
      if (resp.status === 204) {
        this._showEmpty("当前时刻无 ±250 ms 内相近相机帧", "接收时间对齐窗口外");
        return;
      }
      if (!resp.ok) {
        this._showEmpty("摄像头读取不可用", `HTTP ${resp.status}`);
        return;
      }
      const blob = await resp.blob();
      if (token !== this.reqSeq || this.mode !== "replay") return;
      const objUrl = URL.createObjectURL(blob);
      this.blobCache.set(cacheKey, objUrl);
      while (this.blobCache.size > this.maxCache) {
        const firstKey = this.blobCache.keys().next().value;
        URL.revokeObjectURL(this.blobCache.get(firstKey));
        this.blobCache.delete(firstKey);
      }
      this._showImage(objUrl);
    } catch (err) {
      if (token === this.reqSeq) {
        this._showEmpty("摄像头帧加载失败", err.message);
      }
    }
  }
}

export class TimelinePanel {
  constructor(sliderEl, bandsCanvas, readoutEl, tipEl, onSeek) {
    this.slider = sliderEl;
    this.canvas = bandsCanvas;
    this.ctx = bandsCanvas.getContext("2d");
    this.readoutEl = readoutEl;
    this.tipEl = tipEl;
    this.onSeek = onSeek;

    this.timeline = [];
    this.currentFrame = 0;
    this.dragging = false;

    this._bindEvents();
  }

  _bindEvents() {
    this.slider.addEventListener("input", () => {
      const idx = Number(this.slider.value);
      this.onSeek(idx);
    });

    const xToIdx = (clientX) => {
      const rect = this.canvas.getBoundingClientRect();
      if (!this.timeline.length || rect.width <= 0) return 0;
      const t = clamp((clientX - rect.left) / rect.width, 0, 1);
      return Math.round(t * (this.timeline.length - 1));
    };

    this.canvas.addEventListener("pointerdown", (ev) => {
      if (!this.timeline.length) return;
      this.dragging = true;
      this.canvas.setPointerCapture(ev.pointerId);
      this.onSeek(xToIdx(ev.clientX));
    });

    this.canvas.addEventListener("pointermove", (ev) => {
      if (!this.timeline.length) return;
      const idx = xToIdx(ev.clientX);
      if (this.dragging) {
        this.onSeek(idx);
      }
      const row = this.timeline[idx];
      if (row) {
        const rect = this.canvas.getBoundingClientRect();
        const x = clamp(ev.clientX - rect.left, 40, rect.width - 40);
        const fLabel = FALL_STATE_MAP[row.fall_state]?.short || row.fall_state;
        const bLabel = BELIEF_STATE_MAP[row.belief_state]?.short || row.belief_state;
        this.tipEl.textContent = `#${idx} · ${Number(row.t).toFixed(2)}s · ${fLabel} · ${bLabel}`;
        this.tipEl.style.left = `${x}px`;
        this.tipEl.classList.remove("hidden");
      }
    });

    const endDrag = () => {
      this.dragging = false;
    };
    this.canvas.addEventListener("pointerup", endDrag);
    this.canvas.addEventListener("pointercancel", endDrag);
    this.canvas.addEventListener("mouseleave", () => {
      this.dragging = false;
      this.tipEl.classList.add("hidden");
    });
  }

  setTimeline(timeline) {
    this.timeline = Array.isArray(timeline) ? timeline : [];
    const maxIdx = Math.max(0, this.timeline.length - 1);
    this.slider.max = String(maxIdx);
    this.slider.value = "0";
    this.currentFrame = 0;
    this.drawBands();
  }

  setFrame(frameIndex, relTimeSec) {
    this.currentFrame = frameIndex;
    this.slider.value = String(frameIndex);
    const total = this.timeline.length;
    const tStr = typeof relTimeSec === "number" ? `${relTimeSec.toFixed(2)} s` : "0.00 s";
    this.readoutEl.textContent = total > 0 ? `${frameIndex} / ${total - 1} · ${tStr}` : `LIVE #${frameIndex} · ${tStr}`;
    this.drawBands();
  }

  drawBands() {
    const ctx = this.ctx;
    const w = this.canvas.width;
    const h = this.canvas.height;
    ctx.clearRect(0, 0, w, h);

    const n = this.timeline.length;
    if (!n) {
      ctx.fillStyle = "rgba(30, 41, 59, 0.5)";
      ctx.fillRect(0, 0, w, h);
      return;
    }

    const colW = Math.max(1, w / n);
    for (let i = 0; i < n; i++) {
      const row = this.timeline[i];
      const x = (i / n) * w;
      const fCol = FALL_STATE_MAP[row.fall_state]?.color || "#334155";
      const bCol = BELIEF_STATE_MAP[row.belief_state]?.color || "#334155";
      ctx.fillStyle = fCol;
      ctx.fillRect(x, 0, colW + 0.5, 9);
      ctx.fillStyle = bCol;
      ctx.fillRect(x, 10, colW + 0.5, 8);
    }

    // 当前帧游标
    const curX = n > 1 ? (this.currentFrame / (n - 1)) * (w - 2) : 0;
    ctx.fillStyle = "#ffffff";
    ctx.fillRect(curX, 0, 2.5, h);
  }
}
