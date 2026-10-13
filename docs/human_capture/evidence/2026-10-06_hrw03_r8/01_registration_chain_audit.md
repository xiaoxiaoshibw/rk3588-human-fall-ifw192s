# 01 · W03-R3.6 Registration 链只读审计（以当前磁盘代码与 evidence 为准）

- 日期：2026-10-06；writer：OpenCode（DeepSeek v4.1 Flash）；ponytail full。
- 性质：只读审计；本文件不修改任何 production 文件。所有结论以 **当前磁盘真实代码行** + r4/r5/r6/r7 evidence + 本轮实测 SHA 为准；文档/README 仅作对照。
- 口径：console leveled pipeline（`W03_R3_ACCEPTANCE.md` §0）。"实际生产链" = 浏览器 console `human_detect.js` 载入会话后跑的 background matching；tool 端全部为 shadow 验证。

## 0. 结论摘要（TL;DR）

1. **production 的 registration = 每会话独立 ground leveling**（TLS，离线 `offline_display_only`）。**没有任何跨会话 transform 进入 production**；reference 静态图（R3.1）未接线。`build_static_map` / `extract_foreground` / `_bg_match` 只消费 current 会话自己 leveling 后的坐标系。
2. 因此"跨会话 registration"只存在于 **shadow 实验**（R3.2/R3.3/R3.5）：`R_direct = R_cur · R_refᵀ`（tls-direct，无平移）与固定的 R3.2 ICP 解（有平移）；R3.6 条件 A=生产现状（无跨会话对齐，none）、B=该固定 ICP、C=高置信静态结构 point-to-plane（本轮新建）。
3. 坐标链：`p_leveled = R_tls · p_innolidar + t_tls`（每会话各自 R_tls；行主序 3×3；列向量右乘；米）。r7 工具的三种 probe 把 **current 点映射到 reference 帧**（current→reference 方向）。
4. 重复 transform / leveling 后重复旋转：**不存在**（见 Q13/Q14 逐项验证）。
5. 文档 vs 代码：r6 审计引用的行为与代码逐行相符；仅记录一处 shadow 工具选择规则的细差（Q6 备注）。

---

## 1. 逐问回答（工单 §四 15 条）

### Q1. current 点云进入 background matching 前的坐标变换完整路径

```
captures/remote/<sid>/points.bin (stride 28B: x,y,z float32 + 4 通道)
  → human_detect.js: RL.frame_slice(meta)                       [帧表 start_pts/count]
  → 载入时一次性 in-place：GET /api/leveling/leveled_latest?sid → apply_Rt(R,t) 全 buffer
        human_detect.js L91–101 (apply_Rt) / L117–127 (fetch+apply)
        replay.js       L204–215 / L230–239（同款，回放页）
  → build_static_background(): 每帧 strided 拷贝 + PL.denoise() → PL.build_static_map(drop_ground:true)
        human_detect.js L219–242
  ── 之后每帧 ──
  → _run_pipe_frame(): PL.pipeline_frame(slice)                  [human_detect.js L306–311]
      → denoise()（有限 + 0.35–25 m 距离窗）                      [human_pipe_lib.js L107–116]
      → extract_foreground(): z∈[0.10,2.50] + _bg_match()        [L277–289 / L292–303]
      → RESIDUAL = fg_xyzi
```

- 变换只发生在 `apply_Rt` 一步；distance window 里的 0.35 m 是**配平系原点**距离（r7 `01_baseline_equivalence.md` §2 已验证本会话 0 点被该窗剔除）。
- evidence：r7 工具以同款链路（先 apply TLS，再 denoise）复刻，165/165 帧与 production `extract_foreground` 逐点等价（r7 `01` §1）。

### Q2. leveling transform 是什么、从哪来

- 来源：`pc_apps/human_replay/leveling.py`（离线 workbench job）。server 路由 `/api/leveling/leveled_latest`（L376–425）扫描 `<sessions_root>/../leveled/<job>/`，要求 `report.json`：`sid` 匹配、`recommended=="tls"`（L397）、源 SHA 绑定匹配（L408）、report/transform 的 SHA 与 manifest 一致（L412–419）；取 `report.json` mtime 最新者，返回 `tls/transform.json`。
- sessions root = `captures/remote`（`config.py` L13 `DEST_ROOT`），故 `outroot = captures/leveled`（`leveling.py` L355）。
- transform 内容（本轮实测）：
  - current `6bc5aabf…`：pitch 26.4669°、roll −0.3661°、tz 1.32319 m；
  - reference `c9712aca…`：pitch 26.9935°、roll −2.9478°、tz 1.31711 m；
  - 字段：`kind=offline_ground_leveling_transform, schema=1, units=m, from_frame=innolidar, to_frame=ground_offline_display, scope=offline_display_only, physical_verified=false, extrinsics_verified=false, runtime_eligible=false`（`leveling.py` L195–203）。
- 语义：把该会话拟合出的地面法向转正（floor → z=0），**只保证"各自水平"，不保证两会话同一世界系**（r6 §1.1 同结论，代码验证一致）。

### Q3. session-to-session transform 在哪里/做什么

- **production：不存在。** reference（R3.1 静态图）无接线；会话间无任何 transform 传递。
- shadow（仅 R3.2–R3.6 实验）：`R_direct = R_cur · R_refᵀ`（r7 工具 L580–584）把 **reference leveled 帧**的向量映射到 **current leveled 帧**；"tls" probe 用其转置把 current 点送进 reference 帧，**无平移**。
- 固定 ICP 解（R3.2 存值）：`roll 1.7476° / pitch −0.2818° / yaw −2.3924° / t [0.0182, 0.031, 0.0012] m`，方向 = reference→current（详见 Q5/Q12）。

### Q4. reference 坐标系是什么

- reference map = `PL.build_reference_map(REF.frames)`，输入是 reference 会话**自己** apply 了 `c9712aca…` TLS、再 denoise 的帧（r7 工具 L196–210 同款加载）。因此 reference map 位于 **reference 会话的 leveled 坐标系**（名义 `ground_offline_display`，floor z=0）。
- R3.1 builder 本身不做 leveling（`human_pipe_lib.js` L217–261 只做体素/占用统计）；坐标系完全由喂入帧决定。voxel 尺寸 XY 0.15 / Z 0.12，`hit_min=1`、`occ_min=0.5`（v1 候选，未标定）。

### Q5. ICP 在哪里计算

- **只在 shadow**，共 3 处同源实现（同一算法逐行复制）：
  1. `r4/06_r32_audit.js`（R3.2 起源，48 iters 收敛，RMSE 0.1102）；
  2. `r5/11_r33_ab.js`（R3.3 复跑，CHECK 一致）；
  3. `r7/10_r35_attribution.js` L524–577（R3.5 复跑，CHECK 逐位一致）。
- 算法：source = reference map `occ≥0.9` 体素形心（2956）；target = current `build_static_map` strong 体素形心（1480）；最近邻哈希格 0.28 m、一致门 0.25 m；Jacobi 伪逆小角解闭环 50 次迭代（`solveSmallAngle` L117–142）；**无裁剪**；收敛到固定局部解（r4 登记 `roll↔yaw 简并 / weakly observable`）。
- 本轮 recon 已再次复跑并逐位复现存值（`_recon_c_probe.log`）。

### Q6. ICP 是否真正进入 production

- **没有。** `human_pipe_lib.js`/`human_detect.*` 无 ICP 引用（全仓 grep：ICP 只出现在 evidence/shadow 脚本）。`/api/leveling/*` 是 TLS workbench，不含 ICP。生产接入未授权（CL-01/r3–r7 口径一致）。
- 备注（shadow 工具与 server 的细差，非 production 问题）：r7 的 `resolve_transform` 用 **job 目录 mtime** 选最新且不做 SHA/地面身份校验；server 用 **report.json mtime** + 全套校验（`leveling.py` L376–421）。本数据两个 job 唯一，选择结果一致（transform_id 与 r7 记录一致，见 `00_provenance.md` §3）。R3.6 工具沿用 r7 选择规则并加校验（selection 结果不变）。

### Q7. transform composition 顺序

- 每会话：`p_lvl_s = R_s · p_inno + t_s`（先 R 后 +t；s = cur/ref）。
- 跨会话 tls-direct：`p_cur = R_direct · p_ref`，其中 `R_direct = R_cur · R_refᵀ`（列向量、右乘；代码 `m3.mul` 见 Q8）。推导：`p_cur = R_cur p_inno + t ≈ R_cur (R_refᵀ (p_ref − t_ref)) + t_cur`；因两会话 t 只有 z 分量且地面已配平，shadow 只取旋转部分（tls 无平移）。
- ICP：`p_cur = R_icp · p_ref + t_icp`；反向 `p_ref = R_icpᵀ (p_cur − t_icp)`（r7 `alignPoint("icp")` L585–588 即此式）。

### Q8. row-major / column-major

- `transform.json` 的 `R` = 3×3 嵌套数组（**行主序**，每行一子数组）；`apply_Rt` 直接 `R.flat()` 后按 `r[0..8]` 行主序取值（`human_detect.js` L92–101）。数学上 `p' = R p`（R 的行点乘 p）。
- shadow `m3.mul(A,B)` = 标准行主序矩阵乘 `A·B`（r7 L83）；`m3.t` = 转置（L84）；`m3.apply(A,p) = A p`（L85）。

### Q9. 左乘 / 右乘

- 列向量约定：`p' = R p + t`（右乘向量）。组合时新变换 **左乘** 已有：ICP 里 `R ← Rn · R`、`t ← Rn t + tNew`（r7 L556–558），即 `p' = Rn (R p + t) + tNew`。

### Q10. 单位

- 平移/坐标 = 米（`units:"m"`；tz 1.32 m = 地板在传感器系的高度）。
- 旋转矩阵无量纲；**角度字段是度**（pitch/roll_deg、ICP 存值、euler 报告均为度）。
- 点云 = float32 米；匹配半径 0.12 m；体素 0.15/0.12 m。

### Q11. yaw / pitch / roll 定义

- **leveling 参数（transform.json 的 pitch_deg/roll_deg）**：地面法向 n（传感器系）→ 拟合；`pitch = atan2(−n_x, n_z)`、`roll = asin(n_y)`；`R = Rx(roll) · Ry(pitch)`（`leveling_quality.py` L21–24 / L64–66；`compare()` L67 断言 `R[2]==n`）。这是"把地面对正到水平"的 2 参数参数化，**不是**一般姿态的欧拉角。
- **shadow ICP/比较用的 euler（r7 `eulerFromR` L564–569）**：ZYX 提取 `yaw = atan2(R[3],R[0])`、`pitch = asin(−R[6])`、`roll = atan2(R[7],R[8])`。
- 两者语义不同（前者描述地板法向对齐，后者描述任意相对旋转）；跨口径比较必须先转矩阵。r7 的 `tls-direct` 报告（roll −2.582° 等）用的是后者；R3.2 的 `R_cur·R_refᵀ → roll +2.582°` 亦是后者（方向相反）。

### Q12. current → reference 还是 reference → current

- `transform.json`：`from_frame=innolidar, to_frame=ground_offline_display` → **传感器→各自 leveled**。
- r7 probe：`alignPoint(mode)` 把 **current 点** 送进 **reference map 所在帧**（current→reference）：
  - `none`：原样（各自 leveled，未对齐）；
  - `tls`：`p_ref = R_directᵀ p_cur`；
  - `icp`：`p_ref = R_icpᵀ (p_cur − t_icp)`。
  （r7 L585–590；本审计用矩阵验算逐项核对过。）
- ICP 拟合方向为 reference→current（source=ref，target=cur），存值也是该方向。

### Q13. 是否存在重复 transform

- **production 不存在**：TLS 只在载入时对全 buffer 应用一次；`pipeline_frame`/`build_static_map` 不再次应用任何 transform；回放页与检测页各自独立载入、各自应用一次。
- 可能的来源已排查：`captures/leveled/<job>/{tls,svd,ransac}/points.bin` 是**已变换的派生数据**，但不位于 `captures/remote` 会话根下，不会被会话列表/载入链消费（`leveling.py source()` 也只接受原始 `innolidar` 会话）。
- shadow 工具（r7/R3.6）与 production 同口径：每会话恰好一次。

### Q14. 是否存在 leveling 后又重复旋转

- **不存在。** 载入链只有 `apply_Rt` 一处旋转（Q1）；`build_geometry/paint_colours` 只读变换后 buffer；`compute_range`、snap、bbox 皆消费同一 buffer。无"配平后再按 pitch/roll 转回来"或二次旋转路径。
- 注意区别：`transform.json.pitch_deg≈26.5°` 是安装俯仰，不是用于"再旋转"的增量；仅有 `R` 被应用且仅一次。

### Q15. reference builder 姿态 vs current runtime 姿态语义一致性

- current runtime：current 帧先 apply **current 自己** 的 TLS，再 `build_static_map` → online map。
- reference builder：reference 帧先 apply **reference 自己** 的 TLS，再 `build_reference_map`。
- 两者**语义一致**（同一种"各自会议话 TLS → 再建图"的口径），但**坐标系不同**（两会话的物理姿态差 ≈ R_direct，r4 实测 roll 2.582°）；这正是 R3.6 要处理的跨会话 registration 缺口。
- 在 **同会话** 内（如 reference 自吸收 0.9987 的既有实验）同坐标系，不存在该问题。

---

## 2. 文档 vs 代码对照（发现的冲突/差异）

| # | 文档说法 | 代码事实 | 处置 |
|---|---|---|---|
| 1 | r6 §1.1 引 `human_detect.js L117–127` 应用 `recommended=="tls"` transform | 逐行一致（L117 fetch / L120–124 apply / L397 `leveling.py` 过滤） | 无冲突 |
| 2 | r6 §60 引 `leveling.py L200–203` scope 与 eligibility | 实测 transform 字段一致（`offline_display_only` 等） | 无冲突 |
| 3 | R3.2 §9 称 "TLS-direct（roll 2.58°…）" | 方向为 ref→cur（`R_direct = R_cur R_refᵀ`）；r7 tls probe 用其逆 | 文档无误，但方向必须在 R3.6 都写明（本文件 Q7/Q12） |
| 4 | r7 工具 `resolve_transform`（job 目录 mtime）vs server（report mtime + SHA/floor 校验） | 选择规则细节不同；本数据结果相同 | 仅登记（shadow 工具差异，不影响结论；R3.6 工具加校验） |
| 5 | README/文档从未声明 ICP 在 production | 代码 grep 证实 shadow-only | 无冲突 |

## 3. 对 R3.6 实验的直接影响（据此定型 A/B/C）

- 由于 production 无跨会话 registration，**A（production/current）在"reference 融合"假设下 = 不做跨会话对齐（none）**；证据口径与 R3.5 的 `none` 完全一致（R3.5 的 `Registration` bucket 定义为 `icp 命中且 none 未命中`，天然以 none 为现状基线）。
- B = R3.2/R3.5 固定 ICP 解（严格复用，不重调参）。
- C = 本轮新建的高置信静态结构变换（point-to-plane，只使用两会话高置信静态结构；独立于 residual 指标；构造与验证见 `02_experiment_design.md` §4）。
- 所有条件的方向统一为 **current→reference**（与 r7 probe 一致），保证吸收口径可比。

## 4. 本轮为审计配套的实测（可复算）

```bash
# SHA/选 job（本文件 §1/§3 数值）: 见 00_provenance.md 的采集命令
node docs/human_capture/evidence/2026-10-06_hrw03_r8/_recon_c_probe.js   # ICP-B 复跑 + 结构 reconnaissance
node docs/human_capture/evidence/2026-10-06_hrw03_r8/_recon_c2_probe.js  # point-to-plane C 选型（见 02 §4）
```

- `_recon_c_probe.log`：ICP-B 复现存值（`roll 1.7476 / pitch −0.2818 / yaw −2.3924 / t [0.0182,0.031,0.0012]`）；converted cur→ref；静态结构 XY 粗视图（远墙 x≈11.5–12、左侧结构 x≈0–2 等）。
- `_recon_c2_probe.log`：point-to-plane 从 3 个初值收敛；identity 与 B 初值落到同解、even-half 拟合稳定；normal-residual p50：none 38.8 mm → tls 29.9 mm → B 14.5 mm → C 11.0 mm。

**Production modified? NO（本轮审计阶段）。**
