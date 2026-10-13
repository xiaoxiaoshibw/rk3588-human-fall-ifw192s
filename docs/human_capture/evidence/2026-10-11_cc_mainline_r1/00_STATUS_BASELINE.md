# CC 主线 R1 —— 现有离线 Demo 真实效果 + 骨架实现状态基线

2026-10-11（Asia/Shanghai）· writer：Claude Code（CC）。用户指令：Q01 已 CLOSED，主线转为**优先完成离线人体检测效果展示与骨架研发，禁止部署**。本文件记录开工前实测现状，作为后续开发的基线。所有改动仅限本证据目录新增，未触碰 `pc_apps/`、`src/`、`sidequests/human_fusion_lab` 任何源文件（轮到 Codex 写的 SCOPE_AUDIT 冻结文件原样保留）。

## 1. 已实测的现有 Demo（不写代码，只验证+截图）

两个本地服务均已确认在跑（127.0.0.1，仅本机）：

- **Demo V2**：http://127.0.0.1:8798 —— `server_v2.js`，`version:2`，默认 xgb69_candidate，9 会话全列，S9 标 `UNKNOWN + ⚠SHA`。
- **Demo V1**：http://127.0.0.1:8791 —— `server.js`，默认 xgb69_candidate，6 detector 含 `xgb69_unique`（一对一跟踪）与 `geometry`（geometry(post)）。

V2 已具备用户第一阶段要求的大部分：**同一帧同步** 3D / 俯视 XY / 侧视 XZ 三视图、原始点云/前景/候选/分类/轨迹/GT 独立开关、逐帧+拖动+逆向 seek（generation 递增清 tracker）、四模型同候选并列分数（RF51原 0.34/RF51研 0.36/RF69 0.33/XGB 0.72 直接同屏）、失败案例菜单（PERSON_MISS/FURNITURE_FALSE_POSITIVE/MODEL_DISAGREEMENT 直接跳帧）、2D/3D 人工标注草稿（圈真实点、下载/导入/撤销，不冒称 GT）。显式声明 UNCALIBRATED——骨架轴不冒充解剖关节。

## 2. 真实数据与 GT 缺口（与 Codex R9 审计一致，本轮独立复算）

九组真实采集，共 **2605 帧**，真实点云 `points.bin` 只读，input SHA 绑定逐帧核验。无合成数据冒充。

| 会话 | 帧 | GT已知 | GT未知 | 标注覆盖率 |
|---|---:|---:|---:|---:|
| S1 空房间+家具 | 304 | 304 | 0 | 100% |
| S3 近距行走 | 258 | 258 | 0 | 100% |
| S3 远距行走 | 464 | 99 | 365 | 21% |
| S4 走-停-走 | 239 | 11 | 228 | 4.6% |
| S5 原地转身 | 202 | 6 | 196 | 3.0% |
| S6 遮挡 | 238 | 71 | 167 | 29.8% |
| S7 远 5m | 251 | 12 | 239 | 4.8% |
| S8 长时间静止 | 523 | 53 | 470 | 10.1% |
| S9 双人交叉 | 126 | 0 | 126 | 0%（SHA 绑定失配，占位哈希） |
| **合计** | **2605** | **814** | **1791** | **31.2%** |

**31.2% 标注覆盖率是最大瓶颈**：68.8% 的帧（绝大多数是人体活动帧）只能报 UNKNOWN，既不能被算作检测成功，也不能被算作漏检，无法产出有意义的召回率。S9 双人关键场景完全无法验证。

## 3. 九会话真机实测结果（V2 COMPARISON.json，18 runs / 5210 ticks）

### XGBoost（默认）已标帧表现
- 近距行走 258/258；静止 53/53；远 5m 12/12；走-停-走 11/11；原地转身 6/6；遮挡 65/71。
- S1 空房间+家具：0 候选 FP / 0 轨迹 FP（全 304 帧）——对照原 RF51 的 604/600。
- 所有 9 会话 duplicate_ids=0（V2 unique tracker 生效）。

### 原 RF51 基线（生产模型）虚警实证
- S1：家具 FP **604 候选 / 600 轨迹**；近行走 393 FP；远距 227 FP。生产模型在此数据上不可靠。

### 逐层漏检归因（R8/R9，真实数据）
- **RAW**：S6 f128 人贴桌沿只剩 **17 点**，f91 只剩 297 点/55 连续 → 点数不足是漏检根源之一。
- **BG**：S6 f187 保留 9/260、f188 保留 14/268 → 避嫌区过度保留。
- **PROPOSAL**：S6 f91 有 55 点但无提案（最小点数门限）→ 提案层漏检。
- **CLASSIFIER**：S6 f128 提案存在但分数 0.33 < 0.35 门限 → 边界分数漏检。
- **TRACKER**：确认启动损失单独计，不一股脑归 RF。
- **DISPLAY**：仅软件渲染验证，真人级展示损失 UNKNOWN。
- 详见 `sidequests/human_fusion_lab/results/ATTRIBUTION.json`。

### 已知候选比对 vs 全链召回（诚实边界）
固定候选对比（rf51_baseline / rf51 / rf69 / xgb / pointnet_shadow）测的是**候选级 TP**，不含 proposal 漏检，**不能当端到端召回**。RETROSPECTIVE_SESSION_HOLDOUT：回顾性留出，测试会话历史已被查看；**陌生人员 / 独立家具 / 新场景泛化 UNKNOWN**。

## 4. 骨架 / 姿态当前实现状态

**没有任何可运行的骨架/姿态检测。** 唯一存在的是 HR-SKELETON-OFFLINE R1/R3 工具（SUBMITTED/BLOCKED，未 ACCEPTED，2026-10-08/09，写在一批**不同的、更旧的** cap_20261008_* 会话上）：

- `skeleton.py`：全有效成员纯 XY 标准化 + 原 Z + 一一 row/global 映射 + 无符号 PCA 描述；5 个固定槽（HEAD / UPPER_TORSO / CHEST / PELVIS_REGION / LOWER_REGION）+ 可分离时 A/B 下肢共至多 7 槽。HEAD 仅在人工明确标 HEAD_CONFIRMED 区域时取支撑中心，**不做自主头部检测**。
- 独立 `SkeletonTracker`：参考坐标滤波、实际整数 stamp 差值、EMA/跳变/缺失/重获、换键/seek 清状态；不改原 human Tracker。
- 合成形状验收 PASS（7 节点、逆变换 0m、支撑独立复算）；**真人输出全 BLOCKED_GT**——120 分支行 / 336 簇 / 1680 槽全部未审、valid=0（SKO-04/09/10/11/14/15 全部 BLOCKED）。
- 解剖关键点：NOT_ESTIMATED；四肢：UNKNOWN；姿态：UNKNOWN；标定：UNCALIBRATED（既有研究 R/T，物理精度未验收）。

**这套骨架工具与当前 9 会话 fusion 管线是两套独立系统**，数据不共享。骨架当前离"能在真人上跑"差一个**人工 GT 标注 + 复核**的前置门，而不是差算法。

## 5. 证据资产

本目录六张真实浏览器截图（127.0.0.1:8798，默认 XGB）：

| 文件 | 内容 |
|---|---|
| shot_success_walk_near_f100.png | 近距行走成功：GT 绑定 REVIEWED、TP=1 FP=0、四模型同候选分数 |
| shot_furniture_fp_baseline_f0.png | S1 空房间家具误检：原 RF51 807~1637 分判人；XGB 同候选 0.34 全拒 |
| shot_miss_occlusion_f91.png | S6 f91 漏检：PROPOSAL 层，297 点低于提案门限 |
| shot_miss_occlusion_f128_xgb.png | S6 f128 漏检：RAW 17 点 + 分类 0.33<0.35 |
| shot_s9_unknown_twoperson_f30.png | S9 双人：GT UNKNOWN、无人确认 |
| shot_still_s8_f200_xgb.png | S8 静止成功：288 点、0.61 CONFIRMED、t1 连续、未知帧不计入 |

来源证据（只读引用）：`sidequests/human_fusion_lab/results/{COMPARISON,ATTRIBUTION,DATASET_MANIFEST,OBSERVABILITY,...}`、`docs/human_capture/evidence/2026-10-11_human_fusion_demo_v2_r1/`、骨架 `docs/human_capture/evidence/2026-10-09_hrskeleton_offline_r1/REVIEW.md`。

## 6. 后续开发方向（待执行）

按用户给定顺序，下一阶段：

1. 补 GT 标注与复核入口（把 68.8% 未知帧中最有价值的段落补标，先 S9 双人 + S6 遮挡 + 远/静止），把"召回率"从空话说回来。
2. 在 V2 unique tracker 基础上固定融合，关 21 次重复 ID；让 geometry(post) 与 RF 在 tracker 前同源投票，消掉 98.7% track_confirmed 不一致。
3. 打通"骨架工具 ← fusion 九会话已确认人体簇"的数据通道，先静态躯干部位的粗骨架糖葫芦验证，再评估四肢/关节可观测性，不凭空拟合。
4. 优化 RF/XGB/PointNet（PointNet 已实测 3ms 内、不优 XGB、保留 shadow），用无泄漏数据验证。

D01 设备/部署/生产替换/现场发布 / P01 真人效果确认：**NOT_RUN/BLOCKED**，全程保持。
