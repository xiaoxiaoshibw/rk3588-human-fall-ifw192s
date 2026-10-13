# CLUSTER-ADAPTIVE-SPIKE-R1 — 距离自适应聚类离线验证证据目录

日期：2026-10-10
状态：**执行中**（最终裁定在 `FINAL_REPORT.md`，由后续 commit 补齐）

## 0. 任务边界（与工单一致）

只验证 B1 `find_clusters` 的**距离自适应聚类**离线收益；不训练 RF、不改任何生产路径、不动 RK3588 部署。
P 轨道 (`human_pipe_lib.cluster_voxels`) **不在范围**——理由：当前主线是 B1（HR-09/W09 active），P 轨道改聚类属另案。

## 1. 数据绑定冻结（`baseline.json`）

12 段评估会话 + 7 段调参会话已冻结 SHA（首 1MB/总字节数 + meta/ai_labels全量）。见 `baseline.json`。

### 1.1 会话名单

| 角色 | 会话 | 公开锚 |
|---|---|---|
| **调参 (T0)**: 只用它们定 k | cap_20261007_143945 / 150455 / 154007 / 154341 / 154545 / 154920 | 见 §2.1 (114641 移出 T0, 与 E-stand 交叠) |
| **评估静立 GT (E-per)**: | cap_20261007_215540 | 锚 (2.10,-0.57) r=0.55 （README）|
| **评估站立 GT (E-stand)**: | 11 段 1009 站立 (114709/114734/114754/114817/121622/121647/121723/122616/122637/122700/114641 复用）| `ai_labels.json` |
| **空场零锚 (E-none)**: | cap_20261009_113611 | 期望 0 hot / 0 confirmed |
| **多场景参考 (E-ref)**: | 114205 / 114254 / 114340 / 114422 | （姿态 break-case 档案） |

### 1.2 已知 GT 缺口（诚实声明，源自 GT 勘查）

- **r_xy &gt; 3.0m 真人 GT：无**（C1.5 §2 明确缺口）
- **r_xy &lt; 1.2m 真人 GT：无**
- **弯腰/走动/多人 GT：仅 synth_bend_v1 （合成） + 154007 (assist 级）**
- 若参数需要在那些区间生效，**只能标 UNKNOWN，不能报 PASS**

## 2. 标定流程

| 步骤 | 谁做 | 产出 |
|---|---|---|
| p50 NN 点距按距离环估计 | `calibrate_k.py` （只用 T0) | `calibration_k.json` |
| k 与 eps_min 敲定 | 青鹿 LAD 拟合 + 加安全因子 1.5–2.5 | `params_frozen.json` |
| 调参门 | **不进 E0，不回填评估阈值** | 评估不许反向改参 |

## 3. 实现

- A （复现现状）: `_harness_lib.find_clusters_A`
- B （自适应）: `find_clusters_BC` with `eps(r)=max(eps_min,k*r)`
- C （自适应 + 防并簇）: `bridge_policy="height_band"`, wall_bands 见 params_frozen
- A/B/C 唯一变量：邻域扩张规则；其它 5cm/4096 KEY/MIN_POINTS=30/TOP_K=4 与 B1 完全一致
- A 的 Python 与 JS 实现已逐帧 IoU=1.0 对拍通过 （见 §4.1)

## 4. 评估指标（每会话 × 每个算法 逐帧）

| 域 | 定义 |
|---|---|
| 悬浮 | n_comps（含被 min_pts 过滤的） |
| 完整性 IoU(人工簇） | ∩(人锚圈 r=0.55m) ∪ |
| 碎簇率 | 锚圈外有成员、Top4 排外的"人专属簇"簇数，110cm z 兼容 |
| 人+家具并簇率 | 同时覆盖柜位锚点与人锚点的簇占比 |
| RF 正确拒绝率 | E-none 期望 100 （或 UNKNOWN) |
| 静立吸收归因 | hot=0 时聚类 UNKNOWN （不归因聚类） |
| 性能 | find_clusters 耗时 P50/P95 ms、hot/cell/comp 数 |

统一规则：
- 帧间独立性按 **同track 簇段 (≥3 连帧）** 为独立样本单元（Wilson 区间用段数而非帧数）
- 分层： 按 r 分带 （0-1.5/1.5-3/& gt;3m)，按姿态 (stand/站举/站侧），按动静

## 5. 与已有文档的接口

- 输入： STILL_PERSON_RETENTION_PLAN / RF_OPTIMIZATION_R1 / C1.5 等接头参考
- 输出： CLUSTER-ADAPTIVE-R1-ACCEPTANCE.md （下一阶段草案） + FINAL_REPORT.md （裁定）

## 6. 排除事项（明示）

| 不做 | 理由 |
|---|---|
| 改 RF 51 维特征 | 另案 R1 规划 |
| 上板 RK3588 | 未授权 |
| 引入 PointNet/Open3D 等 | 已证跨域失败 + 超出 stdlib+NumPy |
| 调生产阈值 （含 RF_THRESHOLD) | 本轮只动"参数到 spike 脚本", 生产不变 |

## 7. 运行复现

```bash
cd pc_apps/human_ml/spike_cluster
python -B freeze_baseline.py   <evidence_dir>     # 已完成 (SHA 冻结)
python -B calibrate_k.py       <evidence_dir>     # 进行中 (T0 段)
python -B rerun_crosscheck.py ...                 # A 复现 PASS 验证
python -B eval_cluster.py      <evidence_dir>     # 中段: A/B/C 在 E0 全对比
python -B attribution_fail.py  <evidence_dir>     # 失败归因
```

## 8. 约定真相承诺

- 任务#7: **每个 A 成功但 B/C 失败的场景单独归因**, 展示其可视化
- 任务#9: **OpenCode 独立审计失败就写"失败的真实原因", 不虚构通过**
- 任务#11: 最终裁定只可 PASS/FAIL/UNKNOWN 三档；UNKNOWN 配根因和最小下一步
"PASS" 含义 = 至少一项人体聚类指标在评估会话上的可复核提升, 且柜位误检/运行成本没有不可接受退化.

## 9. 文件索引（已落盘 / 可复算）

| 文件 | 内容 | SHA 见 |
|---|---|---|
| `README.md` | 全文索引与任务边界约定 | manifest.json |
| `FINAL_REPORT.md` | **最终报告 + UNKNOWN 裁定** | manifest.json |
| `NEXT_ACCEPTANCE.md` | 下一阶段 ACCEPTANCE 草案 (R2) | manifest.json |
| `FAIL_ATTRIBUTION.md` | 5 失败/2 PASS+1 UNKNOWN 案例归因 | manifest.json |
| `SUMMARY.md` | 分层汇总; 段/帧两口径 | manifest.json |
| `baseline.json` | 22 段输入 SHA + 常量 + git HEAD 冻结 | manifest.json |
| `manifest.json` | evidence+spike 代码+生产 SHA 全 SHA | manifest.json (自指) |
| `calibration_k.json` + `calibrate_k_stdout.log` | p90 NN/LAD 在 TUNING 段估计 | manifest.json |
| `crosscheck_114641_f100.log` `crosscheck_215540_f30.log` `crosscheck_121622_f87.log` `crosscheck_114205_f122.log` | A (Python) vs A (JS) 逐帧 IoU=1.000 对拍 4 例 | manifest.json |
| `test_bc_impl.log` | B/C 实现性质测试 6/6 PASS (单元测试) | manifest.json |
| `eval_frames.jsonl` | 2874 帧 × 3 变体的逐帧完整记录 (5.3MB) | manifest.json |
| `eval_diff.json` | A/B/C 人锚命中差异帧扫描: n_diff=0 | manifest.json |
| `eval_timing_ms.json` | A/B/C find_clusters 耗时分布 (P50/P95) | manifest.json |
| `audit_opencode_v3_flash.md` | OpenCode 审计 9 条结论 | manifest.json |
| `audit_request.txt` | 审计请求原文 (opencode 输入) | manifest.json |

## 10. 与本证据目录关系的 spike 源码（位于 pc_apps/human_ml/spike_cluster/，亦在 manifest.json 记 SHA）

`_harness_lib.py` `_harness_lib_v2.py` `freeze_baseline.py` `calibrate_k.py` `eval_cluster.py` `summarize_eval.py` `rerun_crosscheck.py` `smoke_crosscheck.js` `test_bc_impl.py` `crosscheck_diff_frames.py` `write_manifest.py` `params_frozen.json`

## 11. 最终裁定（来自 FINAL_REPORT §0）

**UNKNOWN**（"人体聚类质量有可复核提升"在 12 段站立 GT 上不成立；无 FAIL 退化）。
唯一合法行动：本 spike 关闭；下步以"走/弯/多人/远距 + 柜位真因"为采集/特征的新 ticket 处理（NEXT_ACCEPTANCE §A)。
