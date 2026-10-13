# HFUS-D04 R1 — S9 GT_V2 session_sha256.points 占位 rebind 调查与补丁记录

日期：2026-10-11。范围：仅调查 + 生成待人工签名的 patch 记录。**GT_V2.json 未修改、patch 未 apply、S9 仍为 INVALID_BINDING / fold=blocked，BLOCKED 状态保持。**

## 1. 调查事实（复现）

对象：`pc_apps/human_replay/gt_store/cap_20261010_180751/GT_V2.json`

- `session_id`: `cap_20261010_180751`（S9）
- `review_status`: `reviewed`；`objects` 共 36 个（任务书「36 对象」属实）
- `annotated_at`: 2026-10-10T14:28:33Z；`frozen_at`: 2026-10-10T15:13:26Z；`frozen_versions`: []
- **`session_sha256` 字段实际只有 `points` 一个键，值为 64 个 `a`（占位）**：
  `{"points": "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa"}`
- **`session_sha256.meta` 键不存在**（不是值错，是字段缺失）。

真实文件 SHA256（本次现算）：

- `captures/remote/cap_20261010_180751/points.bin` = `7d978a67336459f702c91a9eb77f69bee2fef6f444889ee1a0e15eb106726dbd`
- `captures/remote/cap_20261010_180751/meta.json` = `60ddb3d5bc5b2cf078a66a84a7f69f8d71ce9df0a0ff5cf106d42ee87be5b323`

D03 FINAL_MANIFEST 同 sid 记录（`docs/human_capture/evidence/2026-10-11_hfus_d03_r1/FINAL_MANIFEST.json` 与 `_V2.json` 一致）：

- `sha256.points` = `7d978a67...26dbd`（与现算一致）
- `sha256.meta` = `60ddb3d5...b323`（与现算一致）
- `GT_sha256` = `285c11026b57c5c68318cc2869b4c5a82a3d8bb27c5e93db2ea59008e9a11e52`（与当前 GT_V2.json 文件实算一致 —— GT 自 D03 以来未被改动）

**GT 里哪个对、哪个错**：`session_sha256.points='aaaa...'` 是错的（占位，从不匹配任何真实 points.bin）；正确的值应为 `7d978a67...`（与 D03 记录及现算一致）。`session_sha256.meta` 不存在可比对的对象——所以「session_sha256.meta 是否仍匹配 meta」的调查结论为：**否**（GT 里没有 meta 键，无从匹配；meta.json 本身 sha 与 D03 记录一致）。

附注：D04 任务书引用的 `points=6a7e273a...bfe7` 在 D03 FINAL_MANIFEST 中不存在；D03 两版 manifest 与本次实算三方一致为 `7d978a67...`，以实证为准。

## 2. 补丁生成记录

- 工具：`sidequests/human_fusion_lab_next/d04/s9_rebind.js`（本次交付；无 `--apply`，只有 `--check` / `--emit`）
- `node s9_rebind.js --check pc_apps/human_replay/gt_store/cap_20261010_180751/GT_V2.json docs/human_capture/evidence/2026-10-11_hfus_d03_r1`
  → **exit 0**；checks 全过：`before_points_is_placeholder=true`，`d03_points_match=true`，`d03_meta_match=true`，`meta_key_present_in_gt=false`。
- `node s9_rebind.js --emit <同上>` → **exit 0**，生成：
  **`docs/human_capture/evidence/2026-10-11_hfus_d04_r1/s9_rebind/rebind_patch.json`**
  （`fs.open 'wx'` 写入，不覆盖既有；重复 emit 以 EEXIST 拒绝）
- patch 内容要点：`before.points='aaaa...'` → `after.points='7d978a67...'`；meta 键 before/after 均记录为 `null`（GT 中缺失，本补丁不虚构 meta 键值，仅如实记录缺失）；`signed_off_by_human=null`，`apply_authorized=false`。
- 幂等/保护验证：emit 后 GT_V2.json sha256 仍为 `285c1102...`，与 D03 记录一致 —— 原始 GT 未被触碰。

## 3. 该 patch 未 apply —— GT_V2 仍 INVALID_BINDING

本工具**故意不提供 `--apply`**。D02 合同规定 GT 绑定修复须人工审核签名后方合法；工程侧只交付记录。

申请 apply 的必经人工 step：

1. 人工审阅 `rebind_patch.json`，核对 `after.points` 与 D03 FINAL_MANIFEST 同 sid 记录、以及 `captures/remote/.../points.bin` 实算 sha 三者一致。
2. 人工在 patch 中填写 `signed_off_by_human` 并置 `apply_authorized=true`（或另行签署等效授权记录），同时明确决定：是仅修 `points` 值，还是连同补入缺失的 `session_sha256.meta` 键（本补丁如实记录该键缺失但未代拟其值——补 meta 属 GT 结构变更，更需人工拍板）。
3. apply 之后须重跑 D02 绑定验证（S9 `original_gt_binding`）、重算 GT_sha256 并向 D03/D04 manifest 追加新记录（不覆盖旧记录）。
4. 在上述完成前，S9 保持 `fold=blocked`、`S9_identity=BLOCKED`（D02 `qualification.json`），任何汇总结论不得引用 S9。

**状态：BLOCKED 保持。**

## 4. D02 package_01 capabilities 层观察（一并提交，供人工决定）

- D02 `package_01/review_package.json` 550 条记录中含 S9（sid=cap_20261010_180751）40 条，fold 已标 `blocked`、`original_gt_binding="INVALID_BINDING"`、`qualification="UNKNOWN"` —— 排除语义在记录级已落实，未发现把 S9 混入 train/validation/test/stress 的泄漏。
- 观察到的薄弱点（capabilities/资格层，非 GT 内容问题）：
  1. `review_package.json` 顶层与记录级**没有独立 capabilities 声明字段**表达「本包的 S9 记录仅供审计、不具备任何下游资格」；排除只靠 `fold="blocked"` 一个字面值承载。建议人工决定是否需要在后续包版本加显式 capabilities（如 `capabilities: {usable_for_eval: false, reason: "INVALID_BINDING"}`）。
  2. `qualification.json` 以 `S9_identity: BLOCKED` 单列，与其余按 fold 聚合的结构不同构，消费方需特判。
- 以上仅是工具包结构层面的建议，不修改 GT、不修改 D02 既有证据，是否采纳由人工决定。
