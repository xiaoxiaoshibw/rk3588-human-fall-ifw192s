# DET-07 — 归档关闭（ARCHIVED-CLOSED，2026-10-11）

> 性质：本单无执行轮（无 R1、无 evidence 目录、无前向/采集/训练）。本篇是**归档对账记录**，不是实验回传。
> 触发：用户 2026-10-11 明确指示「正式归档关闭」DET 支线。

## 一、关闭范围

| 项 | 终态 |
|---|---|
| DET-01..05 | 已完成 SUBMITTED， acceptance + evidence + returns 三件套全在，**不动**（历史证据链） |
| DET-06 | 已完成 SUBMITTED（+ 独立复核轮 + 修复轮）；`gt_eval_v1`/`gt_eval_v2` 冻结资产**不动**；遗留 BLOCKED 项（E03/G01/L01）、NOT_RUN 项（D01）随支线关闭**自然失效** |
| DET-07 | 草案 v0.1 **从未冻结、从未授权、从未执行** → 归档关闭。三份草案文件（PLAN/ACCEPTANCE/CAPTURE_DESIGN）已加归档头注保留全文 |
| sidequests/human_detectors/ 工作树代码 | 未入库（主树 `?? sidequests/human_detectors/` 整目录未跟踪），活在 codex/human-detector-models worktree。归档=不再推进，不删除、不整理；如重开须先按 T6 流程入库 |
| lidata_adapter / CL2-xx 等其他 sidequests | **不在本次关闭范围**，状态不变 |

## 二、关闭理由（对账）

1. **根问题已由别的路线收口**：DET 支线要回答的是「HR-07/HR-08 证死后怎么可靠检出人」。2026-10-09 起 HR-09 用自采 12 段会话 + 51 维特征 + 随机森林（person/noperson）达成域内 LOSO acc=1.000、空场 0/518 帧误报，且已进 `pc_apps/human_core/` 生产链路（HUMAN-UNIFY-R1 统一 + B1 独立页交付）。预训练检测器路线不再是推进方向。
2. **DET-06 自身结论亦支撑关闭**：预训练 PointPillars（跨域权重）在本传感器上「能响但不可接受」—— 压空场需 τ>0.55 时 recall 仅 ~21%；修复轮 `subvox32` 增益（LOSO ≤0.5 时 91.7%）未经未污染数据确认即失去确认必要性。
3. **DET-07 的确认实验成本（新采集 2–3 段人 + 1 段空场 + 逐帧标注冻结 + 按人隔离 test）与其剩余信息量不匹配**：它回答的「subvox32 是否稳定复现」只服务于一条已不打算走的路。

## 三、遗留开口清单（关闭即冻结，重开须新工单）

- `subvox32` 增益无确认性证据（C1 污染声明永久有效，DET-06 数据不得再充当确认 test）。
- DET-07 采集设计的 9 段站位清单 + 空场 114819#122 净空核对结果，仅对 2026-10-08 时的房间布局成立。
- `sidequests/human_detectors/det07_capture_map.py` 等未入库代码无测试看护，重开前需先在解耦环境复核。
- 若日后做整帧端到端人检（绕过 ROI 判读），DET-01..06 协议与 DET-07 草案仍是最近的可复用起点 —— 这是保留而非删除它们的唯一理由。

## 四、本次改动文件

- `docs/sidequests/DET07_PLAN.md` / `DET07_ACCEPTANCE.md` / `DET07_CAPTURE_DESIGN.md`：标题改为归档关闭口径 + 头注归档声明（其余全文未动）。
- `docs/sidequests/REVIEW.md`：归档表新增 DET-01..07 行。
- 本文件新建。无代码、配置、冻结资产变动；无 commit 之外的入库动作。
