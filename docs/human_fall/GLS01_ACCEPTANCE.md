# GL-S01 地面身份层 / v1

2026-10-05 用户明确授权：仅新增地面身份层 `lowest_floor_sheet_v2`，不降低、不重写 B 层 ROI 质量契约；触面桥接只有在合成测试证明安全后才能进入正式路径。writer：OpenCode（opencode-go/deepseek-v4.1-flash，本会话）；外部独立复审按 WORKFLOW 另行安排，不自行宣布 ACCEPTED。

| ID | 可观察要求 | 覆盖/证据 | 当前结果 |
|---|---|---|---|
| A1 | 合成回归全过：①四块孤立共面小片→拒绝；②障碍触面桥接→按 B 决定（可成功）；③同高低台面、空缺口→身份拒绝；④A 过 B 不足（干净格聚簇）→`INSUFFICIENT_CLEAN_ROI_SUPPORT`；⑥稀疏杂点跨宽缺口→拒绝；⑦2–4cm 起伏地面→A 不断开；另含两个 bug 回归（法向取列、无关小碎片不触发 gap 门）。全部 `-W error`。 | `floor_sheet_test.py` 12 项 + `evidence/2026-10-05_gl_s01_r1/04_all_replay_tests.log` | PASS 作者自验（12/12） |
| A2 | 223757 golden：生产入口 `detect_floor_regions_v2` 在真实 capture 上稳定输出 A=PASS / B=FAIL / `INSUFFICIENT_CLEAN_ROI_SUPPORT`，不生成配平产物、不改源。 | `01_golden_v2_check.py` 产物 `02_golden_v2.log`/`03_golden_v2.json` | PASS 作者自验（clean_cells=6 independent=0 min_sep 0.354 condition 0.162；v1 仍 floor_regions_invalid） |
| A3 | 三个在范围会话（203349/203135/202456）不回归：v2 入口返回与 v1 逐字一致的 regions/kind/推荐，真实 job 复跑三法结论不变。 | 同上 golden 脚本（kind=lowest_connected_floor_v1，regions/candidate 逐字相等）+ `leveling_test.py` | PASS 作者自验 |
| B1 | B 层契约只增不减：逐帧≥30点、厚度≤0.18m、\|n_z\|≥0.94、RMS≤2.5cm、全高度源行、四区互不重叠、最小间距≥0.5m、独立数=4、条件数≥0.1；`floor_detector.py` 内容 SHA 不变。 | `floor_sheet.py`（门直接复用 `floor_detector.PROFILE`）+ SHA 对照（`floor_detector.py` = `72CE790F...` 未变） | PASS 作者自验 |
| B2 | 桥接边界有证明：仅显著碎片（≥0.25m²）、缺口≤4格、缺口占用格触面证据（接触格比≥0.5 且≥1）、仅当最大片<0.5m²时才需要；case②接受、case③⑥拒绝。 | `floor_sheet_test.py` 桥接 3 项（wall 触面 explained、void/宽缺口 unexplained） | PASS 作者自验 |
| C1 | 失败/成功语义固定：A 失败→`floor_regions_invalid: floor identity failed`；A 过 B 不足→`INSUFFICIENT_CLEAN_ROI_SUPPORT`；双过→regions + `kind=lowest_floor_sheet_v2`，`uses_manual_reference=false`、`full_height_preserved=true`。 | 测试 + golden 脚本 | PASS 作者自验 |
| C2 | 消费者：`validation.py:floor_identified` 接受 v2 kind 且 v1 分支不变；`leveling_test.py`/`validation_test.py`/`floor_detector_test.py` 全回归通过。 | `04_all_replay_tests.log`（33 项 OK）；`leveling_test` 稀疏 auto 仍 `floor_regions_invalid` | PASS 作者自验 |
| C3 | 审计：auto `run_job` 的 `code_files`/`code_hashes` 纳入 `floor_sheet.py`；v2 候选携带证据字段（effective_area/coverage/gap/temporal/roi_metrics/fit_frame_count）。 | `leveling.py` 变更 + `floor_sheet.py` candidate 字段 + 测试断言 | PASS 作者自验 |
| S01 | 流程：ponytail 已加载并记录路径；基线/改前 SHA；回归命令与日志；不越界（不改 v1、不改 B、不改 webui/captures/旧证据、不 commit/push/reset）。 | `returns/GL-S01.md` + `evidence/2026-10-05_gl_s01_r1/00_scope_baseline.md` | PASS 作者流程；外部独审 NOT_RUN |
| D01 | 设备/物理/采集/部署 | 本单只离线软件，不以数值 PASS 代替 | NOT_RUN |
