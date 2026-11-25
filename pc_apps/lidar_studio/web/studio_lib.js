/**
 * 雷达体态工作台纯函数核心（零 DOM 依赖，Node 与浏览器共用）。
 * 对应后端契约：pc_apps/lidar_studio/CONTRACT.md (LDSF v1)
 */

export const LDSF_MAGIC = "LDSF";
export const LDSF_VERSION = 1;
export const LDSF_HEADER_SIZE = 40;

export const HDR_HAS_INTENSITY = 0x01;
export const HDR_HAS_RANGE_MASK = 0x02;
export const HDR_IS_LIVE = 0x04;

export const FLAG_TARGET_CORE = 0x01;
export const FLAG_RECOVERY_ADDED = 0x02;
export const FLAG_OTHER_TRACK = 0x04;
export const FLAG_FOREGROUND = 0x08;

const textDecoder = new TextDecoder("utf-8");

export function clamp(v, lo, hi) {
  return v < lo ? lo : v > hi ? hi : v;
}

export function easeOutCubic(t) {
  const x = clamp(t, 0, 1);
  return 1 - Math.pow(1 - x, 3);
}

export function lerpVec3(a, b, t) {
  const u = clamp(t, 0, 1);
  return [
    a[0] + (b[0] - a[0]) * u,
    a[1] + (b[1] - a[1]) * u,
    a[2] + (b[2] - a[2]) * u,
  ];
}

/**
 * 解码 LDSF v1 二进制数据包（严格校验头与边界）。
 */
export function decodeFramePacket(input) {
  let buf;
  let byteOffset = 0;
  let byteLength = 0;
  if (input instanceof ArrayBuffer) {
    buf = input;
    byteOffset = 0;
    byteLength = input.byteLength;
  } else if (ArrayBuffer.isView(input)) {
    buf = input.buffer;
    byteOffset = input.byteOffset;
    byteLength = input.byteLength;
  } else {
    throw new Error("Expected ArrayBuffer or ArrayBufferView");
  }

  if (byteLength < LDSF_HEADER_SIZE) {
    throw new Error(`LDSF packet too short: ${byteLength} < ${LDSF_HEADER_SIZE}`);
  }

  const dv = new DataView(buf, byteOffset, byteLength);
  const magic = String.fromCharCode(
    dv.getUint8(0),
    dv.getUint8(1),
    dv.getUint8(2),
    dv.getUint8(3)
  );
  if (magic !== LDSF_MAGIC) {
    throw new Error(`Invalid LDSF magic: ${magic}`);
  }

  const version = dv.getUint8(4);
  if (version !== LDSF_VERSION) {
    throw new Error(`Unsupported LDSF version: ${version}`);
  }

  const hdrFlags = dv.getUint8(5);
  const decimation = dv.getUint16(6, true);
  if (decimation < 1) {
    throw new Error(`Invalid decimation: ${decimation}`);
  }

  const pointCount = dv.getUint32(8, true);
  const rangeHeight = dv.getUint16(12, true);
  const rangeWidth = dv.getUint16(14, true);
  const xyzLen = dv.getUint32(16, true);
  const intensityLen = dv.getUint32(20, true);
  const rangeMmLen = dv.getUint32(24, true);
  const pointFlagsLen = dv.getUint32(28, true);
  const rangeMaskLen = dv.getUint32(32, true);
  const jsonLen = dv.getUint32(36, true);

  const hasIntensity = Boolean(hdrFlags & HDR_HAS_INTENSITY);
  const hasRangeMask = Boolean(hdrFlags & HDR_HAS_RANGE_MASK);
  const isLive = Boolean(hdrFlags & HDR_IS_LIVE);

  if (xyzLen !== pointCount * 12) {
    throw new Error(`xyzLen mismatch: ${xyzLen} != ${pointCount * 12}`);
  }
  const expIntenLen = hasIntensity ? pointCount * 4 : 0;
  if (intensityLen !== expIntenLen) {
    throw new Error(`intensityLen mismatch: ${intensityLen} != ${expIntenLen}`);
  }
  if (rangeMmLen !== rangeHeight * rangeWidth * 2) {
    throw new Error(`rangeMmLen mismatch: ${rangeMmLen}`);
  }
  if (pointFlagsLen !== pointCount) {
    throw new Error(`pointFlagsLen mismatch: ${pointFlagsLen} != ${pointCount}`);
  }
  const expMaskLen = hasRangeMask ? rangeHeight * rangeWidth : 0;
  if (rangeMaskLen !== expMaskLen) {
    throw new Error(`rangeMaskLen mismatch: ${rangeMaskLen} != ${expMaskLen}`);
  }
  if (jsonLen === 0) {
    throw new Error("Empty LDSF JSON payload");
  }

  const expectedTotal =
    LDSF_HEADER_SIZE +
    xyzLen +
    intensityLen +
    rangeMmLen +
    pointFlagsLen +
    rangeMaskLen +
    jsonLen;
  if (byteLength !== expectedTotal) {
    throw new Error(`LDSF total length mismatch: ${byteLength} != ${expectedTotal}`);
  }

  let off = byteOffset + LDSF_HEADER_SIZE;

  const readFloat32 = (byteOff, count) => {
    if (count === 0) return new Float32Array(0);
    if (byteOff % 4 === 0) {
      return new Float32Array(buf, byteOff, count);
    }
    return new Float32Array(buf.slice(byteOff, byteOff + count * 4));
  };

  const readUint16 = (byteOff, count) => {
    if (count === 0) return new Uint16Array(0);
    if (byteOff % 2 === 0) {
      return new Uint16Array(buf, byteOff, count);
    }
    return new Uint16Array(buf.slice(byteOff, byteOff + count * 2));
  };

  const xyz = readFloat32(off, pointCount * 3);
  off += xyzLen;

  const intensity = hasIntensity ? readFloat32(off, pointCount) : null;
  off += intensityLen;

  const rangeMm = readUint16(off, rangeHeight * rangeWidth);
  off += rangeMmLen;

  const pointFlags = new Uint8Array(buf, off, pointFlagsLen);
  off += pointFlagsLen;

  const rangeMask = hasRangeMask ? new Uint8Array(buf, off, rangeMaskLen) : null;
  off += rangeMaskLen;

  const jsonView = new Uint8Array(buf, off, jsonLen);
  const state = JSON.parse(textDecoder.decode(jsonView));

  return {
    version,
    hdrFlags,
    decimation,
    isLive,
    pointCount,
    rangeHeight,
    rangeWidth,
    xyz,
    intensity,
    rangeMm,
    pointFlags,
    rangeMask,
    state,
  };
}

/**
 * 与 src/human_fall_detection/core/range_live.py::preview_rgb 完全一致的色标（0.1–8.0 m）。
 */
export function rangeToPreviewRgb(rangeMm) {
  if (!Number.isFinite(rangeMm) || rangeMm <= 0) {
    return [0, 0, 0];
  }
  const rangeM = rangeMm / 1000.0;
  const t = clamp((rangeM - 0.1) / 7.9, 0.0, 1.0);
  const r = Math.trunc(255.0 * (1.0 - t));
  const g = Math.trunc(255.0 * (1.0 - Math.abs(2.0 * t - 1.0)));
  const b = Math.trunc(255.0 * t);
  return [r, g, b];
}

/**
 * 预计算 0..65535 mm 的 RGBA 查找表（256 KB），实现高速 2D Canvas 渲染。
 */
export function buildPreviewLutRgba() {
  const lut = new Uint8ClampedArray(65536 * 4);
  for (let mm = 0; mm < 65536; mm++) {
    const o = mm * 4;
    if (mm === 0) {
      lut[o] = 8;
      lut[o + 1] = 12;
      lut[o + 2] = 18;
      lut[o + 3] = 255;
    } else {
      const [r, g, b] = rangeToPreviewRgb(mm);
      lut[o] = r;
      lut[o + 1] = g;
      lut[o + 2] = b;
      lut[o + 3] = 255;
    }
  }
  return lut;
}

/**
 * 显示像素 (col, row) 转回原生传感器 (nativeRing, nativeCol)，对应 nativeTransform: rotate180。
 */
export function displayPixelToNative(col, row, width = 256, height = 192) {
  const c = clamp(Math.floor(col), 0, width - 1);
  const r = clamp(Math.floor(row), 0, height - 1);
  return {
    displayCol: c,
    displayRow: r,
    nativeRing: height - 1 - r,
    nativeCol: width - 1 - c,
  };
}

function normVec3(v) {
  const n = Math.hypot(v[0], v[1], v[2]);
  if (!Number.isFinite(n) || n < 1e-9) return [0, 0, 1];
  return [v[0] / n, v[1] / n, v[2] / n];
}

function crossVec3(a, b) {
  return [
    a[1] * b[2] - a[2] * b[1],
    a[2] * b[0] - a[0] * b[2],
    a[0] * b[1] - a[1] * b[0],
  ];
}

/**
 * 与 session_compare.py::display_basis 一致的配平正交基。
 */
export function computeDisplayBasis(normal) {
  const up = normVec3(normal);
  let fx = 1.0 - up[0] * up[0];
  let fy = -up[0] * up[1];
  let fz = -up[0] * up[2];
  if (Math.hypot(fx, fy, fz) < 1e-6) {
    fx = -up[1] * up[0];
    fy = 1.0 - up[1] * up[1];
    fz = -up[1] * up[2];
  }
  const forward = normVec3([fx, fy, fz]);
  const left = normVec3(crossVec3(up, forward));
  return { forward, left, up };
}

/**
 * 将原始传感器点 (x, y, z) 映射到 Three.js 世界坐标（+X=前, +Y=上, -Z=左）。
 */
export function rawPointToWorld(x, y, z, displayPlane = null, useLeveling = true) {
  if (!useLeveling || !displayPlane || !Array.isArray(displayPlane.normal)) {
    return [x, z, -y];
  }
  const { forward, left, up } = computeDisplayBasis(displayPlane.normal);
  const off = Number(displayPlane.offsetM || 0);
  const lx = x * forward[0] + y * forward[1] + z * forward[2];
  const ly = x * left[0] + y * left[1] + z * left[2];
  const lz = x * up[0] + y * up[1] + z * up[2] + off;
  return [lx, lz, -ly];
}

/**
 * 构造 Three.js Column-Major 4x4 矩阵：raw sensor (x, y, z) -> Three.js 世界 (X, Y, Z)。
 */
export function computeLevelMatrixColMajor(displayPlane = null, useLeveling = true) {
  if (!useLeveling || !displayPlane || !Array.isArray(displayPlane.normal)) {
    // raw (x, y, z) -> (x, z, -y)
    // col0=[1,0,0,0], col1=[0,0,-1,0], col2=[0,1,0,0], col3=[0,0,0,1]
    return [1, 0, 0, 0, 0, 0, -1, 0, 0, 1, 0, 0, 0, 0, 0, 1];
  }
  const { forward, left, up } = computeDisplayBasis(displayPlane.normal);
  const off = Number(displayPlane.offsetM || 0);
  // X_three = dot(p, forward), Y_three = dot(p, up) + off, Z_three = -dot(p, left)
  return [
    forward[0], up[0], -left[0], 0,
    forward[1], up[1], -left[1], 0,
    forward[2], up[2], -left[2], 0,
    0, off, 0, 1,
  ];
}

export const VIEW_PRESETS = {
  front: { key: "1", label: "正面" },
  side: { key: "2", label: "侧面" },
  top: { key: "3", label: "俯视" },
  sensor: { key: "4", label: "传感器" },
  free: { key: "5", label: "立体" },
};

/**
 * 根据目标世界坐标与传感器原点计算平滑补间相机姿态（参考 pc_apps/demo_viewer/build.py）。
 */
export function computePresetPose(preset, targetWorld = [2.5, 0.9, 0.0], sensorWorld = [0, 1.35, 0], dist = 4.6) {
  const tx = Number(targetWorld[0] ?? 2.5);
  const ty = Number(targetWorld[1] ?? 0.9);
  const tz = Number(targetWorld[2] ?? 0.0);
  const target = [tx, ty, tz];

  switch (preset) {
    case "front":
      return {
        position: [tx + dist, ty + 0.35, tz],
        target,
      };
    case "side":
      return {
        position: [tx, ty + 0.35, tz + dist],
        target,
      };
    case "top":
      return {
        position: [tx + 0.05, ty + dist * 1.18, tz],
        target,
      };
    case "sensor": {
      const sx = Number(sensorWorld[0] ?? 0);
      const sy = Number(sensorWorld[1] ?? 1.35);
      const sz = Number(sensorWorld[2] ?? 0);
      return {
        position: [sx - 0.15, sy + 0.15, sz],
        target,
      };
    }
    case "free":
    default: {
      const yaw = -0.78;
      const pitch = 0.40;
      const horiz = dist * Math.cos(pitch);
      return {
        position: [
          tx + horiz * Math.cos(yaw),
          ty + dist * Math.sin(pitch) + 0.4,
          tz + horiz * Math.sin(yaw),
        ],
        target,
      };
    }
  }
}

export const FALL_STATE_MAP = {
  upright: { label: "直立形态", short: "直立", tone: "ok", color: "#45d09e" },
  descending: { label: "高度下降中", short: "下降", tone: "warn", color: "#ffb84d" },
  low_posture_unclassified: { label: "低姿待分类", short: "低姿", tone: "warn", color: "#ff9b42" },
  suspected: { label: "跌倒疑似（几何证据）", short: "疑似跌倒", tone: "danger", color: "#ff5c6c" },
  confirmed: { label: "已确认（本系统禁用）", short: "已确认", tone: "danger", color: "#ff334b" },
  recovering: { label: "恢复站立中", short: "恢复", tone: "info", color: "#58b4ff" },
  unknown: { label: "状态未知", short: "未知", tone: "muted", color: "#5b6a7e" },
};

export const POSTURE_MAP = {
  standing: { label: "站立形态", short: "站", tone: "ok" },
  sitting: { label: "坐/蹲形态", short: "坐", tone: "info" },
  lying_pending: { label: "低水平观察中", short: "低姿", tone: "warn" },
  lying_candidate: { label: "持续水平低姿", short: "躺", tone: "danger" },
  transitioning: { label: "姿态过渡中", short: "过渡", tone: "warn" },
  vertical_surface: { label: "竖直表面（非站立）", short: "竖面", tone: "muted" },
  unknown: { label: "姿态未知", short: "未知", tone: "muted" },
};

export const BELIEF_STATE_MAP = {
  CONFIRMED_HUMAN: {
    label: "多证据物理一致（非真值）",
    short: "物理一致(非真值)",
    tone: "ok",
    color: "#38d9a9",
  },
  CANDIDATE_HUMAN: {
    label: "物理候选（累积中）",
    short: "候选",
    tone: "warn",
    color: "#f5b942",
  },
  UNKNOWN: {
    label: "未知 / 证据不足",
    short: "未知",
    tone: "muted",
    color: "#5b6a7e",
  },
  NONE: {
    label: "无实测目标",
    short: "无目标",
    tone: "muted",
    color: "#334155",
  },
};

export const PRIOR_CLASS_MAP = {
  standing_geometry: "站立几何相容",
  sitting_geometry: "坐蹲几何相容",
  lying_geometry: "躺卧几何相容",
  fragment: "碎片簇（硬否决）",
  planar_structure: "刚性平面结构（硬否决）",
  hanging_or_adhesion: "悬空或支架粘连（硬否决）",
  not_compatible: "几何不相容",
  unknown: "无法评估",
};

export const REASON_CODE_MAP = {
  // 跌倒状态机 & 姿态层（与 pc_apps/demo_viewer/pseudo_live.html 对齐并扩展）
  measured_descent: "此前测得下降",
  posture_transition_supported: "近期有站立形态",
  sustained_low_posture: "低位姿态持续达到时间要求",
  lying_pose_supported: "水平低位姿态满足条件",
  height_dropping: "高度下降中",
  low_posture_without_confirmed_descent: "无已确认的下降证据",
  low_posture_without_lying_pose: "水平低位姿态尚不满足",
  low_posture_duration_pending: "低位持续时间不足",
  target_not_locked: "当前没有锁定的目标",
  target_held_gap: "当前目标暂时缺测",
  target_ambiguous: "目标关联存在歧义",
  ground_unavailable: "地面不可用",
  observation_gap: "观测中断",
  baseline_not_ready: "站立基线未建立",
  posture_not_upright: "姿态不足以判断直立",
  recovery_posture_unknown: "恢复姿态未知",
  rising_toward_baseline: "正在恢复",
  standing_posture: "站立形态",
  recovered: "已恢复站立",
  sustained_low_horizontal_geometry: "持续低矮水平几何",
  lying_duration_pending: "水平低位计时累积中",
  posture_not_evaluable: "几何姿态暂不可评估",
  posture_standing: "站立姿态",
  sustained_standing: "持续站立姿态",
  posture_sitting: "坐蹲姿态",
  sustained_sitting: "持续坐蹲姿态",
  posture_vertical_surface: "竖直表面形态",
  sustained_vertical_surface: "持续竖直表面",
  posture_transition: "姿态已完成过渡",
  posture_transition_pending: "姿态过渡观察中",
  measurement_or_ground_unavailable: "实测点或地面不可用",

  // human_physical_v1 证据与拒绝原因码
  prior_standing_compatible: "剖面与站立几何相容",
  prior_sitting_geometry: "剖面与坐蹲几何相容",
  prior_lying_geometry: "剖面与躺卧几何相容",
  prior_fragment: "碎片簇（过小）",
  prior_planar_structure: "平面结构拒识",
  prior_hanging_or_adhesion: "悬空/粘连拒识",
  prior_not_compatible: "尺寸/剖面不相容",
  prior_unknown_neutral: "先验中性/点不足",
  profile_balanced_vertical_support: "10层垂向填充均衡",
  surface_curved_strong: "表面法向呈强曲面分布",
  surface_curved_moderate: "表面法向呈中等曲面分布",
  surface_normal_planar_penalty: "法向集中于单/双平面（硬否决）",
  nonrigid_articulation_supported: "非刚体内部相对运动支持",
  kinematics_uncalibrated_neutral: "运动学噪声底未标定（中性）",
  soft_rigid_moving_object: "刚体整体平移软惩罚",
  soft_periodic_oscillation: "周期往复振荡软惩罚",
  soft_suspended_oscillator: "悬空周期摆动软惩罚",
  frozen_during_unobserved_frame: "缺测帧冻结置信度",
  gap_ignored_bottom_ground_supported: "底部贴地，忽略中段遮挡空洞",
  vertical_profile_gap_discontinuity: "垂向剖面存在离地断层",
  low_normalized_vertical_fill: "垂向填充率过低",
  thin_bridge_lollipop_adhesion: "细杆/支架粘连结构",
  top_heavy_hanging_mass_concentration: "头重脚轻悬挂分布",
  bottom_detached: "整体离地悬空",
  surface_normal_single_plane: "单平面内点比例过高",
  surface_normal_dual_plane_box: "双正交平面盒体",
  surface_normal_flat_horizontal_plane: "平坦水平桌面/台面",

  // 开机直接算运动学跌倒原因码
  FAST_KINEMATIC: "快速运动学下坠+坍塌",
  SLOW_DESCENT: "缓慢下坠+持续低位坍塌",
  personal_upright_baseline_ready: "个人直立基线已建立",
  collapsed_low_posture_sustained: "体态坍塌低位持续中",
  short_measurement_gap_held: "短缺测保留轨迹（不累计证据）",
  instant_frame0_bootstrap: "首帧免空场初始化完成",
  no_locked_human_target: "当前无已锁定人体目标",
  kinematic_upright: "运动学直立跟踪中",
  kinematic_descending: "运动学高度下降中",
  kinematic_suspected: "运动学疑似倒地（非真值）",

  // full_body_recovery 状态与拒绝原因
  recovered_ok: "局部肢体回收成功",
  no_addition: "无新增可连接点",
  expansion_ratio_exceeded: "拒绝：膨胀比例超限",
  competing_observed_track: "拒绝：邻近有其他实测轨迹竞争",
  envelope_surge_exceeded: "拒绝：水平包络骤增",
  added_planar_surface_leakage: "拒绝：新增点泄漏至刚性平面",
  planar_leakage_detected: "拒绝：检测到平面泄漏",
  background_unavailable: "拒绝：背景不可用",
  ground_unavailable_or_unbound: "拒绝：地面未绑定",
  empty_core_rows: "拒绝：目标核心点为空",
};

export function translateReasonCode(code) {
  return REASON_CODE_MAP[code] || code;
}

export function translateFallState(state) {
  return FALL_STATE_MAP[state] || { label: String(state || "未知"), short: "未知", tone: "muted", color: "#5b6a7e" };
}

export function translatePosture(state) {
  return POSTURE_MAP[state] || { label: String(state || "未知"), short: "未知", tone: "muted" };
}

export function translateBeliefState(state) {
  return BELIEF_STATE_MAP[state] || BELIEF_STATE_MAP.UNKNOWN;
}
