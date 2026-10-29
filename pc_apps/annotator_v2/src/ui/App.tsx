// ui/App.tsx — 应用装配。状态分四类（见 ARCHITECTURE.md）：
//   会话/帧状态（React state + loader ref）、持久标注（doc + 撤销栈）、
//   暂态交互（InteractionController，ref，不触发重渲染）、视图设置（transform ref）。
import React, { useCallback, useEffect, useRef, useState } from "react";
import type { AnnotationDoc, Box, Suggestion } from "../domain/types.ts";
import { emptyDoc, annotatedFrameSet } from "../domain/types.ts";
import { countPointsInBox } from "../domain/geometry.ts";
import { hitBox, boxToRectPx } from "../domain/geometry.ts";
import { UndoHistory, mkBox, mkInterval, mkPerson } from "../annotation/ops.ts";
import type { Op } from "../annotation/ops.ts";
import { SessionLoader, StaleResultError } from "../session/loader.ts";
import { HttpTransport, makeWorkerDecode } from "../session/http.ts";
import type { DecodedFrame, SessionMeta, SessionSummary } from "../session/types.ts";
import { PlaybackClock } from "../timeline/clock.ts";
import { InteractionController } from "../viewport2d/interaction.ts";
import type { Tool } from "../viewport2d/interaction.ts";
import { makeTransform, screenToWorld, metersPerPx, panByPx } from "../viewport2d/transform.ts";
import type { ViewTransform } from "../viewport2d/transform.ts";
import { GtClient, SaveConflictError } from "../storage/client.ts";
import { AlgorithmHost, AlgorithmDisabledError } from "../algorithm/host.ts";
import { makeDemoClusterAdapter } from "../algorithm/demoCluster.ts";
import { fetchRangeResult, makeRangeAdapter } from '../algorithm/rangeResult.ts';
import type { RangeResult } from '../algorithm/rangeResult.ts';
import { Toolbar } from "./Toolbar.tsx";
import { PersonList } from "./PersonList.tsx";
import { PropertyPanel } from "./PropertyPanel.tsx";
import { FrameChecklist } from "./FrameChecklist.tsx";
import { Viewport2D } from "./Viewport2D.tsx";
import { Viewport3D } from "./Viewport3D.tsx";
import { DepthView } from './DepthView.tsx';
import { BodyView } from './BodyView.tsx';
import { Timeline } from "./Timeline.tsx";
import { parseLaunch } from '../session/launch.ts';

const PERSON_PALETTE = ["#e8b339", "#4dd0e1", "#e0705a", "#7fd4a0", "#b39ddb", "#f06292", "#ffb74d", "#4fc3f7"];

export function personColorOf(doc: AnnotationDoc | null, personId: string): string {
  if (!doc) return PERSON_PALETTE[0]!;
  const idx = doc.persons.findIndex((p) => p.personId === personId);
  return PERSON_PALETTE[Math.max(0, idx) % PERSON_PALETTE.length]!;
}

export function App() {
  // ---------- 会话/帧状态 ----------
  const [sessions, setSessions] = useState<SessionSummary[]>([]);
  const [sessionId, setSessionId] = useState<string>("");
  const [meta, setMeta] = useState<SessionMeta | null>(null);
  const [frameIndex, setFrameIndexState] = useState(0);
  const [playing, setPlaying] = useState(false);
  const [frameEpoch, setFrameEpoch] = useState(0); // 新解码帧到达（2D/3D 消费）
  const [frameStatus, setFrameStatus] = useState<"idle" | "loading" | "ready" | "error">("idle");

  // ---------- 持久标注 ----------
  const [doc, setDocState] = useState<AnnotationDoc | null>(null);
  const [dirty, setDirty] = useState(false);
  const [historySize, setHistorySize] = useState({ past: 0, future: 0 });
  const [annotator, setAnnotator] = useState<string>(() => localStorage.getItem("annotator_v2.name") ?? "");

  // ---------- 暂态/视图/UI 状态 ----------
  const [tool, setToolState] = useState<Tool>("select");
  const [selectedBoxId, setSelection] = useState<string | null>(null);
  const [targetPersonId, setTargetPersonId] = useState<string | null>(null);
  const [show3d, setShow3d] = useState(false);
  const [rangeWorkspace, setRangeWorkspace] = useState(true);
  const [expandedBody, setExpandedBody] = useState(false);
  const [algoEnabled, setAlgoEnabled] = useState(false);
  const [algoRunning, setAlgoRunning] = useState(false);
  const [algorithmMode, setAlgorithmMode] = useState<'range' | 'demo'>('range');
  const [rangeResult, setRangeResult] = useState<RangeResult | null>(null);
  const [rangeError, setRangeError] = useState('');
  const [status, setStatus] = useState<{ msg: string; err: boolean } | null>(null);

  // ---------- refs（高频/非渲染状态） ----------
  const loaderRef = useRef<SessionLoader | null>(null);
  const frameRef = useRef<DecodedFrame | null>(null);
  const docRef = useRef<AnnotationDoc | null>(null);
  docRef.current = doc;
  const toolRef = useRef<Tool>(tool);
  toolRef.current = tool;
  const selectionRef = useRef<string | null>(selectedBoxId);
  selectionRef.current = selectedBoxId;
  const targetPersonRef = useRef<string | null>(targetPersonId);
  targetPersonRef.current = targetPersonId;
  const frameIndexRef = useRef(frameIndex);
  frameIndexRef.current = frameIndex;
  const metaRef = useRef<SessionMeta | null>(meta);
  metaRef.current = meta;
  const transformRef = useRef<ViewTransform>(makeTransform());
  const historyRef = useRef(new UndoHistory());
  const clockRef = useRef<PlaybackClock | null>(null);
  const controllerRef = useRef<InteractionController | null>(null);
  const gtRef = useRef(new GtClient());
  const genRef = useRef(0);
  const openRequestRef = useRef(0);
  const launchRef = useRef(parseLaunch(window.location.search));
  const baseRedrawRef = useRef<(() => void) | null>(null);
  const overlayRedrawRef = useRef<(() => void) | null>(null);
  const setStatusThrottled = useRef(0);

  const say = useCallback((msg: string, err = false) => {
    setStatus({ msg, err });
    setStatusThrottled.current = Date.now();
  }, []);

  // ---------- 编辑提交 ----------
  const commitOp = useCallback((op: Op) => {
    const before = docRef.current;
    if (!before) return;
    const { doc: next } = historyRef.current.commit(before, op);
    setDocState(next);
    setDirty(true);
    setHistorySize(historyRef.current.size());
  }, []);

  const undo = useCallback(() => {
    if (!docRef.current) return;
    const next = historyRef.current.undo(docRef.current);
    if (!next) return;
    setDocState(next);
    setDirty(true);
    setHistorySize(historyRef.current.size());
  }, []);

  const redo = useCallback(() => {
    if (!docRef.current) return;
    const next = historyRef.current.redo(docRef.current);
    if (!next) return;
    setDocState(next);
    setDirty(true);
    setHistorySize(historyRef.current.size());
  }, []);

  // ---------- 帧控制 ----------
  const setFrameIndex = useCallback((i: number) => {
    const m = metaRef.current;
    if (!m) return;
    const clamped = Math.max(0, Math.min(m.frameCount - 1, Math.floor(i)));
    clockRef.current?.syncTo(clamped);
    if (clamped !== frameIndexRef.current) {
      genRef.current += 1;
      frameRef.current = null;
      setRangeResult(null);
      setFrameEpoch(e => e + 1);
    }
    controllerRef.current?.interrupt(); // 切帧打断未完成手势（反例 3）
    frameIndexRef.current = clamped;
    setFrameIndexState(clamped);
  }, []);

  const pausePlayback = useCallback(() => {
    clockRef.current?.pause();
    setPlaying(false);
  }, []);

  // ---------- 交互控制器（一次装配，deps 全走 ref 闭包） ----------
  if (controllerRef.current === null) {
    controllerRef.current = new InteractionController({
      tool: () => toolRef.current,
      setTool: (t) => setToolState(t),
      selection: () => selectionRef.current,
      setSelection: (id) => setSelection(id),
      hitTest: (x, y) => {
        const d = docRef.current;
        const t = transformRef.current;
        if (!d) return null;
        const boxes = d.boxes
          .filter((b) => b.frameIndex === frameIndexRef.current)
          .map((b) => ({ box: b, rect: boxToRectPx(b, (wx, wy) => {
            const sx = t.canvasW / 2 + (wx - t.cx) * t.scalePxPerM;
            const sy = t.canvasH / 2 - (wy - t.cy) * t.scalePxPerM;
            return { sx, sy };
          }, metersPerPx(t)) }));
        return hitBox(x, y, boxes, 8);
      },
      getBox: (id) => docRef.current?.boxes.find((b) => b.boxId === id),
      toWorld: (sx, sy) => screenToWorld(transformRef.current, sx, sy),
      drawTargetPersonId: () => targetPersonRef.current ?? docRef.current?.persons[0]?.personId ?? null,
      currentFrameIndex: () => frameIndexRef.current,
      metersPerPx: () => metersPerPx(transformRef.current),
      commitOp: (op) => commitOp(op),
      panBy: (dx, dy) => {
        transformRef.current = panByPx(transformRef.current, dx, dy);
        baseRedrawRef.current?.();
      },
      pausePlayback,
      requestRedraw: () => overlayRedrawRef.current?.(),
    });
  }

  // ---------- 会话加载 ----------
  const ensureLoader = useCallback(() => {
    if (!loaderRef.current) {
      loaderRef.current = new SessionLoader(new HttpTransport(), makeWorkerDecode(), 24);
    }
    return loaderRef.current;
  }, []);

  useEffect(() => {
    let cancelled = false;
    new HttpTransport().listSessions().then((s) => {
      if (!cancelled) setSessions(s);
    }).catch((e) => say(`会话列表加载失败：${String(e)}`, true));
    return () => { cancelled = true; };
  }, [say]);

  const openSession = useCallback(async (sid: string, initialFrame = 0) => {
    if (!sid) return;
    pausePlayback();
    const requestGeneration = ++openRequestRef.current;
    genRef.current += 1;
    frameRef.current = null;
    setMeta(null);
    metaRef.current = null;
    setDocState(null);
    setRangeResult(null);
    setTargetPersonId(null);
    setSessionId(sid);
    setSelection(null);
    setFrameStatus("loading");
    const loader = ensureLoader();
    const gt = new GtClient();
    try {
      const m = await loader.resetForSession(sid);
      if (requestGeneration !== openRequestRef.current) return;
      const d = await gt.load(sid);
      if (requestGeneration !== openRequestRef.current) return;
      if (d && (d.sessionId !== sid || d.frameCount !== m.frameCount)) throw new Error('草稿与会话绑定不匹配');
      gtRef.current = gt;
      setMeta(m);
      metaRef.current = m;
      const requestedFrame = Math.max(0, Math.min(m.frameCount - 1, initialFrame));
      frameIndexRef.current = requestedFrame;
      setFrameIndexState(requestedFrame);
      clockRef.current = new PlaybackClock({
        stampSecs: m.frames.map((f) => f.stampSec),
        initialFrame: requestedFrame,
        onFrame: (i) => setFrameIndex(i),
      });
      const nextDoc = d ?? emptyDoc(sid, m.frameCount, annotator);
      setDocState(nextDoc);
      setTargetPersonId(nextDoc.persons[0]?.personId ?? null);
      historyRef.current = new UndoHistory();
      setHistorySize({ past: 0, future: 0 });
      setDirty(false);
      say(`会话 ${sid}：${m.frameCount} 帧 / ${m.frames.length > 0 ? m.frames.length : 0} 帧时间轴就绪`);
    } catch (e) {
      if (requestGeneration !== openRequestRef.current || e instanceof StaleResultError) return;
      setFrameStatus("error");
      say(`打开会话失败：${e instanceof Error ? e.message : String(e)}`, true);
    }
  }, [annotator, ensureLoader, pausePlayback, say, setFrameIndex]);

  useEffect(() => {
    const launch = launchRef.current;
    if (!launch || sessions.length === 0) return;
    launchRef.current = null;
    if (sessions.some(s => s.sessionId === launch.sid)) void openSession(launch.sid, launch.frame);
    else say(`控制台指定的会话不存在：${launch.sid}`, true);
  }, [sessions, openSession, say]);

  // ---------- 帧获取 ----------
  useEffect(() => {
    if (!meta || sessionId !== meta.sessionId) return;
    let cancelled = false;
    const loader = loaderRef.current;
    if (!loader) return;
    setFrameStatus((s) => (s === "error" ? s : "loading"));
    let fetchTimer = 0;
    let prefetchTimer = 0;
    const fetchNow = () => {
      const t0 = performance.now();
      loader.getFrame(frameIndex)
        .then((f) => {
          if (cancelled || !f || f.sessionId !== metaRef.current?.sessionId || f.frameIndex !== frameIndexRef.current) return;
          const g = globalThis as { __annotatorFrameStats?: Array<{ frameIndex: number; ms: number; count: number; cached: boolean }> };
          g.__annotatorFrameStats ??= [];
          g.__annotatorFrameStats.push({ frameIndex, ms: performance.now() - t0, count: f.count, cached: performance.now() - t0 < 1 });
          if (g.__annotatorFrameStats.length > 500) g.__annotatorFrameStats.shift();
          frameRef.current = f;
          setFrameStatus("ready");
          setFrameEpoch((e) => e + 1); // 2D/3D 消费同一份引用
          // 暂停/拖时间轴时等手停下来再预取，避免长会话一次拖动打出成百上千个 1.3MB 请求。
          if (!playing) prefetchTimer = window.setTimeout(() => {
            if (!cancelled) loader.prefetchAround(frameIndex);
          }, 150);
        })
        .catch((e) => {
          if (cancelled || e instanceof StaleResultError) return;
          setFrameStatus("error");
          say(`帧 ${frameIndex} 加载失败：${e instanceof Error ? e.message : String(e)}`, true);
        });
    };
    // 暂停且未缓存：先等 80ms；快速逐帧/拖时间轴时只真正加载停下来的那一帧。
    if (playing || loader.peek(frameIndex)) fetchNow();
    else fetchTimer = window.setTimeout(fetchNow, 80);
    if (playing) loader.prefetchAround(frameIndex);
    return () => {
      cancelled = true;
      window.clearTimeout(fetchTimer);
      window.clearTimeout(prefetchTimer);
    };
  }, [frameIndex, meta, sessionId, say, playing]);

  useEffect(() => {
    setRangeResult(null);
    setRangeError('');
    if (!meta || meta.sessionId !== sessionId) return;
    let cancelled = false;
    const controller = new AbortController();
    // 暂停拖时间轴时只取停下来的帧；播放时仍按帧取（体积很小）。
    const timer = window.setTimeout(() => {
      fetchRangeResult(sessionId, frameIndex, controller.signal).then(packet => {
        if (!cancelled) setRangeResult(packet);
      }).catch(error => {
        const name = error instanceof Error ? error.name : "";
        if (!cancelled && name !== "AbortError") setRangeError(String(error));
      });
    }, playing ? 0 : 120);
    return () => {
      cancelled = true;
      window.clearTimeout(timer);
      controller.abort();
    };
  }, [sessionId, frameIndex, meta, playing]);

  // ---------- 播放循环 ----------
  useEffect(() => {
    if (!playing) return;
    let raf = 0;
    const loop = () => {
      clockRef.current?.tick();
      if (!clockRef.current?.isPlaying) { setPlaying(false); return; }
      raf = requestAnimationFrame(loop);
    };
    raf = requestAnimationFrame(loop);
    return () => cancelAnimationFrame(raf);
  }, [playing]);

  const togglePlay = useCallback(() => {
    const clock = clockRef.current;
    if (!clock) return;
    if (clock.isPlaying) {
      clock.pause();
      setPlaying(false);
    } else {
      controllerRef.current?.interrupt();
      clock.play();
      setPlaying(true);
    }
  }, []);

  // ---------- 人物/标注动作 ----------
  const addPerson = useCallback(() => {
    const d = docRef.current;
    if (!d) return;
    const n = d.persons.length + 1;
    let name = `P${n}`;
    while (d.persons.some((p) => p.personId === name)) name = `P` + (Number(name.slice(1)) + 1);
    commitOp({ t: "addPerson", person: mkPerson(name) });
    targetPersonRef.current = name;
    setTargetPersonId(name);
    say(`已添加人物 ${name}（画框目标）`);
  }, [commitOp, say]);

  /** 切到画框：没有人物时自动建 P1；有人物但未选目标时默认第一个（否则拖框会被静默拒绝）。 */
  const selectTool = useCallback((t: Tool) => {
    controllerRef.current?.interrupt();
    if (t === "draw") {
      const d = docRef.current;
      if (d && d.persons.length === 0) addPerson();
      else setTargetPersonId((cur) => cur ?? d?.persons[0]?.personId ?? null);
    }
    setToolState(t);
  }, [addPerson]);

  const removePerson = useCallback((personId: string) => {
    commitOp({ t: "removePerson", personId });
    if (targetPersonRef.current === personId) setTargetPersonId(null);
  }, [commitOp]);

  const copyBoxToNextFrame = useCallback((box: Box) => {
    const m = metaRef.current;
    if (!m || box.frameIndex + 1 >= m.frameCount) return;
    const next: Box = {
      ...box,
      boxId: mkBox(0, "", { x: 0, y: 0, w: 1, h: 1 }, { kind: "human" }).boxId,
      frameIndex: box.frameIndex + 1,
      origin: { kind: "propagated", fromBoxId: box.boxId },
      reviewed: false,
      updatedAtMs: Date.now(),
    };
    commitOp({ t: "addBox", box: next });
    setFrameIndex(box.frameIndex + 1);
    setSelection(next.boxId);
    say(`框已复制到第 ${box.frameIndex + 1} 帧（来源 propagated）`);
  }, [commitOp, say, setFrameIndex]);

  const addIntervalForPerson = useCallback((personId: string, kind: "action" | "event", label: string, start: number, end: number) => {
    const m = metaRef.current;
    if (!m) return;
    const clampedStart = Math.max(0, Math.min(m.frameCount - 1, Math.floor(start)));
    const clampedEnd = Math.max(clampedStart, Math.min(m.frameCount - 1, Math.floor(end)));
    const itv = mkInterval(personId, kind, label, clampedStart, clampedEnd);
    commitOp({ t: "addInterval", interval: itv });
    say(`已添加区间 ${label} [${clampedStart}, ${clampedEnd}]`);
  }, [commitOp, say]);

  // ---------- 保存/导出 ----------
  const saveDraft = useCallback(async () => {
    const d = docRef.current;
    if (!d) return;
    const client = gtRef.current;
    try {
      const v = await client.save({ ...d, annotator });
      if (client !== gtRef.current || docRef.current?.sessionId !== d.sessionId) return;
      if (docRef.current === d) setDirty(false);
      setDocState((cur) => (cur && cur.sessionId === d.sessionId ? { ...cur, savedAtMs: Date.now() } : cur));
      say(`已保存（版本 v${v}）`);
    } catch (e) {
      if (client !== gtRef.current) return;
      if (e instanceof SaveConflictError) {
        say(`保存冲突：服务器已有 v${e.currentVersion}，请先「重载草稿」`, true);
      } else {
        say(`保存失败：${e instanceof Error ? e.message : String(e)}`, true);
      }
    }
  }, [annotator, say]);

  const reloadDraft = useCallback(async () => {
    if (!sessionId) return;
    const request = openRequestRef.current;
    try {
      const d = await gtRef.current.load(sessionId);
      if (request !== openRequestRef.current) return;
      if (d && (d.sessionId !== sessionId || d.frameCount !== metaRef.current?.frameCount)) throw new Error('草稿与会话绑定不匹配');
      setDocState(d ?? emptyDoc(sessionId, metaRef.current?.frameCount ?? 0, annotator));
      historyRef.current = new UndoHistory();
      setHistorySize({ past: 0, future: 0 });
      setDirty(false);
      setSelection(null);
      say("已重载草稿");
    } catch (e) {
      say(`重载失败：${e instanceof Error ? e.message : String(e)}`, true);
    }
  }, [annotator, say, sessionId]);

  // ---------- 算法 ----------
  const hostRef = useRef<AlgorithmHost | null>(null);
  if (hostRef.current === null) {
    hostRef.current = new AlgorithmHost(makeDemoClusterAdapter(), {
      enabled: () => algoEnabledRef.current,
      currentGeneration: () => genRef.current,
      commitOp: (op) => commitOp(op),
    });
  }
  const algoEnabledRef = useRef(algoEnabled);
  algoEnabledRef.current = algoEnabled;

  const runAlgorithm = useCallback(async () => {
    const d = docRef.current;
    const loader = loaderRef.current;
    if (!d || !loader) return;
    if (!algoEnabledRef.current) { say("算法未启用", true); return; }
    const requestedFrame = frameIndexRef.current;
    const requestedGeneration = genRef.current;
    const frame = frameRef.current;
    if (!frame || frame.sessionId !== d.sessionId || frame.frameIndex !== requestedFrame) {
      say('当前帧尚未就绪', true); return;
    }
    setAlgoRunning(true);
    try {
      const adapter = algorithmMode === 'range'
        ? makeRangeAdapter(await fetchRangeResult(d.sessionId, requestedFrame)) : makeDemoClusterAdapter();
      if (genRef.current !== requestedGeneration || !algoEnabledRef.current) return;
      const host = new AlgorithmHost(adapter, {
        enabled: () => algoEnabledRef.current, currentGeneration: () => genRef.current,
        commitOp: op => commitOp(op),
      });
      hostRef.current = host;
      const suggestions: Suggestion[] = await host.run({
        sessionId: d.sessionId,
        frameIndex: requestedFrame,
        generation: requestedGeneration,
        frame,
        doc: d,
      });
      if (genRef.current !== requestedGeneration || docRef.current?.sessionId !== d.sessionId || !algoEnabledRef.current) return;
      if (suggestions.length === 0) {
        say("算法：无建议（或结果已过期被丢弃）");
      } else {
        commitOp({ t: "composite", label: "算法建议", ops: suggestions.map((s) => ({ t: "addSuggestion", suggestion: s } as Op)) });
        say(`算法：${suggestions.length} 条建议（待人工采用）`);
      }
    } catch (e) {
      if (e instanceof AlgorithmDisabledError) say("算法未启用", true);
      else say(`算法失败：${e instanceof Error ? e.message : String(e)}`, true);
    } finally {
      setAlgoRunning(false);
    }
  }, [commitOp, say, algorithmMode]);

  const adoptSuggestion = useCallback((sug: Suggestion) => {
    const d = docRef.current;
    const host = hostRef.current!;
    if (!d) return;
    const personId = targetPersonRef.current ?? d.persons[0]?.personId;
    if (!personId) { say("先添加/选择目标人物再采用", true); return; }
    const r = host.adopt(d, sug.suggestionId, personId);
    if (!r) return;
    commitOp({ t: "composite", label: "采用建议", ops: r.ops });
    setSelection(sug.box ? r.createdId : null);
    say(`已采用建议 → 人物 ${personId} 的${sug.box ? '框' : '区间'}（来源保留）`);
  }, [commitOp, say]);

  const rejectSuggestion = useCallback((sug: Suggestion) => {
    const d = docRef.current;
    const host = hostRef.current!;
    if (!d) return;
    const r = host.reject(d, sug.suggestionId);
    if (!r) return;
    commitOp({ t: "composite", label: "拒绝建议", ops: r.ops });
  }, [commitOp]);

  // ---------- 少量可选快捷键（核心操作全部有按钮） ----------
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      const target = e.target as HTMLElement | null;
      if (target && (target.tagName === "INPUT" || target.tagName === "SELECT" || target.tagName === "TEXTAREA")) return;
      if ((e.ctrlKey || e.metaKey) && e.key.toLowerCase() === "z") {
        e.preventDefault();
        if (e.shiftKey) redo(); else undo();
      } else if ((e.ctrlKey || e.metaKey) && e.key.toLowerCase() === "y") {
        e.preventDefault();
        redo();
      } else if (e.key === "ArrowLeft") { pausePlayback(); setFrameIndex(frameIndexRef.current - 1); }
      else if (e.key === "ArrowRight") { pausePlayback(); setFrameIndex(frameIndexRef.current + 1); }
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [pausePlayback, redo, setFrameIndex, undo]);

  // ---------- 窗口失焦 → 取消未完成手势（反例 3 的一半） ----------
  useEffect(() => {
    const onBlur = () => controllerRef.current?.externalCancel();
    window.addEventListener("blur", onBlur);
    return () => window.removeEventListener("blur", onBlur);
  }, []);

  // 播放期间标注人正在编辑（拖拽中）→ 时钟强制暂停
  useEffect(() => {
    const c = controllerRef.current;
    if (c && c.editingActive && clockRef.current?.isPlaying) {
      clockRef.current.pause();
      setPlaying(false);
    }
  });

  // ---------- 派生 ----------
  const boxesThisFrame = doc ? doc.boxes.filter((b) => b.frameIndex === frameIndex) : [];
  const annotatedFrames = doc ? [...annotatedFrameSet(doc)].sort((a, b) => a - b) : [];
  const suggestionsThisFrame = doc ? doc.suggestions.filter((s) => s.status === "pending" &&
    (s.interval ? s.frameIndex <= frameIndex && s.interval.endFrame >= frameIndex : s.frameIndex === frameIndex)) : [];
  const selectedBox = boxesThisFrame.find((b) => b.boxId === selectedBoxId) ?? null;
  const stats = loaderRef.current?.stats();

  return (
    <div className={`app${expandedBody && rangeWorkspace ? ' expanded-body' : ''}`}>
      <Toolbar
        tool={tool}
        setTool={t => { if (t === 'draw' || t === 'pan') setRangeWorkspace(false); selectTool(t); }}
        canUndo={historySize.past > 0}
        canRedo={historySize.future > 0}
        onUndo={undo}
        onRedo={redo}
        onSave={saveDraft}
        onReload={reloadDraft}
        onExport={() => doc && gtRef.current.exportDownload(doc)}
        dirty={dirty}
        annotator={annotator}
        setAnnotator={(v) => { setAnnotator(v); localStorage.setItem("annotator_v2.name", v); }}
        algoEnabled={algoEnabled}
        setAlgoEnabled={(v) => { genRef.current += 1; algoEnabledRef.current = v; setAlgoEnabled(v); }}
        algoRunning={algoRunning}
        onRunAlgorithm={runAlgorithm}
        show3d={show3d}
        setShow3d={setShow3d}
        status={status}
        sessions={sessions}
        sessionId={sessionId}
        onOpenSession={openSession}
      />
      <div className="panel left">
        <button className={rangeWorkspace ? 'active' : ''} onClick={() => setRangeWorkspace(true)}>2D 距离图 / 身体部位</button>
        <button className={!rangeWorkspace ? 'active' : ''} onClick={() => setRangeWorkspace(false)}>XY 俯瞰图 / 整人框</button>
        <PersonList
          doc={doc}
          boxesThisFrame={boxesThisFrame}
          targetPersonId={targetPersonId}
          setTargetPersonId={setTargetPersonId}
          onAddPerson={addPerson}
          onRemovePerson={removePerson}
          personColorOf={personColorOf}
        />
        <FrameChecklist
          doc={doc}
          currentFrame={frameIndex}
          onSetFrames={(frames) => commitOp({ t: "setSampleFrames", frames })}
          onSeek={(f) => { pausePlayback(); setFrameIndex(f); }}
        />
      </div>
      <div className="main">
        {rangeWorkspace && meta && <button className="body-expand" onClick={() => setExpandedBody(v => !v)}>{expandedBody ? '恢复面板' : '放大标注区'}</button>}
        {meta && rangeWorkspace ? (rangeResult ? <BodyView
          key={`${sessionId}/${frameIndex}/${targetPersonId ?? 'candidate'}/${rangeResult.frame.rawSha256}`}
          packet={rangeResult} person={targetPersonId ?? `candidate_${rangeResult.frame.trackId ?? 'missing'}`}
          box={boxesThisFrame.find(b => b.personId === targetPersonId) ?? null} doc={doc}
          frameRef={frameRef} frameEpoch={frameEpoch} pause={pausePlayback} />
          : <div className="empty-hint">{rangeError || '加载当前帧 LiDAR 距离图…'}</div>) : meta ? (
          <>
            <Viewport2D
              controllerRef={controllerRef}
              transformRef={transformRef}
              baseRedrawRef={baseRedrawRef}
              overlayRedrawRef={overlayRedrawRef}
              frameRef={frameRef}
              frameEpoch={frameEpoch}
              sessionId={sessionId}
              doc={doc}
              frameIndex={frameIndex}
              selectedBoxId={selectedBoxId}
              tool={tool}
              suggestions={suggestionsThisFrame}
              frameStatus={frameStatus}
              meta={meta}
            />
            {show3d && (
              <Viewport3D
                frameRef={frameRef}
                frameEpoch={frameEpoch}
                boxes={boxesThisFrame}
                doc={doc}
                onClose={() => setShow3d(false)}
                personColorOf={personColorOf}
              />
            )}
          </>
        ) : (
          <div className="empty-hint">左上选择会话开始标注</div>
        )}
      </div>
      <div className="panel right">
        {!rangeWorkspace && <DepthView key={`${sessionId}/${frameIndex}/${rangeResult?.frame.rawSha256 ?? ''}`} packet={rangeResult} />}
        <h4>识别结果</h4>
        <select aria-label="算法来源" value={algorithmMode} onChange={e => {
          genRef.current += 1; setAlgorithmMode(e.target.value as 'range' | 'demo');
        }}>
          <option value="range">距离图跟踪 / 跌倒规则</option>
          <option value="demo">演示聚类（不识别跌倒）</option>
        </select>
        {rangeResult && algorithmMode === 'range' && <div className="status-msg">
          动态过程：<strong>{rangeResult.frame.state}</strong><br />
          {rangeResult.frame.groundAlert && <>低位提示：<strong>{rangeResult.frame.groundAlert.active ? '持续低姿态提示' : rangeResult.frame.groundAlert.state === 'low_pending' ? `观察中 ${rangeResult.frame.groundAlert.durationSec.toFixed(2)} / 1.5 s` : '未触发'}</strong>（蹲坐也可能触发，非确认跌倒）<br /></>}
          躺倒几何：{({lying_candidate:'持续躺倒形状候选',lying_pending:'躺倒形状观察中',vertical_surface:'竖直表面',unknown:'观测不足'} as Record<string,string>)[rangeResult.frame.posture?.state ?? ''] ?? '未生成'}<br />
          目标 {rangeResult.frame.trackId ?? 'UNKNOWN'} · {rangeResult.frame.measured ? '当前实测' : '缺测'}<br />
          高度 {rangeResult.frame.heightMedianM === null ? 'UNKNOWN' : `${rangeResult.frame.heightMedianM.toFixed(2)} m`}<br />
          {rangeResult.frame.reasons.join(' / ')}<br />
          人体与跌倒真值 UNKNOWN · 确认告警关闭
        </div>}
        {rangeError && <div className="status-msg">{rangeError}</div>}
        <PropertyPanel
          doc={doc}
          frame={frameRef.current}
          frameIndex={frameIndex}
          meta={meta}
          selectedBox={selectedBox}
          onCommit={commitOp}
          onCopyNext={copyBoxToNextFrame}
          onDelete={() => { if (selectedBox) { commitOp({ t: "removeBox", boxId: selectedBox.boxId }); setSelection(null); } }}
          suggestions={suggestionsThisFrame}
          onAdopt={adoptSuggestion}
          onReject={rejectSuggestion}
          personColorOf={personColorOf}
          onAddInterval={addIntervalForPerson}
          onRemoveInterval={(id) => commitOp({ t: "removeInterval", intervalId: id })}
          targetPersonId={targetPersonId}
        />
      </div>
      <Timeline
        meta={meta}
        frameIndex={frameIndex}
        playing={playing}
        clock={clockRef.current}
        onTogglePlay={togglePlay}
        onSeek={(i) => { pausePlayback(); setFrameIndex(i); }}
        onStep={(d) => { pausePlayback(); setFrameIndex(frameIndexRef.current + d); }}
        doc={doc}
        personColorOf={personColorOf}
        frameStatus={frameStatus}
        cacheStats={stats}
        annotatedFrames={annotatedFrames}
        algorithmIntervals={rangeResult?.allIntervals ?? []}
      />
    </div>
  );
}
