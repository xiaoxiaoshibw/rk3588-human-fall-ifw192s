// timeline/clock.ts — 播放时钟：以源帧时间戳（stamp_sec）为纲。
// 播放：按壁钟推进目标源时间，当前帧 = 满足 stamp ≤ 目标的最大帧（真实源帧，
// 不造帧、不改时间戳）；播放可以丢过时显示帧，暂停/逐帧/标注始终精确到源帧。
export interface PlaybackClockOptions {
  stampSecs: number[]; // 每帧源时间（单调不减）
  onFrame(frameIndex: number): void;
  onEnd?(): void;
  /** 初始帧（打开会话可直接落在指定帧，而不是总从 0 开始）。 */
  initialFrame?: number;
}

export class PlaybackClock {
  private playing = false;
  private rate = 1;
  private frameIndex = 0;
  private playStartWallMs = 0;
  private playStartStamp = 0;
  /** 编辑进行中：外部置 true，播放被强制暂停（规范十一）。 */
  editing = false;

  constructor(private opts: PlaybackClockOptions) {
    this.frameIndex = Math.max(0, Math.min(this.frameCount - 1, Math.floor(opts.initialFrame ?? 0)));
  }

  get isPlaying(): boolean { return this.playing; }
  get currentFrame(): number { return this.frameIndex; }
  get frameCount(): number { return this.opts.stampSecs.length; }

  play(): void {
    if (this.playing || this.editing) return;
    if (this.frameIndex >= this.frameCount - 1) this.frameIndex = 0; // 到尾重播
    this.playing = true;
    this.playStartWallMs = nowMs();
    this.playStartStamp = this.stampAt(this.frameIndex);
  }

  pause(): void {
    if (!this.playing) return;
    this.playing = false;
  }

  seek(i: number): void {
    const clamped = Math.max(0, Math.min(this.frameCount - 1, Math.floor(i)));
    if (clamped === this.frameIndex) return;
    this.frameIndex = clamped;
    if (this.playing) {
      this.playStartWallMs = nowMs();
      this.playStartStamp = this.stampAt(clamped);
    }
    this.opts.onFrame(clamped);
  }

  /** 外部（逐帧/时间轴/复制到下一帧）同步内部帧号；不触发 onFrame，避免回环。 */
  syncTo(i: number): void {
    const clamped = Math.max(0, Math.min(this.frameCount - 1, Math.floor(i)));
    if (clamped === this.frameIndex) return;
    this.frameIndex = clamped;
    if (this.playing) {
      this.playStartWallMs = nowMs();
      this.playStartStamp = this.stampAt(clamped);
    }
  }

  step(delta: number): void {
    this.pause();
    this.seek(this.frameIndex + delta);
  }

  setRate(rate: number): void {
    if (rate <= 0) return;
    // 平滑换速：重锚当前帧
    if (this.playing) {
      this.playStartStamp = this.stampAt(this.frameIndex);
      this.playStartWallMs = nowMs();
    }
    this.rate = rate;
  }

  getRate(): number { return this.rate; }

  /** 由 rAF 驱动（每帧一次）；非播放状态无副作用。 */
  tick(): void {
    if (!this.playing) return;
    const target = this.playStartStamp + (nowMs() - this.playStartWallMs) / 1000 * this.rate;
    const stamps = this.opts.stampSecs;
    // 二分：最大 stamp ≤ target
    let lo = 0, hi = stamps.length - 1;
    if (target < stamps[0]!) { this.frameIndex = 0; this.opts.onFrame(0); return; }
    if (target >= stamps[stamps.length - 1]!) {
      this.frameIndex = stamps.length - 1;
      this.opts.onFrame(this.frameIndex);
      this.playing = false;
      this.opts.onEnd?.();
      return;
    }
    while (lo < hi) {
      const mid = Math.ceil((lo + hi) / 2);
      if (stamps[mid]! <= target) lo = mid; else hi = mid - 1;
    }
    if (lo !== this.frameIndex) {
      this.frameIndex = lo;
      this.opts.onFrame(lo);
    }
  }

  private stampAt(i: number): number { return this.opts.stampSecs[i] ?? 0; }
}

function nowMs(): number {
  return typeof performance !== "undefined" ? performance.now() : Date.now();
}

/** 时间轴像素布局（渲染用纯函数）。 */
export interface TimelineLayout {
  widthPx: number;
  frameCount: number;
}

export function frameToX(l: TimelineLayout, frame: number): number {
  if (l.frameCount <= 1) return 0;
  return (frame / (l.frameCount - 1)) * l.widthPx;
}

export function xToFrame(l: TimelineLayout, x: number): number {
  if (l.frameCount <= 1) return 0;
  const t = Math.max(0, Math.min(1, x / l.widthPx));
  return Math.round(t * (l.frameCount - 1));
}

export function formatStamp(stampSec: number): string {
  return `${stampSec.toFixed(2)}s`;
}
