# P02 R3 分区/逐帧地面建模 · 作者自验报告（SUBMITTED）

2026-10-04。范围：只写本目录新文件 + `P02_ACCEPTANCE.md` 追加 R3 条目 + `returns/P02.md` 末尾追加。**不修改**任何生产代码、runtime、driver、webui、annotator.html、采集配置或 R2 既有证据；不设备/采集/部署/网络/commit/push/reset。R3 不升级 `physical_verified/extrinsics_verified/runtime_eligible`（全部 false），1.14m 实测继续另存不绑定。

ponytail 实际读取：`C:\Users\30680\.claude\skills\ponytail\SKILL.md`（见 00_BASELINE.md）。

## 冻结数据域（写前实测核验）

复用 R2 `2026-10-04_p02_four_roi_r1/02_FROZEN_POINTS.npz`：392196 点（#1=151861、#2=90803、#3=101948、#4=47584），A=91/C=102 帧，772 个 (session,frame,region) 单元。annotator.html / R2-r2 纯函数 / 两 session bin/meta SHA 与 R2 声明全部一致（00_BASELINE.md）。**先冻结、后估计；不裁尾、不改 ROI、不降门**。R3 只在类型 C 主路径下，按提示词「如类型C」一样交付模型 II —— 但注意：类型 B 主路径要求的模型 I 也交了（提示词§3.2 明说"类型A 时也交，作为对照"），所以 R3 实际 3.1a/B/C 全做 + 模型 I & II 双交。

## 必做分析结果

### 3.1 分区诊断（门控）

**每 ROI 独立平面**（向上对齐名义 Ry26）：四区自身全点残差全部 PASS 数据门：

| ROI | pitch | roll | d (m) | RMS (m) | P95 (m) |
|---|---:|---:|---:|---:|---:|
| #1 | 28.4853° | 3.5151° | 1.42419 | 0.0150 | 0.0297 |
| #2 | 26.3491° | −0.7492° | 1.30666 | 0.0086 | 0.0164 |
| #3 | 27.9016° | −5.8628° | 1.33978 | 0.0131 | 0.0252 |
| #4 | 23.9123° | −1.9458° | 1.19136 | 0.0154 | 0.0273 |

注意 #3 的 27.9016°/−5.8628°/1.33978 与 R2 的局部单区旧模型一致 —— R2 把它"拉正"到联合平面，R3 独立拟合确认这是 ROI 局部真实斜率。

**3.1a 成对一致性矩阵（6 对，全点互预测）全部 FAIL**：

| 对 | 法线夹角 | d 差 (m) | 最劣互预测 P95 (m) |
|---|---:|---:|---:|
| 1↔2 | 4.7690° | 0.11753 | 0.0584 |
| 1↔3 | **9.3960°** | 0.08440 | **0.1009** |
| 1↔4 | 7.1214° | **0.23283** | 0.1130 |
| 2↔3 | 5.3431° | 0.03312 | 0.0690 |
| 2↔4 | 2.7141° | 0.11530 | 0.0514 |
| 3↔4 | 5.5837° | 0.14842 | 0.0878 |

max 夹角 9.40°、max d 差 0.233m，远超参考门（0.5°/5mm）→ 类型 A 一票否决。这定量闭合 R2 留一区 FAIL 的根因：四块地不在同一刚体平面上。

**3.1b 分区×session 8 平面**：A#k 与 C#k 参数几乎重合（如 A1 28.4876°/3.5103°/1.42416 vs C1 28.4833°/3.5194°/1.42421，d 差 ~5e-5 m、角差 <0.008°）→ 分区平面在两 session 间稳定。

**3.1c 残差分解**：帧内结构项 share ~0.001–0.008，真噪声 share ~0.99；A/C 与 region 的慢变项 relative energy = **2.0e-05**（≈0.002%）。**跨区不可预测几乎全部来自「分区平面几何不一致」，不是帧级漂移或 session 间慢变**。注意：i+iii≠100%（median 非能量正交投影，逐帧 ±1~2cm 尺度跳变×大点数），该形态如实保留，未强行正交归一。

**类型判定 = C**（量化依据如实记录）：max 成对夹角 9.396°>0.5°、max d 差 0.23283m>5mm（已非 A）；分区内部逐帧 std max：pitch 0.2196°（A3）/ roll 0.1396°（C1）/ d 0.00564m（A3），均有 ≥0.05° 或 ≥5mm 项。但同时**逐帧分布重尾/非对称**（如 C3 roll median=−5.88、p1/p99=−6.19/−5.56；均值 std 受跳变影响），MAD 与 std 同数量级但仍 ≥0.09°；d 通道在 A/C 之间有约 1~2cm 慢漂移。类型 B/C 干净互斥前提不成立；R3 保留真实形态。

### 3.2 模型 I（分区平面集）

存储格式沿用 R2 `01_DISPLAY_MODEL.json` 的 source-frame 约定（schema 1，R=`Rx(roll)@Ry(pitch)` 主动列向量，tz=d，yaw=0），每区一条 `display:regionN` 记录 + display XY footprint（annotator ROI 各边再内缩 2cm，footprint 之间缓冲带不相交）。

**联合评估（392196 点，每点用自己区的平面）**：RMS **0.01335 m** / P95 **0.02632 m** / support **0.99870** / PASS。
**对照 R2 联合单平面（同点重算）**：RMS 0.01892 / P95 0.03792 / support 0.98562 / PASS。
**Δ**：RMS −0.00557 m、P95 −0.01160 m、support +0.01308 —— 模型 I 把残差压掉 ~30%，证明跨区误差主因是分区几何。

**消费接口草案**：`z_ground(p_source, region=None)`；region 命中用该区 plane_source，region=None 按 display XY footprint 查表。**回退显式**：XY 落在所有 footprint 外 → region=None，调用方必须显式处理 None；不默认最近区、不插值。

### 3.2 模型 II（逐帧 TLS 序列）

03_PER_FRAME_MODEL.npz：772=193×4 条记录（source n/d + ordinals + sigma2 + cov_n + cov_d），cov 为一阶 delta sandwich（PPCF 型、非高斯稳健、PSD），sigma2 = 未修正 ML 残差方差，与 R2 stats 同口径。**协方差只作不确定度参照，不是物理精度**。

时变性：Δ帧 mad pitch 0.13–0.19°、d 0.004–0.006 m；d 通道全段线性趋势 −0.0019~−0.187 m/193 帧（A2/A4 显著），且 CUSUM 检测器在稳健中位数版本下密集报警（每 cell 14–105 点）—— 不是孤立跳变而是持续慢漂移+重尾跳变的混合。**插值禁止跨这些帧**。

消费接口草案：优先**时间索引查表**（772 条，零插值假设、可证伪、缺帧显式报错）；参数插值仅作备选。

### 3.3 升级建议（≤20 行）

见 07_REPORT.html 末卡；核心是 P02 显示配平改分区平面集，模型 I 已给出具体改动面（NPZ/HTML/ground_local 契约均最小），但仍**不升级** physical/runtime；P1-01 仍差独立物理测量、未曝光区域 holdout、距离偏置证据。本建议不授权任何落地改动。

## 验证与回传

- 生成脚本 `p02_r3_analysis.py` → `python -B -W error` exit 0（输出 01~05 + 03 NPZ + 04/05 JSON）。
- 独立数值核验 `check_r3.py`（06_NUMERICAL_CHECKS.json）：forward/inverse/signedZ ≤1e−12 m、proper R(|det R−1|<1e−12)、Rn=up(max |Rn−up|<1e−12)、unit_n、TLS 重算 n/d ≤1e−9、模型 I 数据门 PASS、772 行数、NPZ↔JSON 数值一致、协方差 PSD —— **全部 PASS，exit 0**。
- 页面 `07_REPORT.html` + Node 逻辑检查 `check_html.js`（08_NODE_HTML_CHECKS.txt exit 0）：真实 JSON 渲染出 6 对 FAIL 行、8 canvas、772 行记录数；boot() 404 → 显式「加载失败」；三种坏数据（空 DIAG / 空 series / null M2）→ 明确抛错。**真实 browser NOT_RUN**（file:// fetch 受限，见页面提示）。
- 失败保留：3.1a 六对互预测 FAIL 全部红色展示；类型判定 C 的量化依据包含重尾/漂移形态（未裁尾）。
- 指定独审：NOT_RUN（本单为 Claude Code 作者自验，返回模板允许的 SUBMITTED 状态）。

## 逐 ID 结果

| ID | 结果 | 证据 |
|---|---|---|
| P02-F | PASS（作者自验） | 01_REGION_DIAG.json 分区平面+6 对矩阵（全 FAIL 保留）+8 cell+分解+类型 C；02_FRAME_SEQUENCE.json 772 行 |
| P02-G | PASS（作者自验） | 04_MODEL_I.json 每区 source-frame 记录+footprint+联合评估与单平面对照+消费接口草案；06 数值核验全过 |
| P02-H | PASS（作者自验） | 05_MODEL_II.json + 03_PER_FRAME_MODEL.npz（772 条 n/d+协方差）+时变性（趋势/Δstd/CUSUM/重尾）+消费接口草案；06 NPZ↔JSON 一致+协方差 PSD |
| P02-I | PASS（作者自验） | 只用 R2 冻结 392196 点；不裁尾/不调 ROI/不降门；3.1a FAIL 保留 |
| S01 | PASS（范围与页面逻辑作者自验） | 00_BASELINE.md 输入/保护 SHA、起始 HEAD 3fc1338、用户差异已录；ponytail 声明已写；Node 检查器模拟非法输入 PASS；**指定独审与真实 browser NOT_RUN** |
| D01 | NOT_RUN | 不设备/采集/部署/网络/driver/commit/reset/生产外参写入 |

## 附：产物 SHA（写后实算）

见 10_MANIFEST.json。
