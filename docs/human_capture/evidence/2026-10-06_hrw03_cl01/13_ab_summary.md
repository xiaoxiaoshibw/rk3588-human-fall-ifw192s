# 13 · CL-01 第二阶段：Connectivity Shadow AB 总结（A/B/C/D）

- 日期：2026-10-06；writer：OpenCode（DeepSeek v4.1 Flash）；ponytail 已加载（full）。
- 性质：离线 shadow AB，**production 零改动**（未采集/未部署/未 commit）；见 §1 SHA 事件。
- 输入：`cap_20261002_223757`（leveled，points sha `8afb660b…`）+ R3.1 reference `cap_20261004_203349`（仅用于 detail 帧的 ref proxy 统计）。
- 复现：`node 09_ab_shadow_impl.js`（自检）→ `node 10_ab_synthetic_results.js` → `node 11_ab_real_frame_results.js` → `node 12_ab_debug_gen.js` → 本文件。

## 0. 一句话结论

**XY-only 4 邻并不是对象级 HUMAN+STATIC merge 的主要放大因素**：把 connectivity 放宽（XY8）会显著恶化 merge（+69.5k 点），
收紧（XYZ26 / constrained-3D）也无法拆开 f55/f155/f160 的关键 merge（人体与静态结构物理贴邻且 Z 重叠）；
唯一真实、可复现的 connectivity 收益是 **z 互不重叠的 VERTICAL_ALIAS**（XYZ26 修复 4039 点；constrained-3D 修复 668 点），
量级远小于 background residual / 前景几何本身的贡献。constrainted-3D（D*=G0.30）在保住干净人体的同时带来部分碎片代价，
但在代表性帧上没有达到“merge 明显下降”的预期。**最终标签：`NO_CHANGE`**（以 §1 SHA 裁定为前提）。

## 1. 收尾 SHA 复核 = **RAW FAIL / CONTENT PASS（外部 EOL 批量改写事件）**

| 项 | 值 |
|---|---|
| raw sha256（当前字节） | `f580778c366767529d74d17af8ff2ecba4a22728dcd9fc06743e74d510a4dc83` → **FAIL**（≠ `5bce92a4…142b4`） |
| normalized（CRLF→LF 后） | `5bce92a433e58d537c05bfd36f516077f94e80bf351a94aae8efad46b04142b4` → **与第一阶段一致** |
| 机制 | 810 行全部 LF→CRLF（+1 byte/行 = +810 bytes）；逐行内容与第一阶段读取完全一致 |
| 时间/范围 | mtime `2026-10-06T21:15:11`；`pc_apps/human_replay/` 下 **11 个文件同一秒被外部批量改写**（human_detect.*、replay.js、leveling.*、index.html、human_replay_lib.py、human_pipe_lib.test.js 等）；**非本会话所为** |
| AB 计算所用内容 | `11_ab_real_frame_results.json` 在 run 时记录 `inputs.human_pipe_lib = 5bce92a4…`（即 phase-1 LF 内容）；改写发生在 run 之后 |

取证：`13_sha_recheck.log`（本目录，含命令与清单）。**本会话未回改 EOL，也未修改任何 production 文件。**
按工单字面规则“未通过 SHA 复核则本轮实验无效”——本轮的**数据结论**基于 5bce92a4 内容（已证明与当前内容语义等价），
但 raw 门状态需用户裁定（接受 EOL 归一 = 有效；要求字节级 = 无效，需外部改写方负责）。

## 2. 自检（全部 PASS）

1. **A 完整复刻**：165 帧 raw 均值 47.69 / filtered 均值 21.9 / `<3 voxel` 碎片 **4255**，与第一阶段 06 JSON 逐位一致。
2. **A ↔ production 等价**：逐帧（165/165）shadow A 的 raw+filtered 分区与 `PL.cluster_voxels(PL.voxelize(pts))` 多重集合一致（0 失配）。
3. **Synthetic A–H**（10_ab_synthetic_results）：10/10 与预期一致（Case A C=2；Case C A/B=1、C/D=2；Case D D-G0 断桥=3、G≥0.15 保桥；Case G B=C=1、A=D=2；E/F/H 符合约定）。
4. Smoke：HTML 打开即渲染、点击选中、A 分区对照正常（browser console 零错误）。

## 3. Variant（唯一变量 = connectivity）

- **A**：XY 0.15 柱 + 4 邻（production 复刻，min_voxels=3）。
- **B**：XY 0.15 柱 + 8 邻（负向对照）。
- **C**：XYZ **0.15³** cell + 26 邻（shadow 自有 key，非 key_bg）。
- **D-G{0,0.15,0.30,0.45}**：XY 柱 + 4 邻 + 垂直兼容门（列内 Z occupancy bin 的 `minGap ≤ G`）。

## 4. 全 165 帧聚合（差分 = X vs A，raw 分区）

| variant | raw/帧 | filt/帧 | `<3 voxel` | 丢点 | split 事件(点) | z-分离 split | merge 事件(点) | cluster ms mean/p95 | total p95 |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| A | 47.69 | 21.9 | **4255** | 11702 | 0 | 0 | 0 | 0.86 / 1.35 | 27.8 |
| B | 26.76 | 15.08 | 1926 | 7385 | 0 | 0 | **353 (69481)** | 1.04 / 1.69 | 28.0 |
| C | 61.27 | 39.51 | 3591 | 8058 | 555 (120869) | 134 (4039) | 300 (22491) | 5.35 / 7.94 | 34.4 |
| D-G0.00 | 147.93 | 37.49 | 18223 | 39427 | 813 (170039) | 74 (2087) | 0 | 1.39 / 2.27 | 28.4 |
| D-G0.15 | 81.30 | 30.04 | 8457 | 19861 | 611 (135139) | 36 (1043) | 0 | 1.35 / 2.13 | 28.4 |
| **D-G0.30（D\*）** | 63.01 | 26.48 | 6028 | 15186 | 422 (78413) | 21 (668) | 0 | 1.32 / 2.12 | 28.3 |
| D-G0.45 | 54.37 | 24.60 | 4912 | 13003 | 283 (68712) | 11 (369) | 0 | 1.33 / 2.18 | 28.6 |

- **B 只有 merge、没有 split**：8 邻把 A 的相邻/对角/碎片全部并进更大簇（如 f63 clean 人体簇 2874 → 3549，多吞 650 点静态残留）。
- **C 双向失控**：既拆（120.9k 点，其中仅 4.0k 是 z-分离）又并（26 邻对角/纵向新增 22.5k 点合并）；detail 帧总簇数 827 vs A 446。
- **D 系列只有 split（边集是 A 的子集）**：G 越小越激进；代价是 `<3 voxel` 碎片与丢点成倍增长。D\* 选择：G0.30（clean 最小 retention 0.998、碎片 1.42×、丢点 1.30×、p95 1.58× 均过 invariant 门；z-分离收益 668 点 > G0.45 的 369 点）。

## 5. 重点帧（person component：人工代理 = 已知位置圆柱，proxy ≠ GT）

| 帧 | A person 簇 | B | C | D\* | 结论 |
|---|---:|---:|---:|---:|---|
| f55 merged | 3190 | 3216 | 3165 | **3166** | merge 未拆（ref 0.19 不变） |
| f150 merged | 4203 | 4250 | 3570 | **3570** | **部分改善**：拆出 632 点低层结构块（bbox≈[1.53,2.46]×[0.77,1.59]×z≤1.34），person 簇 y 上限 1.59→0.73、点数 −15% |
| f155 merged | 3558 | 3562 | 3548 | **3520** | merge 未拆（−38 点） |
| f160 merged | 2429 | 2431 | 2426 | **2423** | merge 未拆（−6 点） |
| f63 clean walk | 2874 | **3549（+675）** | **3524（+650）** | 2874 | B/C 过并；D 安全 |
| f80 clean stand | 2499 | 2499 | 2498 | 2494 | retention ≥0.998（D\*） |
| f10/f30 static-residual | 1564/1487 | — | 切碎 | 切碎（416/1034 点） | 身份仍为静态残留；但 **D\* 切块后 f2/f10 的残留块反而通过全门+HUMAN_SHAPE**（静态误确认 detail 帧计数 A=1 → C=2 → D\*=3） |

Retention（D\*，clean 帧）：最低 0.998；merged 帧 = 1（人体主体未被拆）。Contact 佐证（f55/f150/f155/f160）：
A 的人/非人跨边 80/59/89/100 条、cut 后仍连通（宽接触）——这就是“收紧连通性拆不开关键 merge”的机制证据。

## 6. 下游仅观察（未修改 evidence/classifier；POST_FILTER_ERROR 仍属另一问题）

detail 帧合计（21 帧）：A: 446 簇 / HUMAN_CANDIDATE 64 / CONFIRMED 22 / SOLID_UNIFORM 79；
B: 321/27/9/67（过度合并致候选与确认减少）；C: 827/72/23/73；D\*: 539/68/25/73。
静态残留（ref>0.5、uppers<5）被 CONFIRMED 的簇数：A=1、B=0、C=2、D\*=3 —— **D\* 未降低该风险，反而略增**。

## 7. 最终回答（工单 §9 七问）

1. **XY4 是 merge 放大因素吗？** —— 不是主要因素。放宽（B）放大 merge、收紧（D）不改善关键 merge；merge 量级由前景几何（残留+贴邻）决定。XY4 是 z-分离别名合并的唯一来源，但本数据集量级小（≤4.0k 点/165 帧）。
2. **XY8 恶化吗？** —— 是，最差：+353 事件/+69481 点 merge、零 split，连干净行走人体都开始吸收静态残留。
3. **XYZ26 降低 vertical alias 吗？** —— 是（134 事件/4039 点，占其 split 点 3.3%），但作为整体方案不成立。
4. **XYZ26 新 over-split / over-connect？** —— 两者都出现：116k 点 z-重叠拆解（表面/结构碎片化，detail 簇数 827 vs 446）、+300 事件/22491 点新合并（对角/纵向）。
5. **constrained-3D 优于 A/C 吗？** —— 部分：无新 merge（优于 C）、f150 分离 632 点、人体保留 ≥0.998；但 f55/f155/f160 无效、碎片 +42%、丢点 +30%、静态误确认 1→3、p95 1.58×。**不构成净收益**。
6. **改善来自 connectivity 还是 residual？** —— 可测的改善都来自 connectivity（f150 块分离、z-分离别名），但主导失败（对象级 merge、碎片、静态残留）仍由 background residual 与前景几何支配；因此不能把本轮问题归于 clustering connectivity。
7. **是否进入 production change proposal？** —— **否**。标签：**`NO_CHANGE`**。
   （附加条件：§1 的 SHA raw 门需用户裁定；若裁定字节级 FAIL 则本轮实验无效，需在先决条件满足后重跑。）

## 8. 边界 / 未做 / 已知限制

- f55/f155/f160 的“物理贴邻 + Z 重叠”merge 不属于任何 connectivity 规则的解决面（除非引入背景/radial 语义，已超出本轮变量范围）。
- D 的列内不做纵向拆分（同柱堆叠由 C 语义处理）；D 参数 sweep 仅 {0,0.15,0.30,0.45} m。
- detail 帧 proxy（圆柱/ref）≠ 逐点 GT；远场 ref 匹配受跨会话 registration 残差影响（no-ICP 口径）。
- 10_ab log 文本中 `filt=` 显示 `undefined` 为打印字段名笔误（JSON 字段 `filtered` 正确）。
- 运行时间在 Windows Node v24.14 上测得，仅用于 variant 相对比较（非板端口径）。
- 未采集、未部署、未 commit、未修改 production；B/C/D 与 debug HTML 均为离线脚本产物。
