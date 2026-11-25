import assert from "node:assert/strict";
import {
  BELIEF_STATE_MAP,
  FALL_STATE_MAP,
  FLAG_FOREGROUND,
  FLAG_RECOVERY_ADDED,
  FLAG_TARGET_CORE,
  HDR_HAS_INTENSITY,
  HDR_HAS_RANGE_MASK,
  HDR_IS_LIVE,
  LDSF_HEADER_SIZE,
  computeDisplayBasis,
  computeLevelMatrixColMajor,
  computePresetPose,
  decodeFramePacket,
  displayPixelToNative,
  easeOutCubic,
  lerpVec3,
  rangeToPreviewRgb,
  rawPointToWorld,
  translateBeliefState,
  translateFallState,
  translatePosture,
  translateReasonCode,
} from "./studio_lib.js";

function makePacket({
  xyz,
  pointFlags,
  rangeMm,
  state,
  intensity = null,
  rangeMask = null,
  decimation = 2,
  isLive = false,
  height = 2,
  width = 2,
}) {
  const n = xyz.length / 3;
  const jsonBytes = new TextEncoder().encode(JSON.stringify(state));
  const intenLen = intensity ? n * 4 : 0;
  const rmmLen = height * width * 2;
  const rmaskLen = rangeMask ? height * width : 0;
  const total = LDSF_HEADER_SIZE + n * 12 + intenLen + rmmLen + n + rmaskLen + jsonBytes.length;

  const buf = new ArrayBuffer(total);
  const dv = new DataView(buf);
  dv.setUint8(0, 76); // 'L'
  dv.setUint8(1, 68); // 'D'
  dv.setUint8(2, 83); // 'S'
  dv.setUint8(3, 70); // 'F'
  dv.setUint8(4, 1);
  let hdrFlags = 0;
  if (intensity) hdrFlags |= HDR_HAS_INTENSITY;
  if (rangeMask) hdrFlags |= HDR_HAS_RANGE_MASK;
  if (isLive) hdrFlags |= HDR_IS_LIVE;
  dv.setUint8(5, hdrFlags);
  dv.setUint16(6, decimation, true);
  dv.setUint32(8, n, true);
  dv.setUint16(12, height, true);
  dv.setUint16(14, width, true);
  dv.setUint32(16, n * 12, true);
  dv.setUint32(20, intenLen, true);
  dv.setUint32(24, rmmLen, true);
  dv.setUint32(28, n, true);
  dv.setUint32(32, rmaskLen, true);
  dv.setUint32(36, jsonBytes.length, true);

  let off = LDSF_HEADER_SIZE;
  new Float32Array(buf, off, xyz.length).set(xyz);
  off += n * 12;
  if (intensity) {
    new Float32Array(buf, off, intensity.length).set(intensity);
    off += intenLen;
  }
  new Uint16Array(buf, off, rangeMm.length).set(rangeMm);
  off += rmmLen;
  new Uint8Array(buf, off, pointFlags.length).set(pointFlags);
  off += n;
  if (rangeMask) {
    new Uint8Array(buf, off, rangeMask.length).set(rangeMask);
    off += rmaskLen;
  }
  new Uint8Array(buf, off, jsonBytes.length).set(jsonBytes);
  return buf;
}

// 1. LDSF 解码与畸形包拒绝
{
  const buf = makePacket({
    xyz: [1, 2, 3, 4, 5, 6],
    intensity: [100, 900],
    rangeMm: [0, 100, 4050, 8000],
    pointFlags: [FLAG_TARGET_CORE, FLAG_RECOVERY_ADDED | FLAG_FOREGROUND],
    rangeMask: [0, FLAG_TARGET_CORE, FLAG_RECOVERY_ADDED, 0],
    state: { frame_index: 12, fall_status: "suspected" },
    decimation: 2,
    isLive: true,
  });
  const dec = decodeFramePacket(buf);
  assert.equal(dec.version, 1);
  assert.equal(dec.decimation, 2);
  assert.equal(dec.isLive, true);
  assert.equal(dec.pointCount, 2);
  assert.deepEqual(Array.from(dec.xyz), [1, 2, 3, 4, 5, 6]);
  assert.deepEqual(Array.from(dec.intensity), [100, 900]);
  assert.deepEqual(Array.from(dec.rangeMm), [0, 100, 4050, 8000]);
  assert.deepEqual(Array.from(dec.pointFlags), [FLAG_TARGET_CORE, FLAG_RECOVERY_ADDED | FLAG_FOREGROUND]);
  assert.deepEqual(Array.from(dec.rangeMask), [0, FLAG_TARGET_CORE, FLAG_RECOVERY_ADDED, 0]);
  assert.equal(dec.state.fall_status, "suspected");

  assert.throws(() => decodeFramePacket(buf.slice(0, 10)));
  const badMagic = new Uint8Array(buf.slice(0));
  badMagic[0] = 88;
  assert.throws(() => decodeFramePacket(badMagic.buffer));
}

// 2. preview_rgb 色标一致性（0.1–8.0 m）
{
  assert.deepEqual(rangeToPreviewRgb(0), [0, 0, 0]);
  assert.deepEqual(rangeToPreviewRgb(100), [255, 0, 0]); // 0.1 m -> t=0 -> 红
  assert.deepEqual(rangeToPreviewRgb(4050), [127, 254, 127]); // 4.05 m -> t=0.5 -> 绿
  assert.deepEqual(rangeToPreviewRgb(8000), [0, 0, 255]); // 8.0 m -> t=1 -> 蓝
  assert.deepEqual(rangeToPreviewRgb(12000), [0, 0, 255]); // 截断到 1.0
}

// 3. rotate180 像素坐标 <-> 原生网格换算
{
  assert.deepEqual(displayPixelToNative(0, 0, 256, 192), {
    displayCol: 0,
    displayRow: 0,
    nativeRing: 191,
    nativeCol: 255,
  });
  assert.deepEqual(displayPixelToNative(255, 191, 256, 192), {
    displayCol: 255,
    displayRow: 191,
    nativeRing: 0,
    nativeCol: 0,
  });
}

// 4. 配平基与 4x4 矩阵一致性
{
  const plane = { normal: [-0.463888, -0.032116, 0.885311], offsetM: 1.366635 };
  const basis = computeDisplayBasis(plane.normal);
  const dotFU = basis.forward[0] * basis.up[0] + basis.forward[1] * basis.up[1] + basis.forward[2] * basis.up[2];
  assert.ok(Math.abs(dotFU) < 1e-6);

  const rawPt = [2.0, 0.3, -0.4];
  const worldPt = rawPointToWorld(rawPt[0], rawPt[1], rawPt[2], plane, true);
  const m = computeLevelMatrixColMajor(plane, true);
  // 校验列主序矩阵与 rawPointToWorld 一致
  const mx = m[0] * rawPt[0] + m[4] * rawPt[1] + m[8] * rawPt[2] + m[12];
  const my = m[1] * rawPt[0] + m[5] * rawPt[1] + m[9] * rawPt[2] + m[13];
  const mz = m[2] * rawPt[0] + m[6] * rawPt[1] + m[10] * rawPt[2] + m[14];
  assert.ok(Math.abs(mx - worldPt[0]) < 1e-6);
  assert.ok(Math.abs(my - worldPt[1]) < 1e-6);
  assert.ok(Math.abs(mz - worldPt[2]) < 1e-6);
}

// 5. 视角预设与补间
{
  const pFront = computePresetPose("front", [2, 1, 0], [0, 1.3, 0], 4);
  assert.ok(pFront.position[0] > pFront.target[0]);
  const pTop = computePresetPose("top", [2, 1, 0], [0, 1.3, 0], 4);
  assert.ok(pTop.position[1] > pTop.target[1] + 4);
  const pSensor = computePresetPose("sensor", [2, 1, 0], [0, 1.35, 0], 4);
  assert.ok(pSensor.position[0] < 0.1 && Math.abs(pSensor.position[1] - 1.5) < 0.01);
  assert.equal(easeOutCubic(0), 0);
  assert.equal(easeOutCubic(1), 1);
  assert.deepEqual(lerpVec3([0, 0, 0], [2, 4, 6], 0.5), [1, 2, 3]);
}

// 6. 语义诚实与中文字典
{
  const conf = translateBeliefState("CONFIRMED_HUMAN");
  assert.ok(conf.label.includes("非真值"));
  assert.equal(translateFallState("suspected").short, "疑似跌倒");
  assert.equal(translatePosture("lying_candidate").short, "躺");
  assert.equal(translateReasonCode("measured_descent"), "此前测得下降");
  assert.equal(translateReasonCode("expansion_ratio_exceeded"), "拒绝：膨胀比例超限");
  assert.equal(translateReasonCode("FAST_KINEMATIC"), "快速运动学下坠+坍塌");
  assert.equal(translateReasonCode("SLOW_DESCENT"), "缓慢下坠+持续低位坍塌");
  assert.ok(Object.keys(FALL_STATE_MAP).length >= 7);
  assert.ok(Object.keys(BELIEF_STATE_MAP).length >= 3);
}

console.log("studio_lib.test.js: all assertions passed");
