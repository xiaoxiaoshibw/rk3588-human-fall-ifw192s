# 骨架当前实现状态 —— 最终事实（CC 主线第三轮核实）

2026-10-11 · writer: CC。纠正我此前任何过度/不足表述。全部结论含实测命令。

## 一、骨架当前实现状态（回答用户直接问题）

**没有任何已部署/已验收的骨架或姿态识别。** 唯一代码资产是 HR-SKELETON-OFFLINE 的 `skeleton.py`（A–F 离线可行性工单）：

- **状态**：SUBMITTED / **BLOCKED**，**未 ACCEPTED**。它跑在一批**更旧的** `cap_20261008_*` 会话（与当前 fusion 9 会话 `cap_20261010_*` 不同源）。
- **真人输出全部 BLOCKED_GT**：336 簇 / 1680 槽全未审、valid=0（SKO-04/09/10/11/14/15 全 BLOCKED）。
- 解剖关键点 **NOT_ESTIMATED**、四肢 **UNKNOWN**、姿态 **UNKNOWN**、标定 **UNCALIBRATED**。

### 设计形态（读完源码后的准确描述）
`skeleton.py` 提供 `normalize()`（纯 XY 平移到簇质心 + row/global 映射 + 逆变换核验）、`observe()`（Z 带内中位数 + 点/跨度门）、`nodes()`（5 固定槽 + 至多 LOWER_A/B）、独立 `SkeletonTracker`（EMA/跳变/缺失/重获）。

**关键设计**：`nodes()` 对**每一个槽**（不止 HEAD）都要求 `review[slot].visibility=='VISIBLE'` 的人工可见性标记，否则一律 `VISIBILITY_UNKNOWN` 拒绝。即它是 **GT 门控的"已知这是人簇后的节点提取器"**，不承担自动判人。冻结参数 `prototype_params_v1.json`：站立 Z 带 UPPER_TORSO[1.15,1.4] / CHEST[0.95,1.15] / PELVIS[0.55,0.85] / LOWER[0.1,0.55]；`node_max_xy_span_m=0.8`、`node_min_points=6`。

## 二、打通探测实测（fusion 九会话确认人簇 → skeleton）

适配器 `run_skeleton_adapt.js`：fusion `CONFIRMED_HUMAN` 候选的真实成员点按 `normalize()` 输入形态适配。三会话（近走/静止/遮挡，xgb69）：

| 会话 | 已确认人候选 | 固定 Z 带点数 | 说明 |
|---|---:|---|---|
| 近走 175429 | 277 | 上身284/胸220/骨盆272/下身235 | 人形完整，z 0.25–1.6m |
| 静止 180557 | 523 | 类似 | 站立，z span ~1.3m |
| 遮挡 180235 | 201 | 部分带不足 | 部分帧仅头/肩，稀疏 |

### 两个实测结论（直接调 `observe()`，15 簇 × 4 带）

| 带 | valid(OBSERVED_REGION_MEDIAN) | 拒绝 |
|---|---:|---|
| CHEST | 11/15 | 4× CONFLICTING_SPATIAL_SUPPORT |
| UPPER_TORSO | 10/15 | 5 |
| PELVIS_REGION | 12/15 | 3 |
| LOWER_REGION | 11/15 | 4 |

- **正**：固定 Z 带**确实落在人体带**，底层 `observe()` 对 ~73% 的真实人簇节点给出有效中位数支撑 → **粗躯干骨架（胸/骨盆/下身中位点）在这批点云上可观测**。
- **负**：27% 因 `xy_span>0.8m` 被拒——**手臂/肩展使上身 XY 跨度达 0.99–1.04m**。冻结 `node_max_xy_span_m=0.8` 是对旧会话几何定的，**对 IFW192S 当前人簇未校准**。这本身是一次"雷达到地面/人体几何坐标核验"：**高度落在人体带（z 带有效），但 XY 跨度门对真实肩臂展过严**（手的水平外展是合法的，不应等于 CONFLECT）。
- **全 0 适配**只是 `nodes()` 的人工 visibility 门控被空 review 触发，非坐标失守。

## 三、因此骨架推进的现实路径（离线，不虚构）

1. **短期可交付**：用 fusion 已确认人簇 + 直接 `observe()`（绕过空 review），产出**胸/骨盆/下身 3–4 个粗节点**的真实轨迹可视化（点支撑中位数），明确标注"区域中位点，非解剖关节，未标定"。这是可验证的粗骨架。
2. **HEAD**：保持 BLOCKED——需人工 `HEAD_CONFIRMED` 标可见头区，不自主把最高点当 HEAD（举手时最高点是手）。
3. **校准**：`node_max_xy_span_m` 需按 IFW192S 站/走/遮挡真实几何重估（而非沿用 0.8）；此时才谈"可靠标定"。
4. **姿态（站/坐/躺/跌倒）**：在粗节点稳定后再做；不允许凭空拟合不可观测关节。
5. **GT 门控**：skeleton 的 visibility 门需人工标注生产——指向用户的"修 GT 绑定、提供人工标注和复核入口"。

## 四、事实纠正记录（透明）
- 我先前"可观测 100%"是 JS 端 band 点数顶满，未过 `observe()` 跨度门；
- "0/40 invalid"是空 review 触发 visibility 门控，非坐标失守；
- 真实是 **~73% 节点可观测 + xy_span 门未校准**。

D01/P01 NOT_RUN/BLOCKED。证据：`run_skeleton_adapt.js`、`skeleton_adapt/`、本目录报告与命令输出。
