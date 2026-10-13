# 01 · R3.5 Step-0 Baseline 等价 / 守恒 / 自检（G0 门）

- 日期：2026-10-06；writer：OpenCode（DeepSeek v4.1 Flash）；ponytail full。
- 数据源：`02_attribution_results.json`（digest `4b89a0444991d60f84c01961cf732fc4447e2cad4f8536bb99d89f01485d0c0c`）、`12_run1_stdout.log`、`13_run2_stdout.log`。
- 结论：**G0 全部 PASS**（165/165 帧 + micro-cases 逐点 0 mismatch；守恒成立；标签分区 = residual；在线 map 复刻等价；两次运行确定性一致；跨轮关键数字全部复现）。归因结果的有效性以本文件为前提（归因内容见 `05_frame_analysis.md`）。

## 1. BASELINE_A shadow 与 production 逐点等价（工单 §三）

被测生产语义：`extract_foreground(denoised, online_map)` = z∈[0.10,2.50] 裁剪 + `_bg_match`（3×3×3 邻域、点到形心距离 `< 0.12`、命中即删）。shadow 侧独立实现同语义（`shadowExtract`/`shadowBgMatch`，同参数同算式），对 **全部 165 帧** 逐点比对：

| 检查 | 结果 |
|---|---|
| 帧数 | 165 |
| 残差数组长度/计数不一致帧（`n_fg`、`n_dropped`） | **0** |
| 逐点身份 mismatch（`fg_xyzi` Float32 元素逐位、含 i 通道） | **0** |
| 守恒不一致帧（§2） | 0 |
| 生产语义自检违例（residual 点竟能被在线 map 命中） | **0** |

## 2. 守恒（工单 §四/§十一 Check 1）

全 165 帧合计（值取自 JSON `conservation.totals`，逐帧 `conservation_ok=true`）：

```
N_FRAME_RAW  8,105,838
   − N_RANGE_REJECT        0        （0.35–25 m 距离窗，在 TLS 配平后应用 → 见下注）
   = N_DENOISE  8,105,838
N_DENOISE
   = N_Z_REJECT  3,086,548           （z ∉ [0.10, 2.50]，主要为地板/上沿）
   + N_BG_MATCH  4,259,941           （在线 map 命中删除）
   + N_RESIDUAL    759,349           （= 本工具归因对象全体）
```

- `N_Z_REJECT + N_BG_MATCH + N_RESIDUAL = N_DENOISE` ✓；`N_RESIDUAL == production n_fg` ✓；`N_Z_REJECT + N_BG_MATCH == production n_dropped` ✓（逐帧）。
- **注**：`n_range_reject=0` 不是漏检——console 口径为「先 TLS → 再 denoise」，denoise 的 0.35 m 下限量的是**配平系原点到点的距离**（原点到地面投影点），不是传感器距离；本会话 leveled 数据中无点落入该窗内（另有 1,250,007 个原始点位于传感器 0.35 m 内，经 TLS 提升后位于配平系原点上方 ~1.32 m，不受该窗影响）。该事实只影响"距离窗是否触发"，不改变与生产的一致性（逐点等价已证）。

## 3. 逐帧守恒之外的三项强制自检

1. **标签分区 = residual（Check 2）**：165/165 帧 `sum(primary label) == n_residual`（PASS；`UNKNOWN` 标签实际用量 = 0）。
2. **在线 map stats 复刻等价（02 §4.1 门）**：复刻键集 1,720 == 生产 `build_static_map` 1,720；逐键 `tier`/`hits` 与形心（双精度逐位 `===`）**全等，0 mismatch**（strong 1,480 / supported 240）。
3. **inputs_unchanged（Check 5）**：运行前后 7 个输入 SHA（3 源码 + 2 会话 × meta/points）全等 → 未动输入、未动生产（另见 `00_provenance.md`）。

## 4. 确定性（Check 4；两次完整独立运行）

| 项 | run1 | run2 |
|---|---|---|
| 模式 | full（写本目录） | full（写临时目录） |
| 规范化 digest（不含 generated/elapsed_ms/mode） | `4b89a0444991d60f84c01961cf732fc4447e2cad4f8536bb99d89f01485d0c0c` | 同左（**一致**） |
| `03_attribution_points.csv` SHA256 | `08691659aaf26bf122d3f13be164d6b4c9a7cb5e7d6842512248b1ca7327f4e6` | 同左（byte-identical） |
| `04_attribution_voxels.csv` SHA256 | `5662d18f1fd52f43ab4af567d77824f0add5d13c06349263105fb87737f25e30` | 同左（byte-identical） |
| `02_attribution_results.json` | `83e4ecca…` | 仅 `generated`/`elapsed_ms` 不同；去时间戳后归一化 SHA 相同 |

## 5. micro-cases（03 计划 G0：恰在门限/跨格/±1 边界/z 裁剪边界）

| 用例 | 点数 | 生产 residual | shadow residual | mismatch | 手写期望核对 |
|---|---|---:|---:|---:|---|
| C1 手工单体素：三轴 ±(r∓1e−6)、对角 (r/√3·(1∓ε))、±2 格外 | 13 | 7 | 7 | **0** | PASS（13/13 outcome 符合设计期望） |
| C2 空 map：z = 0.10 / 0.10−1e−9 / 2.50 / 2.50+1e−9 / 1.00 | 5 | 5 | 5 | **0** | PASS（裁剪边界含取等） |
| C3 真实在线 map 孤立 strong 体素：三轴 ±(r∓1e−6) | 8 | 4 | 4 | **0** | PASS（4 内点被吸收 / 4 外点残留） |

（C3 的孤立判据 = 该体素 0.35 m 内无其他在线体素：此时任意测试点到邻近体素距离 ≥ 0.35−0.12 > 0.12，期望无歧义。）

## 6. 跨轮复现 CHECK（与既有 R3.1–R3.3/r5 记录对齐）

| 检查 | 本轮实测 | 既有记录 | 判定 |
|---|---|---|---|
| reference map 体素数（203349, hit_min=1） | 5,286 | r4/04：5,286 | PASS |
| reference occ≥0.5 体素 | 3,707 | r4/04：3,707 | PASS |
| 参考会话自带在线 map（build_static_map on 203349） | 2,063（strong 1,885 / supported 178） | r4/04：2,063（1,885/178） | PASS |
| ICP 复跑（R3.2 同款，ref occ≥0.9 ↔ cur strong） | iters=48；roll 1.7476 / pitch −0.2818 / yaw −2.3924；t=[0.0182,0.031,0.0012] | r5/11 保存值逐位 | PASS |
| R3.3 A 层（ALL 抽稀，occ≥0.5，none/center） | **0.779556** | 0.7796（±0.0005） | PASS |
| probe f10 簇（n / no-align center 命中） | 1564 / 1365 | r5 探针：1564 / 1365 | PASS |
| probe f55 簇 | 3190 / 621 | r5 探针：3190 / 621 | PASS |
| probe f160 簇 | 2429 / 1024 | r5 探针：2429 / 1024 | PASS |

统计侧信息（`maps.ref`，仅登记，不作为硬检查）：`occ≥0.5 且不在当前在线 map 且 每帧<2 点` = 1,653；`occ≥0.5 且不在当前在线 map 且 从未出现 ≥2 点/帧` = 612。r4/04 的 1,834/1,632 是**对参考会话自身物性**的统计（"每帧<2 点"的定义及其对照 map 与本处不同），两者不构成冲突；硬检查（5286/3707/2063）已逐位对齐。

## 7. 本文件不证明什么

- 等价性只证明"shadow 复刻了生产的行为"，**不**证明归因标签正确（那是 `05` 的内容，且均为 proxy）。
- micro-cases 是行为边界核对，不是统计验收。
- 确定性一致仅表示本工具在相同输入下可复现，不代表结果对 registration 条件的选择不敏感（敏感性正是归因要测的东西，见 05）。
