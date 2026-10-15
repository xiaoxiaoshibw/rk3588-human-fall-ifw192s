# OpenCode 只读收尾复核（V3）— 结论：**PLAN_PASS**

## 一、N1–N4 闭环

- **N1（PR07c 分支/分母）→ 已关闭**：V3 `L122` 明确“Python 八动作固定 NOT_EVALUATED；JS/S8 仅在 GT 绑定有效且对应评分域存在非零 FURNITURE 标签分母时可评……缺负例标签或分母 0 的会话 NOT_EVALUATED，禁止作为 0 或安全 PASS”。与 `score_background_ab.py:34-40,55`（FURNITURE 标签仅非-094333 会话可得）及 `FINAL_REPORT:69-70`（S8 已标非人 0）一致。
- **N2（PR07b 基线臂具名）→ 已关闭**：V3 `L121` 把基线固定为 `2026-10-14_hf_real_close_data_bg_r1` 的 **C_V2_DIAGNOSTIC**，A_P/B_FROZEN 仅旁列消融、不得选优替换。
- **N3（80 帧双重角色）→ 已关闭**：V3 `L56` 新增“80 帧同时属于 1966 帧完整回归，必须分别列‘回归总表’和‘上下文留出子表’，不累计为额外独立样本”。
- **N4（4/8 会话无泛化）→ 已关闭**：V3 `L56` 新增“只覆盖 8 会话中的 4 段，不能支撑跨人/跨场景泛化”。

## 二、C_V2_DIAGNOSTIC 基线与 GT-free largest XYZ cluster 核对（对 `score_background_ab.py`）

V3 `L121` 描述的基线配置与源码逐项吻合：
- 臂名 `C_V2_DIAGNOSTIC`：`score_background_ab.py:22` 三臂之一；`background_ab.js:47` 定义为 `extract_foreground_fused(c.buf,keys,causal)`（冻结参考 B 键 + 因果在线图）。
- “原 −0.25m 域”：`background_ab.js:70` `ground_keep_below_m=-.25`（三臂共用诊断域）。
- “原两段源/参考”：S8 = `cap_20261010_180557`↔`175227`（`score_background_ab.py:15,76`）。
- “GT-free largest XYZ cluster 评分配置”：`score_background_ab.py:47-49`——`core.cluster(p[ids],cfg)` 后 `max(groups,key=len)`；`:48` 注释“GT-free largest cluster diagnostic；do not call this production target selector”，`:65` summary `selector:'largest XYZ cluster, same cfg all arms'`。三臂共用同一选择器，故“与同一源域/选簇基线比较”成立。

核对结论：基线与选择器描述**准确无歧义**，与源码一致。

## 三、剩余限制（非阻断，仅记录）

- CONTEXT_HOLDOUT 为同数据内上下文留出（4/8 会话），非独立新数据；计划已自述，PR11 泛化 BLOCKED 覆盖。
- PR07b/PR07c 的 JS/S8 仅部分标签、无完整身份 GT；完整纯度仍 UNKNOWN/BLOCKED。
- 跨仓依赖 `D:/Code/radar/.../20261014-low-pose-r01` 在目标仓之外，本轮已确认存在（含 background.npz/background.json/manifest.json 与八个 registration），实施时须按计划 `L50` 落 SHA。
- 纯文档瑕疵：§7 `L135` 仍写“作者修正文档另存 v2”（版本已到 v3），建议后续随文改为“另存下一版本”，不影响计划有效性。

## 四、边界

PR01–PR10、PR07a/b/c 全部 **NOT_RUN**；PR11/PR12 **BLOCKED**。技能 `C:/Users/30680/.codex/skills/ponytail/SKILL.md` 已于上一轮成功读取，本轮不重读。本裁决仅为计划批准：**不构成实现授权，不改 NOT_RUN/BLOCKED，生产晋级 BLOCKED**。