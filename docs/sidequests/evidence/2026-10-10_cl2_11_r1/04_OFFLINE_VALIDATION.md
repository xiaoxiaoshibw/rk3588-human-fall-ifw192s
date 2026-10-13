# CL2-11 / 04 已有数据离线验证 — 2026-10-10

范围：只用**已实际存在、可只读复位**的资料（S02/S03/S04/S05 + CL2-10 冻结 diagnostics）。任何
板端独占的资料（S01 bag 的复解码、S09 PCAP）本轮 **NOT_RUN**，不得代替执行。

## 4.1 数据完整性核验（先于一切分析）

| 核验 | 方法 | 结果 |
|---|---|---|
| bin SHA 与冻结 report 一致 | `report.source.bin_sha256 == '97def5d2…017fc'` | PASS（cl2_11_ring_probe.py 启动时断言） |
| frame72 ROI2 点数 | domain holdout filter (region==2 & ordinal==72) | 300 点，与 CL2-10 报告一致 |
| 复算 signed mean / RMS / P95(abs) | 与 CL2-10 冻结口径一致（同平面、同残差定义） | −0.00079674 m / 0.02741799 m / 0.05029187 m，完全一致 |
| FIT 域 ROI2 点数 | domain region_codes==2 → source_rows | 63959 点 |
| channel_diagnostics 的 ROI2 count | 01_channel_diagnostics.json "2".count | **64850 = FIT 63959 + holdout 891 (300+294+297)**；直查 domain.npz 证实（见 `cl2_11_verify_counts.json`）——原有记述“63959 与 channel diagnostics count 一致”错误，两者口径不同 |
| source_rows 越界 | rows.max() < n_bins | PASS（300 点最大行 < 10,708,741） |

与 CL2-10 冻结输入逐字节一致，没有发生“用不同输入重新得出想要的结构”。

## 4.2 逐点身份与字段对照（STEP3）

- 逐点 x/y/z：从 bin 28B stride @0/4/8 读出 float32→float64，与 CL2-10 原口径一致。
- ring：uint16 @16；frame72 300/300 与 FIT 63959/63959 均 ≠ 0 → **CLAUDE prompt 的“原始通道信息
  实际存在”成立**。
- intensity：float32 @12；相关 −0.310（CL2-10 同源已报；本轮未重算画蛇添足）。
- timestamp：float32 @20，属于设备未锚定时间域；逐帧内为本帧相对微秒偏移，跨帧不连续，
  对 ROI2 结构分析不新增信息（未纳入判别）。

## 4.3 复解码对照的预注册指标（本轮实际执行部分）

预注册（写在执行前，见 00 表 I103）：
1. 按 ring 的 count / signed mean / P95(abs) / tail>50mm — 全部点保留；
2. ring↔display-x 的均值/min/max 映射（用 report.estimators.tls.R[0]）；
3. FIT 域与 frame72 留出域同口径；
4. 若某 ring 无标签（ring==0），单列，不并入统计。

执行产物：
- `docs/sidequests/evidence/2026-10-09_cl2_10_r1/cl2_11_ring_probe.json`（ring/range/XY 概览）
- `docs/sidequests/evidence/2026-10-09_cl2_10_r1/cl2_11_ring_xy_probe.json`（ring↔display-x 混淆量化）
- **边界披露（审计发现 #6）**：上述两个 JSON 是**本轮 CL2-11 产生的诊断**，但按当时工作目录被写入了
  CL2-10 的封号 evidence 目录——与本轮 00 表“只新增自己 evidence 目录，不回填旧记录”冲突，且可以被误
  读为 CL2-10 的官方输出。处置详见 06_INDEPENDENT_REVIEW_NOTES.md §6.3：不在 CL2-10 目录再增删字节
  （避免再改其起止状态），改为 (a) 本目录 07 manifest 跨目录登记两个文件 SHA；(b) FINAL_REPORT 披露关系；
  (c) 任何对 CL2-10 的复核以其 `05_evidence_manifest.json` 为准（这两个文件不在其中，不影响封号完整性）。
- 本目录本地验证产物：`cl2_11_verify_counts.json`（holdout ROI2=891=300+294+297 与 FIT 63959 的精确核对）

主要结果（02 §3 已按审计修正）：
- signed‑mean 平均步进 ≈**0.0071 m/ring**（0.013 m/ring 是 display‑x 步进，原稿混标，已更正）；
- 相邻 ring 的 display‑x 正规化重叠中位 ≈**64%**（原稿“30–50%”低估，已更正）；
- range 仅 1.5–1.75 m 窗口，无法支持“随距离”判据；
- frame72 300/300 与 FIT 63959/63959 无 ring==0 记录；
- **y 内结构（审计补充）**：frame72 每 ring 的 display‑y 跨 ≈0.24 m ≈ 6× x 跨；固定 ring 内 resid‑on‑y
  线性斜率在 −0.10..+0.10 且符号跨环不规则——排除了“每环常量偏差”这个最简单的 B 子型，但相容于
  “g 有 y 依赖”或“b 有 y 结构且与 ring 非对齐”，未用于重建 g/b（数据含在 `cl2_11_verify.py` 输出，
  该脚本参数/计算口径已在 03 与 04 双预注册）。

## 4.4 缺失 / 重复 / 时间错配 / 转换误差清单

- 缺失：S01 bag（板端）、S07 现场照片/标记、S09 PCAP、厂商综合数据包协议、通道标定表。
- 重复：S02 在 cl208audit 与 ldiar/captures/remote 两份镜像，SHA 已在历史会话按 manifest 等价核验，本轮取证用 cl208audit 镜像。
- 时间错配：meta time_domain=device_stamp_s_unanchored（设备微秒域未锚定系统钟）；bag_time_sec（1791519408.326=2026-10-09T12:16:48.326+08）是相对时钟且 seq 连续、offset 连续、无丢点记录（meta 每帧 dropped_frames/points=0）→ 未检出时间错配。
- 转换误差：残差刚体坐标不变性 ≤8.9e-16 m，机器精度内无变换误差；display-x 投影使用 report R[0]（与 CL2-10 坐标定义一致）。

## 4.5 未执行项与原因（诚实标记）

- bag 独立复解码：**NOT_RUN（BLOCKED）**。S01 在板端 /mnt/captures，本轮未授权设备连接，
  本地无副本。STEP3 的“提取链验证”此子项留作 STEP4 计划的一部分。
- PCAP/SDK 重放：**NOT_RUN**。S09 MISSING。
- IMU 逐条取证：**NOT_RUN**。HF 项目规则 IMU 仅健康监测；且 IMU 与 ROI2 几何无因果通道。
- 任何 TLS/局部平面/权重/门控修改：**NOT_RUN**。本轮禁改。

## 4.6 结论

现有离线数据**足以**确认：残差场沿 x 稳定、ring↔x 混淆量化、没有任何提取链硬错误（坐标不变性/映射连续/点数一致）。
现有离线数据**不足以**区分 A/B/C：所有差异在数学上与欠定观测方程相容（02 §6）。
按预注册指标完成的全部验证都是描述性，未生成任何 TLS 候选、未导出任何“有效 TLS”。
