# CC 主线 R1 汇总 —— 离线人体检测展示 + 骨架研发（禁止部署）

2026-10-11 · writer: CC。用户四步指令：**(1)完善离线Demo (2)修识别链 (3)骨架研发 (4)交付亲眼可见的真实效果**。全程**离线只读 fusion/skeleton/captures，未改任何链源文件、未部署**（D01/P01 NOT_RUN/BLOCKED）。

## 复跑入口
```
cd sidequests/human_fusion_lab
node run_r3_all.js
```

## 已交付（10 张真实图，已逐张送达）

### A. 现有 Demo 真实效果（阶段1）
| 图 | 内容 |
|---|---|
| shot_success_walk_near_f100 | XGB 近走：GT 绑定 REVIEWED，TP=1 FP=0，四模型同候选分数 |
| shot_furniture_fp_baseline_f0 | 原 RF51 家具误检 807-1637 分判人；XGB 同候选 0.34 全拒 |
| shot_miss_occlusion_f91 | PROPOSAL 层漏检（点数<门限） |
| shot_miss_occlusion_f128_xgb | RAW 17 点不足 + 分类 0.33<0.35 |
| shot_s9_unknown_twoperson_f30 | S9 双人 GT UNKNOWN |
| shot_still_s8_f200_xgb | 静止成功，t1 连续 |

指向入口：Demo V2 `http://127.0.0.1:8798`、V1 `http://127.0.0.1:8791`（本机 127.0.0.1）。

### B. 识别链诊断（阶段2）—— 权威定案
| 用户交办 | 定案 | 证据 |
|---|---|---|
| 重复 ID | **真实**：裸默认 tracker rf51_baseline 恰 **21** 次（复现 R5–R8），rf51_candidate 54、xgb 25；根因= FusionTracker 贪婪单绑（`core/fusion.js:37-77`）无全局一对一；**unique tracker 全 0** | R3_DIAGNOSTICS.json、dup_f0.png |
| 确认票 | **无需修**：真实 FusionTracker.votes 复算违反=0，3/5/3 自洽 | 三轮核实 |
| geometry(post) | **当前已修**：Q01 同口径 6520 候选 mismatch=**0**（Q01 称 98.7%）；`detector.js:13-17` 补丁已修 | R3_GEOMETRY |
| BG/PROPOSAL/CLASSIFIER 漏检归因 | 全局已标 FN：CLASSIFIER 65 + PROPOSAL 49 | R3 layer_miss |

逐帧缺陷可视化（俯/侧/3D，聚焦缩放）：dup_f0.png、miss_f91.png、furn_f0.png、ok_f100.png（results/R3_VIZ/*.svg 全套）。

### C. 骨架研发（阶段3）—— 可验证粗骨架首次接通
| 图 | 内容 |
|---|---|
| skel_f100.png | 近走 f100：4/4 节点全 valid，CHEST/PELVIS/LOWER 紫色骨架线垂直，z=0 地面线 |
| skel_f200.png | 静止 f200：2/4 valid，上身因跨度>0.8m 保守拒绝（不显示不错放） |
| skeleton_coarse/skel_f60 | 遮挡：一簇 0/4、一簇 4/4（稀疏可见性真实分化） |

**首次把 fusion 已确认人簇成员点接入 skeleton.py observe()，产出真实可验证粗骨架**（非合成、非旧会话）。诚实标注：节点=区域中位点支撑、非解剖关节、UNCALIBRATED、HEAD 未显示（需人工 HEAD_CONFIRMED）。

**标定核验真实发现**：`node_max_xy_span_m=0.8` 对 IFW192S 真实肩臂展（0.99-1.04m）未校准，27% 节点因此保守拒绝 → 需按真实几何重估（属"雷达到地面/人体几何核验"）。

## 关键诚实边界
- GT 覆盖来自 reviewed 文件绑定（元数据资格），非独立物理真值；传播观测相关。S9 双人 0% 且 SHA 失配。
- "候选人簇点喂骨架"是**离线可行性探针**，非验收；skeleton 本身 SUBMITTED/BLOCKED 未 ACCEPTED。
- 所有图为真实点云渲染，零合成。
- 未修任何链源文件——重复 ID 修法（unique tracker 一对一）已就绪待"采用为默认 + S9/遮挡验证不劣化"。

## 工具资产（新增，可复跑）
- `run_r3_diagnostics.js`（重复ID/漏检/几何一致性）、`render_r3_frames.js`（SVG 三视图+聚焦缩放）、`run_skeleton_adapt.js`（骨架可观测性）、`render_skeleton_coarse.js`（粗骨架节点图）、`run_r3_all.js`（统一入口）、`r3_viz_jobs.json`。
- 证据：`R3_*.json`、`results/R3_VIZ/`、`skeleton_adapt/`、`skeleton_coarse/`。
- 文档：`00_STATUS_BASELINE.md`、`01_R3_TRACKER_GEOMETRY_RECONCILE.md`（三轮纠错定案）、`02_SKELETON_STATE_AND_ADAPT.md`、本 SUMMARY。

## 下一步建议（离线，待用户确认后推进）
1. **采用 unique tracker 为默认 fusion tracker**，在 S9 双人 + 遮挡会话实测不劣化召回后定案（修 21/54/25 重复 ID）。
2. GT 标注+复核入口扩量（S9 重绑 SHA、低覆盖会话 S5 3%/S4 4.6%/S7 4.8% 优先），把"召回"从 31% 覆盖说起。
3. 校准 `node_max_xy_span_m` 按真实几何重估；HEAD 人工标注打通后做全身粗骨架。
4. 算法优化（48正+1430负、会话分组冻结）：减 S1 原 RF 604 FP、修 S3 远 FN65、S6 遮挡 FN。
5. 粗节点稳定后再做 站/坐/躺/跌倒 状态判断。
