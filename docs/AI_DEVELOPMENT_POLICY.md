# AI 开发规范（已并入项目工作流）

本文件已被 [PROJECT_WORKFLOW.md](PROJECT_WORKFLOW.md) 取代。原三策略（ENGINEERING / RESEARCH / CONSOLIDATION）、ponytail 记录、工单/验收/回传要求全部废止。原文归档在 `docs/archive/workflow_legacy_2026-10-18/AI_DEVELOPMENT_POLICY.md`。

仍然有效的只有两条：

1. **真实**：没有 ground truth / 独立验证，就不写准确率、召回率或“效果通过”；每个数字必须能指到证据文件；失败与 UNKNOWN 照实写。
2. **安全**：`PROJECT_WORKFLOW.md` §5 的红线（data/junction、Git、设备、模型）默认不动；用户明确要求才做。
