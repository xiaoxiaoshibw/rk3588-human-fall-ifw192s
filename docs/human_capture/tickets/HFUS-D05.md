# HFUS-D05 工单：人体前景保留与 UNKNOWN/CLEANUP 重构

> 2026-10-11 用户连续实施授权，主控接管当日登记。不重复 D04 无效方向；直接实施/运行/测试/交付。
> **优先级：实际识别效果 > 可视化可验证性 > 性能优化 > 文档数量。**

## 范围（做）

1. 追踪 RAW→BG→UNKNOWN→CLEANUP→PROPOSAL→CLASSIFIER→TRACKER 逐点损失归因（先做、先于任何变体调参）。
2. 三条可替换算法并行实现并真跑九会话：
   - A UNKNOWN 自适应邻域重判决（预登记 0.3m / 0.6m）
   - B 人体候选感知 CLEANUP
   - C 时序前景恢复（须支持跳帧/倒放后状态重置，不跨会话污染）
3. 基线、A、B、C 及必要组合的对照结果（保留 RF/RFC 51D 基线可复现，作为 pinned 变体而非枷锁）。
4. D05 离线可视化 Demo（九会话切换/播放/步进/重置；原始点云 + D04 baseline + D05 新算法三窗同步；显示被删/被恢复/候选/最终识别；候选 ID/评分/每层点数；一键跳近/远/静/家具误检/失败帧；A/B/C 可切换同帧对比；保留 D04 Demo 不覆盖）。

## 边界（不做）

- 不动生产主链、不 commit/push、不部署板端、不采集。
- 不改 `background/`、`contracts/*`、`eval/instrument.js`；新代码只进 `sidequests/human_fusion_lab_next/d05/`。
- `captures/`、GT、模型、D01–D04 证据只读。
- S9（cap_20261010_180751）INVALID_BINDING → 不参与正式打分，只列探索行；人工未审核区域一律 UNKNOWN。
- 即使算法 FAIL 也要保留实际运行结果，不得包装成 PASS。

## 工作组织

- 主控（Claude Code）：接口/归因探针/评测/组合/Demo/回归/证据/return。
- Agent A/B/C：隔离工作区域，禁止并发覆盖同一文件；写码前必加载 ponytail skill 并在回传中记录使用路径。

## 验收表

版本化验收表：`docs/human_capture/evidence/2026-10-11_hfus_d05_r1/BASELINE_D05.md`（预登记，跑前冻结）。
结果判定：工程 / 算法 / GT 资格 / 生产接入 四项独立裁定，PASS/FAIL/NOT_RUN/BLOCKED 逐项对 ID 汇报；失败如实留账。

## 返回与证据

- 证据：`docs/human_capture/evidence/2026-10-11_hfus_d05_r1/`（不覆盖旧证据）。
- 回传：`docs/human_capture/returns/HFUS-D05.md`（追加式，不覆盖 D04）。
