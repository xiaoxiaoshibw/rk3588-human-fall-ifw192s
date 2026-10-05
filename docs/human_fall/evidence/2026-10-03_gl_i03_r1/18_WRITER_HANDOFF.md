# GL-I03 R1用户调整writer/复审分工 / 2026-10-03

最新用户原话：“算法和代码你开发吧，交给opencode二次审核开发”。此为直接授权，覆盖本单历史“仅OpenCode生产writer、Codex不写源码”角色限制。当前无活动OpenCode进程，root/Codex接任唯一生产writer；角色交接由本文件与WORKFLOW最新覆盖登记。

本单范围仍为wrapper显式--constrained-config、新独立geometry_constrained_gli03_r1.yaml只0.05/8、新test_gli03_candidate_override.py三文件。既有00_diag/04设计门与GLI03_ACCEPTANCE v1沿用，既定数据/先验/冻结算法不因角色改变而自动扩权。先完成具体可复查实现/自验，再交OpenCode二审；其服务故障不阻断Codex授权内实现，不假称二审已经完成。

Codex实际完整读取ponytail技能源 C:/Users/30680/.codex/skills/ponytail/SKILL.md；理解load_config→resolve→fit→schema→exclusive输出链后按最小修改实现。所有原默认/emit/人工draft/frame gate/source/physical语义保持。

Codex自验和只读助手复核分别记名，不冒称本人实现的独立验收。OpenCode保持原指定Go Flash/defaultDB，派二审前≤1min无工具probe；失败立即记二审BLOCKED，不切modelDBauth、不改权限。审核第一阶段只读、报告既有K/P缺陷；如需代码返工，Codex已停写后显式交OpenCode成为单writer，再由Codex独审其修改。没有两writer并行，没有算法返工R2或新里程碑自动授权。

保留旧服务/空stdout/授权拒绝历史证据，不reset/checkout/clean/commit/push。HEAD/含untracked全树与冻结十SHA在本次写前/写后核对。外部human_limb用户差异保留。
