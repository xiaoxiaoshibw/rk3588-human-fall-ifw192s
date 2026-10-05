# 支线任务盘点 / 2026-10-02 重制定（v2）

> **归档说明**：本表是 2026-10-02 晚基于主线时点重新制定的现行视图。首次编制的旧版见 [REVIEW_v1_archive.md](REVIEW_v1_archive.md)（2026-10-02 早，板端不可达、HR-01/HR-02 未落地时的口径）。**原版 T1 的结论已被 HR-01/HR-02 直接推翻——不要按 v1 行动。**

## 自 v1 以来的关键变化（重制定的依据）

| 维度 | v1（2026-10-02 早） | v2 现状（2026-10-02 晚） |
|---|---|---|
| 板端 SSH 22 | NOW BLOCKED，测试失败 | ✅ **实测可通**（`ssh ldiar-wel` BatchMode 通；主机时钟显示 2026-10-02 周五 18:50，比 PC 慢约 3 小时，属已知） |
| 真实点云素材 | 仓内 0 个 pcap/bag；captures/ 不存在；唯一样本是 8k 单帧平面 | ✅ 板端 SSD 已有 **22 个 `cap_*` 会话目录**；PC 已拉回 3 个到 `D:\Code\ldiar\captures\remote\` |
| PC 回放链路 | 仅 `fall_replay.py`（npz 离线算法回放）；preview 页无离线模式 | ✅ **HR-01 fetch.py**（8766 REST→scp 限速→sha256→PATCH，已 push `2f5385a`）+ **HR-02 点云回放器**（worktree `pc_apps/human_replay/`，未 commit/push）已落地 |
| GL-03 主线 | R2 修复自验完、returns 尚未追加，未 SUBMITTED | ✅ **R7 已收口**：软件 G01/G02/G03/G04/G05/G07/G08 PASS、G06/D01 BLOCKED、无 R8 |
| GL-04 | 未出现在 v1（未派工） | ✅ **GL-04 R1 已 SUBMITTED**（preview 网页修复，OpenCode，未 commit/push） |
| HR 链后续 | 不存在 | HR-03..05（剪辑/导航/3D 标注）**HR-05 标注**依赖 HR-02+HR-04，不能跳 |
| 1111 暂存入库 | 提案 | ✅ 已按 T6 分批全入库（最新 HEAD `8633eac` HR-02） |
| 板端 8090/8765 | BLOCKED | 容器内无 curl 无法实测；页面/bridge 仍可 PC 浏览器直连访问 |

## 现行支线总表（v2，按主线推进的下一步向量重排）

| 新 ID | 任务 | 状态 | 关键结论 & 依赖 |
|---|---|---|---|
| **S1** | **HR 自采-回传-回放链收口**（接 HC-01..04 与 HR-01/HR-02 主板） | 🟡 **下一单主线** | HR-03（剪辑）→ HR-04（导航）→ HR-05（3D 人工标注 + `source:"human"`）；**HR-05 是标注，必须 HR-02+HR-04 完成后开始**。工单/密约在 `docs/human_capture/` |
| **S2** | **GL-04 收口 & 板上复审** | 🟡 Codex 主线的下一步 | GL-04 R1 已 SUBMITTED；V10 BLOCKED、D01 NOT_RUN、浏览器交互证据 NOT_RUN——现在**板端可达**，可以补浏览器/真机证据；GL-03 R7 的 G06/D01 BLOCKED 也依赖板。推进方向清晰：**从软件层转向设备层证据** |
| **S3** | 把 `cap_*` 点云素材引入 HF 离线链（+回看旧 T1） | 🟢 **现在可做** | 板端 22 个 session、PC 3 个已就位；HR-02 已把 28B meta/点帧通灵，**只差"回放→fall_replay 算法输入"一步**。旧 T1 说"无素材缺工具"已成过去式 |
| **S4** | 板端 WebUI 通道 / 运维改进（接旧 T5） | ⚪️ 待激活 | bat 明文 → `ssh ldiar-wel`、8090 兜底失败静默、8765 无检测；GL-04 真机复审会自然把这些暴露出来，**不需要单独开工** |
| **S5** | HR-02 与 GL-04 的 worktree 处理 | 🟡 渐进 | `pc_apps/human_replay/`（HR-02）+ `webui/human_fall_preview/`（GL-04）都还没 commit/push；滚入主线时的单独批次，不强行 | 

## 已归档（v1 原文及替代路径）

| 旧 ID | 旧任务 | v2 状态 | 接替工件 |
|---|---|---|---|
| T1 | 无板离线回放链路盘点 | 🟠 **过时** | S1（HC/HR 自采链已把"需要 bag/pcap"变成已有素材）+ S3。原报告留档 [T1_replay_boundary.md](T1_replay_boundary.md) |
| T2 | 驱动 diff 审查（publish_manager.cpp） | 🟢 **已完成** | `ef67461` 已入库（HF-02 R2 终态，sha256 已锁定）。原文留档 [T2_driver_diff_review.md](T2_driver_diff_review.md) |
| T3 | 跌倒文献补 Lai 2026 | 🟢 **已完成** | `49eb758` 已入库；`文档/跌倒检测文献/` manifest 已更新。PDF 由机构渠道后续 |
| T4 | 10-1 数据集调研 README 补强 | 🟢 **已完成** | `49eb758` 已入库（6 篇均判**不能直接复用**，借密度/阈值）。原文留档 [T4_dataset_survey.md](T4_dataset_survey.md) |
| T5 | `open_webui.bat` 运维通道盘点 | 🟢 **已完成，建议并入 S4** | SSH 在线；bat 本身可用，3 条改进可并入 S4 的一次板端巡检。原文留档 [T5_webui_ops.md](T5_webui_ops.md) |
| T6 | 仓库卫生与分批入库 | 🟢 **已完成** | 所有批次已入库（`ef67461` → `8633eac` 全链）。原文留档 [T6_repo_hygiene.md](T6_repo_hygiene.md) |

## 现在的明确阻塞 / 下一步

| 项 | 谁负责 | 需要的外部动作 |
|---|---|---|
| S2 真机/浏览器证据 | Codex 主线 | 板端恢复后走 GL-04 R1 的 V10/D01；**不需要在支线层面新增工具** |
| S1 下一单 HR-03 | 主线/Codex | 用户在 `docs/human_capture/README.md` 的授权；我只是支线观察员，不发起 |
| S3 回放→算法输入 | 增量工具 | 以 HR-02 的 meta/28B 结构为输入，把 fall_replay 的 npz→点云 通路补上；**比旧 T1 的"写 bag→npz 转换器"范围小得多** |
| 板上 boot 一致性 | 运维 | SSD bind/容器重建后 symlink（见 BOOTSTRAP.md）；不属当前支线 |

## 保持的边界（从 v1 继承未变）

- 支线只读 + 单文件写入；不动主线工单 / 冻结资产（`config/default.yaml`/`geometry.yaml` / `src/CMakeLists.txt` 软链 / 不占 line).
- 文献/公开数据集不直接进本项目的训练/评测集（T4 结论仍然成立）。
- 驱动 C++ 在 R2 已锁定，不再因支线去改；任何改动回到 HF 工单主线。

—— 这份 v2 是当前主支线视图；v1 保留作为"板端不可达时期"的历史参照。
