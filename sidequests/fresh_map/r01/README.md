# FRESH-MAP r01 — 增量新鲜度占用图（sidequest，非主线交付物）

## 定位

无监督时序表示/可视化实验。**不是**学习分类器、不是生产件；与已关闭的 limb/ML 跨域、
DET 归档支线不冲突。起因：`docs/human_capture/evidence/2026-10-15_traditional_cluster_ml_effect_r1/TRADITIONAL_CLUSTER_ML_EFFECT_REPORT.md`
判定"聚类聚不到人"的根源 = **在线硬背景把静立的人当房间抹掉（97~98% 吞没）**，其建议方向
"背景只作特征/风险，不做不可逆硬删"。用户 2026-10-15 拍板本验证："长期不动的背景灰度化，
运动/新出现物体打新鲜度标签，随静止渐黑"。本支线是该方向的第一个工程验证。

计划文件：`C:\Users\30680\.claude\plans\cached-marinating-octopus.md`（M0+M1 数字先行；
M2 浏览器目视页暂缓，数字过了另单）。

## 机理（三态 + 永不删除）

- **背景层**：批式一次、不可变参考图（复用 `human_pipe_lib.build_reference_map`，occ≥0.5 入图），
  只决定"灰度/暗记"配色与 ref_sup 判定，**无删除权**。来源 = 外部空场会话或本会话前 K 帧 warmup。
- **新鲜度层**（`fresh_lib.js`，纯增量）：每 3D 体素（XY 0.15m/z 0.12m，工作带 z∈[0.10,2.50]）
  持 `{慢参考形心 rx/ry/rz, occ, f∈[0,1], event_run, ever_event, ref_sup}`。
  - 事件判据（三门，全过才候选帧）：支持门 n≥2 点；ref 支撑格→位移门（多数点距慢参考>0.12m），
    非 ref 格发过事件前→"新出现延续观察"（首见/连续帧），发过事件后→位移门；
    滞回门 连续≥2 候选帧 → f=1。
  - 衰减：非发火帧 `f *= exp(-dt/τ)`（dt=bag_time_sec 真实秒；乱序钳 0；linear 可选）。
  - **HOT 冻结**：f≥hot_f_min 期间慢参考/occ EMA 冻结——防止复刻"在线背景慢慢吃掉静立者"。
  - 三态：HOT（f≥0.15，热度渲染预留）/ **GHOST**（¬ref_sup ∧ ever_event：曾经动/新出现、
    后来停 = 静立者证据，永久保留；当前帧无点落入则天然不进候选）/ COLD_BG（其余：灰度背景）。
- **目标级记忆**（`FreshMemory`）：候选点→XY 柱聚类→锚点库，语义照搬
  `human_core/engine.js` retention（window_confirm=3 / timeout_s=180 / max_lost_for_retain=30 /
  hot_cell_radius 0.4m，不改值）。GHOST 超窗/与人融合位的证据由此层续命。
- 候选集 = HOT ∪ GHOST ∪ live 锚点半径内的点。全程无删除。

## 诚实边界（预注册）

1. 从 warmup 起全程静立的人会被参考图当家具（无监督原理上不可分，limb v1..v6 教训）——
   E4 阴性对照臂记录之，不进成功判据。
2. `move_tol(0.12) ≥ 单体素半对角(≈0.118)`：单格内位移门几乎不可达。事件主要靠
   "新占用/跨格"；"走回头路"旧格不重亮但仍以 GHOST 身份在候选集内；慢走重触发靠 EMA
   滞后效应，未在本轮标定。
3. ref 支撑格与"坐上椅面的人"融合后冷却归 COLD_BG（人身上方非 ref 体素仍是 GHOST + 锚点层兜底）。
4. 设备静止前提：板被搬动 = 图作废重建（板端接驳前置条件 = `sensor_quality.static_background_usable`）。
5. 跨日 ref 错配（221808↔10-13 会话 +69% 残余是已证事实）由"永不硬删 + ever_event"消化，
   只影响配色不影响留存；P-set 未标身份，可含边缘家具体素（报告同披露口径）。

## 参数表（默认；标定组见 run_grid.sh）

| 参数 | 默认 | 依据 |
|---|---|---|
| voxel_xy/z、z 带、ref 半径/occ | 0.15/0.12、[0.10,2.50]、0.12/0.5 | 沿用 PIPE 常量互操作 |
| ev_hit_min_pts | 2 | 空场噪声摊薄≪1 点/格/帧；对照 3 |
| move_tol_m | 0.12 | ≥2×bg_jitter_max+体素量化（见诚实边界 2） |
| ev_confirm_frames | 2 | sparkle 单帧主闸；对照 3 |
| τ(s)/decay | 8/exp | 静 15.4s→黑界；对照 4/16/linear |
| hot_f_min | 0.15 | ≈2τ |
| slow_alpha / warmup | 0.02 / 40 | ≈50 帧 EMA / ≈4s |
| retention 四项 | 3/180/30/0.4 | 照搬 engine.js，不改 |

## 运行

```
node fresh_lib.test.js                       # M0 单测（file-per-suite，禁 glob）
bash run_grid.sh                             # M1 全网格 → docs/sidequests/evidence/2026-10-15_fresh_map_r1/grid/
node collect.js <grid目录>                    # 汇总表
# 单跑：
node run_fresh.js --session ../../../captures/remote/cap_20261013_082623 \
  --ref-session ../../../captures/remote/cap_20261014_221808 \
  --outdir <新目录> --pset-window 20:140 --compare-base-a
```

每跑产出 `<sid>__<tag>.csv`（逐帧 n_fired/n_hot/n_ghost/obs_pset/kept_fresh/kept_baseA）、
`<sid>__<tag>.json`（summary+metrics+caveats）、`__survival_curve.csv`、`manifest.json`
（源码/输入 SHA 冻结，拒覆盖/拒运行期篡改纪律照 human_core/runner.js）。

## 判据（预注册，跑前写死）

- S1 静立存活：E1 各段 fresh 候选留存（P-set 被观测体素中仍为 HOT/GHOST/live 锚点近）≥95%。
  BASE_A 对照列如实记录（本地素材静置段偏短，报告"≤~5%"复现口径需板侧长静立 S8 素材，另单）。
- S2 复活延迟：E3 `revive_latency_frames` 中位 ≤3 帧（ev_confirm=2 原理下界 2；口径
  region50 或 first_fire 兜底，标注 mode）。
- S3 空场安静：E2 `fired_per_min`/假 live 锚点率低，且存在一组参数同时过 S1–S3。
- S4 实时预算：`mean_ms_fresh_update` ≤5ms（node/PC 口径；全链测量开销另报 mean_ms_full_tick，
  其中含 BASE_A 对照与聚类测量，非实时路径）。
- 失败线：F1 全网格不过 S3；F2 GHOST 簇与家具在几何门统计上不可分（hum_ratio 无差）；
  F3 优化一轮仍 >15ms/帧；F4 "动后才静"30s 内丢失。

## 结果（M1 实测，2026-10-15）

完整判定见 `docs/sidequests/evidence/2026-10-15_fresh_map_r1/00_ACCEPTANCE_V1.md`
（T01~T11），数据 `10_TABLE.csv`/`grid/`，选定参数 `10_SELECT.json`。要点：

- **S1 静立存活 PASS**：E1 六段（动→静）fresh 候选留存 P0 组 0.988~0.998，
  30 跑全量最低 0.979；同分母 BASE_A 硬背景对照尾段仅 0.41~0.77。
  报告"97~98% 吞没"极端口径需板侧长静立 S8 素材，本轮 NOT_RUN（如实记录）。
- **S2 复活 PASS**：E3 first_fire 口径 0~1 帧。
- **S3 空场安静 PASS（选定 evconf3 组）**：干净空场 111738 假发火 0/min、0 锚点；
  噪声空场 221808 假锚点 ~0.08/min（门 ≤2）、几何门假簇率 0。P0 组在 221808 有
  77% humanish 假簇 → F2 现象在案，参数级缓解，本支线不宣称身份裁决。
- **S4 FAIL（边缘）**：fresh_update 均值 2.45~8.01ms（node/PC，49k 点/帧），30/44 ≤5ms；
  未触 F3(>15ms)。升级路径：体素累加表扁平化复用。
- **E4 阴性对照 NOT_OBSERVED**：两段"初始躺地"并非全程静止（窗口内 215/244 HOT），
  warmup 吞人边界未在本地实证——诚实边界声明继续有效，不当作已验证。
- 结论：**方向可行，可晋级 M2（目视/实时页）另单**；S8 复现、221808 噪声归属为遗留项。

## M2（2026-10-15 追加，浏览器目视）

`fresh.html` + `fresh_overlay.js`（挂 replay.js 的 HUMAN_DETECT_OVERLAY 钩子，算法零漂移）。

看效果（推荐）：`python serve_fresh.py` → 开 `http://127.0.0.1:8791/sidequests/fresh_map/r01/fresh.html`
即开即播（默认 空场=221808、主会话=082623，右上「会话」下拉直接换）；file:// 直开亦可，走两个目录按钮。

画面语义（**r4 起 = 证据/对象两层**；因用户目视批评"近距离点本来多、振动明显，别把它们当人"）：

| 视觉 | 含义 |
|---|---|
| **亮白 / 亮青蓝** | 人形对象：候选簇过 `classify_human` 几何门 + 3 帧连续确认 → live 锚点半径内 |
| 淡青（随 f 沉暗） | 未认领的运动证据（近距振动、噪点闪烁只到这层，永不冒充对象） |
| 暗蓝 | 未认领 GHOST 残影（曾动后停，点不删） |
| 近黑 | 长期不动背景 / 带外 |

渲染挂 M1 冻结选组 `ev_confirm=3`（r2 演示页漏挂，r4 补）。
测试：`node fresh_overlay.test.js` **5/5**（含"桌角型簇永不亮白"）；真实会话认领数由 4-5 → 0-1，
见 `docs/sidequests/evidence/2026-10-15_fresh_map_r4/10_REALDATA_CLAIM.txt`（含误认领/卧倒不认领两条局限）。
r2/r3 过程证据：`…_fresh_map_m2_r1/`、`…_fresh_map_r3/`。

## 2026-10-16 低姿身份保持

演示层复用既有站姿确认与FreshMemory，增加低姿的唯一近邻续接。低姿本身不能新建身份；
必须有2秒/20帧内、0.4m内已确认站姿锚点，且无身份/候选竞争；
相对该身份先前确认的站姿峰值，重心和簇高度均须下降至少0.25m。
低姿候选高度0.2–1.2m、顶高≤1.3m、XY半径≤既有track_gate_xy_m(0.75m)，
至少60个非参考图且曾发火的当前点，并占该簇≥50%。这是研究页几何启发式，不是跌倒判决。

低姿显示按当前簇XY柱和非参考图活动体素认领；HOT暖白，冷却后蓝色。
不会扩大原0.4m圆盘来染亮周围背景。缺测/歧义时拒绝续接；reset、切会话或换参考清除身份。
初始便躺地、多人交叉、碎簇/遮挡及与家具合并时仍可能不亮，地面带外点也不会补造。

`node fresh_overlay.test.js`：8项回归，含站立→倒地→静卧40s、无历史低姿、背景及关联拒绝门。
本轮唯一验收：`docs/sidequests/evidence/2026-10-16_fresh_map_low_pose_r1/ACCEPTANCE_V1.md`；
结果和局限见同目录报告。直接拖时间轴会重置状态；复核用`?freeze=200`从0逐帧推进。
