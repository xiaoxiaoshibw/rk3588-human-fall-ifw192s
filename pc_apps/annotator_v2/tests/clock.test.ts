// tests/clock.test.ts — 播放时钟：按源时间推进、暂停/逐帧精确、结束停播、换速重锚。
import { describe, expect, it, beforeEach, afterEach, vi } from "vitest";
import { PlaybackClock, frameToX, xToFrame } from "../src/timeline/clock.ts";

// 10Hz 源帧：stamp 100.0, 100.1, ...
const STAMPS = Array.from({ length: 11 }, (_, i) => 100 + i * 0.1);

let now = 0;
let spy: ReturnType<typeof vi.spyOn>;

beforeEach(() => {
  now = 0;
  spy = vi.spyOn(performance, "now").mockImplementation(() => now);
});
afterEach(() => spy.mockRestore());

function mkClock() {
  const frames: number[] = [];
  const ended: boolean[] = [];
  const clock = new PlaybackClock({ stampSecs: STAMPS, onFrame: (i) => frames.push(i), onEnd: () => ended.push(true) });
  return { clock, frames, ended };
}

describe("PlaybackClock", () => {
  it("播放按源时间推进：0.15s → 第 1 帧（100.1 ≤ t < 100.2）", () => {
    const { clock, frames } = mkClock();
    clock.play();
    now = 150;
    clock.tick();
    expect(clock.currentFrame).toBe(1);
    expect(frames).toEqual([1]); // 只发变化的帧
    now = 350;
    clock.tick();
    expect(clock.currentFrame).toBe(3);
  });

  it("暂停后 tick 无副作用；逐帧 step 精确到源帧", () => {
    const { clock, frames } = mkClock();
    clock.play();
    now = 150;
    clock.tick();
    clock.pause();
    now = 5000;
    clock.tick();
    expect(clock.currentFrame).toBe(1);
    clock.step(1);
    expect(clock.currentFrame).toBe(2);
    clock.step(-1);
    expect(clock.currentFrame).toBe(1);
    expect(frames).toEqual([1, 2, 1]);
  });

  it("播到末尾：停播 + onEnd 一次", () => {
    const { clock, ended } = mkClock();
    clock.play();
    now = 2000;
    clock.tick();
    expect(clock.currentFrame).toBe(STAMPS.length - 1);
    expect(clock.isPlaying).toBe(false);
    expect(ended).toHaveLength(1);
  });

  it("seek 边界钳制；播放中 seek 重锚不跳变", () => {
    const { clock } = mkClock();
    clock.seek(999);
    expect(clock.currentFrame).toBe(STAMPS.length - 1);
    clock.seek(-5);
    expect(clock.currentFrame).toBe(0);
    clock.play();
    now = 50;
    clock.tick();
    expect(clock.currentFrame).toBe(0);
    clock.seek(5);
    now = 110; // seek 重锚于 now=50；60ms 后目标 = 100.5+0.06 = 100.56 → 帧 5
    clock.tick();
    expect(clock.currentFrame).toBe(5);
  });

  it("倍速 2×：0.1s 壁钟走 0.2s 源时间 = 2 帧", () => {
    const { clock } = mkClock();
    clock.play();
    clock.setRate(2);
    now = 100;
    clock.tick();
    expect(clock.currentFrame).toBe(2);
  });

  it("initialFrame 决定播放起点；syncTo 同步帧号但不回调", () => {
    const frames: number[] = [];
    const clock = new PlaybackClock({ stampSecs: STAMPS, initialFrame: 5, onFrame: (i) => frames.push(i) });
    expect(clock.currentFrame).toBe(5);
    clock.play();
    now = 150; // 从第 5 帧 100.5s 起走 0.15s → 第 6 帧
    clock.tick();
    expect(clock.currentFrame).toBe(6);
    expect(frames).toEqual([6]);
    clock.syncTo(9);
    expect(clock.currentFrame).toBe(9);
    expect(frames).toEqual([6]);
  });

  it("时间轴换算互逆", () => {
    const layout = { widthPx: 500, frameCount: 11 };
    expect(frameToX(layout, 0)).toBe(0);
    expect(frameToX(layout, 10)).toBe(500);
    expect(xToFrame(layout, 250)).toBe(5);
    expect(xToFrame(layout, -20)).toBe(0);
    expect(xToFrame(layout, 999)).toBe(10);
  });
});
