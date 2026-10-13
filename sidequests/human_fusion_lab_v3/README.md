# HUMAN-FUSION-BG-V3 Demo V3 启动与复现

研究入口：http://127.0.0.1:8800 （或 `node sidequests/human_fusion_lab_v3/server_v3.js 8800`）。

对照 V2：http://127.0.0.1:8798 (`node sidequests/human_fusion_lab/server_v2.js 8798` 仍开，互不冲突）。

## 启动

```powershell
node D:/Code/ldiar/sidequests/human_fusion_lab_v3/server_v3.js 8800
# 浏览器打开 http://127.0.0.1:8800/
```

依赖：本机 Node.js；冻结 captures/remote；冻结 `human_fusion_lab` 全套 V2 资产（审计/GT/模型/包络）。

## V3 相对 V2 新增

- **A/B/C 三组背景对照**（同一空场包络源 cap_20261009_113611，SHA 28afdaa4…）：
  - A = 生产 V2 现有算法（包络热点 + 0.25）
  - B = 生产容差体素（build_reference_map + extract_foreground_fused，occ≥0.5 体素）
  - C = 距离自适应 τ(r) 差分（参数 τ0=0.15 k=0.05/min0.12/max0.45）
- **右侧"背景组 A/B/C"**选择器 + "激活组 FG"高亮（蓝点）+ 原 `foreground`（V2 PFUS A 链）独立勾选
- **"逐点追溯"**：GT 人体前 24 raw 点在激活组的 kept/reason 高亮（绿=保留，红=删除）
- **状态行打印** BG 对照（A/B/C × GT 人点/家具点级 kept/raw）和包络 SHA 前缀
- 四模型仍冻结（V2 不动），外加 PointNet 影子对照（不采纳，仅评估）

## 复现工具链（全部在 `tools/` 下）

```bash
# 1) 背景资格核查
node sidequests/human_fusion_lab_v3/tools/audit_backgrounds.js
# 2) A/B/C 三组逐帧评估 (九会话全帧)
node sidequests/human_fusion_lab_v3/tools/eval_bg_groups.js
# 3) S6 逐层归因 (B 组, 91/128)
node sidequests/human_fusion_lab_v3/tools/layer_attribution.js cap_20261010_180235 91,128 B
# 4) S6 候选改进验证
node sidequests/human_fusion_lab_v3/tools/candidate_improve_s6.js
# 5) S9 GT 修复 (双轨 provenance + label_derived)
node sidequests/human_fusion_lab_v3/tools/audit_s9_gt.js
# 6) B 组候选行导出 (S1 家具 neg / S9 blocked 候选)
node sidequests/human_fusion_lab_v3/tools/export_bg_candidates.js cap_20261010_175227
node sidequests/human_fusion_lab_v3/tools/export_bg_candidates.js cap_20261010_180751
# 7) +B 家具 neg 消融 (已弃置, 模型已删)
python -X utf8 sidequests/human_fusion_lab_v3/tools/train_bg_rf.py
# 8) 四模型 + PointNet 同点集受控对照
python -X utf8 sidequests/human_fusion_lab_v3/tools/eval_controlled_comparison.py
# 9) V3 整树基线 / 最终对账
node sidequests/human_fusion_lab_v3/tools/build_baseline_v3.js
node sidequests/human_fusion_lab_v3/tools/freeze_v3.js
```

## 证据目录（READ ONLY）

`docs/human_capture/evidence/2026-10-11_human_fusion_bg_v3_r1/`：
- **REPORT_FINAL.md** — 七问逐项回答
- V3_BASELINE.json / V3_FREEZE_FINAL.json — 12,154 文件对账
- BG_AUDIT.json — 9 会话 ELIGIBLE（同 setup 实测）
- BG_GROUPS_EVAL.json — A/B/C × 2,605 帧 × GT 对象逐点
- LAYER_ATTRIBUTION / CANDIDATE_IMPROVE — S6 根因转移证据
- S9_GT_PROVENANCE_DRAFT.json — S9 修复（非 GT，DRAFT_UNREVIEWED）
- CONTROLLED_COMPARISON / TRAIN_BG_REPORT — 四模型+PointNet 对照, +B neg 消融弃置
- CASES.json — 38 案例（V2 35 + V3 3）

## 诚实声明

- **V3 不改 V2 检测链**；四模型候选/track 数据与 V2 COMPARISON.json 完全相等。
- **V3 不改生产**：src/inno_lidar_ros, src/human_fall_detection, pc_apps/human_replay 生产源, webui 全部 SHA 与 V2 HEAD 026e063 一致。
- 已知外在文件 (Q01_BROWSER_E2E/Q01_FINDINGS/DEMO_BROWSER_E2E/UNIFY_REGRESSION/server.js) SHA 与任务开始时一致，未前进。
- 验证自写 (validate_v2 cap_*) 是同一管线重放，内容等价覆盖。
- S9 可信 GT 仍 BLOCKED；+B neg 消融已弃置；XGB 家具泛化 UNKNOWN（新证伪）；S6 完整修复 UNKNOWN；跨场景/演员/日 UNKNOWN。
