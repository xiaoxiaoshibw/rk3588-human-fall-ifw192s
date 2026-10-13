# 工单 HR-RET-V2：静立人保留 · 融合 v2 生产接入（能力旗标默认关闭）

- 状态：**increment 2 已交付（自验 PASS，2026-10-08）/ 待独立复审（V2-14）**；唯一验收表 v1：[HRRETV2_ACCEPTANCE.md](../HRRETV2_ACCEPTANCE.md)。
- 授权：用户 2026-10-08「授权」（承接 [HUMAN_RECOGNITION_REVIEW_AND_PLAN.md](../HUMAN_RECOGNITION_REVIEW_AND_PLAN.md) §4 的"生产接入"一项）。
- writer：OpenCode（opencode-go/deepseek-v4.1-flash，本会话）；ponytail 实读（opencode skill，base `C:\Users\30680\.config\opencode\skills\ponytail`，full）。
- 依据：[FUSION_PRIORITY_RULE_DRAFT.md](../FUSION_PRIORITY_RULE_DRAFT.md) §3.1/§4/§5；离线证据 [2026-10-08_fusion_v2_ab_r1](../evidence/2026-10-08_fusion_v2_ab_r1/README.md)（11/11 PASS）。

## 范围

- **做**：
  - increment 1（已交付）：`human_pipe_lib.js` 新增**融合删除能力函数** `extract_foreground_fused`（默认不被任何现有路径调用）+ 单测；P 路径行为不变。
  - increment 2（已交付）：消费侧**能力旗标**（默认关闭；只有 VALID artifact 才走 v2 分支，其余保持 P）；加载路径与浏览器/节点行为验证；行为 digest 回归。
- **不做**：不改 P 路径语义、不改 0.65/0.85 等阈值、不改聚类/资格/跟踪/Fall、不接板端、不动驱动/网络；W03 自身验收状态不变。
- **前置说明**：三段新会话配准为 DEGRADED（inlier 0.46）、旧对 artifact 为 STALE（代码绑定）——按既有 loader 状态机处理（DEGRADED 仅诊断）；正式**启用**（旗标打开）以验收表与后续评审为准。（2026-10-08 inc2 实测复核：四个现存 artifact 均已因代码绑定漂移为 `STALE(REFMAP_DRIFT, METHOD_STALE)`——现状即"不启用 v2"；重新激活须重签 artifact，另行授权。）

## 交付物

- 代码 diff（human_pipe_lib.js + human_pipe_lib.test.js）；
- 单测日志（`evidence/2026-10-08_hrretv2_r1/lib_tests.log`）；
- 验收表逐条自验；
- 独立复审（非本 writer，待 increment 2 完成后安排）。

### increment 2（2026-10-08 交付，自验 PASS）

- 代码：`human_pipe_lib.js`（`pipeline_frame` 可选 `ctx.fusion`，缺省/`refkeys=null` ⇒ P 逐位不变）+ `registration.js`（`fusionKeys` 门：默认关；仅 VALID 启用；其余 fail-closed）+ 两测试文件（V2-11a/b）。
- 证据：[evidence/2026-10-08_hrretv2_r2](../evidence/2026-10-08_hrretv2_r2/README.md)——套件全绿（38/38、registration 全 PASS、45/45、panel、11/11）、
  行为 digest 回归（D1–D5 全 PASS；真实 artifact 全 STALE → 不启用 v2）、浏览器/节点行为验证（7/7 复刻对账）、空场 V2-07（0 candidate / 0 confirmed）。
- 未做：V2-14 独立复审（非本 writer，待安排）；未 commit。
