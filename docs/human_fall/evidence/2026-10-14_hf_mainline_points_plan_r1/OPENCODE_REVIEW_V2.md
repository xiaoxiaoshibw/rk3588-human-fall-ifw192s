# OpenCode 只读计划审核（V2）— 结论

## 0. 身份、技能与读取

- **实际模型/会话身份**：opencode CLI，运行时模型 `opencode-go/deepseek-v4.1-flash`（提供方/权重 UNKNOWN）。独立只读审核者；本轮未写任何文件、未运行命令/算法/测试/服务。
- **技能路径（本轮已成功读取）**：`C:/Users/30680/.codex/skills/ponytail/SKILL.md`（120 行，ponytail 最懒可用方案 ladder，默认 full）。首轮该路径被 external_directory 拒绝，本轮许可后读取成功；正文身份与计划自述一致。作为审核者我不适用 ponytail，仅记录。
- **本轮新增读取**：`docs/human_fall/HF_MAINLINE_POINT_RETENTION_PLAN_20261014_V2.md`（全文 148 行）、`docs/human_fall/evidence/2026-10-14_hf_mainline_points_plan_r1/CONTEXT_HOLDOUT_V2.json`（全文）、跨仓依赖目录 `D:/Code/radar/Plan/evidence/indoor-empty/20261014-low-pose-r01/`（glob 列出）、该目录 `background.json`、`manifest.json`、`REPORT.md`。
- **限制**：`manifest.json` 为单行超长文件，read 在第 2000 字符截断，**未能直接读到其 `reference` 字段**（仅由 REPORT.md、R3 报告、background.json 的独立 `source_sha256` 旁证）；未计算任何 SHA、未运行校验。

## 总体裁决：**PLAN_PASS**

V2 对首轮 P1/P2/P3 **逐条全部闭环**，且我在源码/跨仓证据上独立复核这些修订属实；未发现新的阻断性缺陷。剩余仅为不影响收口的 P3 澄清项。**本结论仅为计划批准，不构成实现授权、不改变 NOT_RUN/BLOCKED 状态。**

---

## 一、逐条闭环核对

### P1-1（PR07 跨数据集混用 + 家具 NOT_EVALUATED 矛盾）→ **已解决**
V2 §6 `L120/L121/L122` 拆为 PR07a（Python 几何门：32 空场 0 目标/0 新增事件 + 1934 帧无新目标缺失，不报身份精度）、PR07b（JS/S8 的 53 帧/57045 部分标签门，人体 foreground 与 selected 保留均不退化，094333 不适用）、PR07c（已绑定家具标签子项；无负例标签会话 `NOT_EVALUATED`，不作 0/安全，不阻断几何诊断但阻断完整纯度/安全/生产表述）。`L129` 明确“三者独立逐项报告，不汇成跨数据集 PASS、不拼分母”。跨数据集混用与“假零家具”矛盾均被拆解。**闭环成立。**

### P1-2（独立验证集未具名）→ **已解决，并已独立核验帧域**
V2 §2 `L33` + §4 `L56` 具名 CONTEXT_HOLDOUT 80 帧，落盘 `CONTEXT_HOLDOUT_V2.json`。我独立核验（对 `REPORT.md` 帧数表）其帧域均有效：
- 083218（231 帧）f40–59 ✓；083044（251）f80–99 ✓；082829（183）f40–59 ✓；082717（327）f220–239 ✓；合计 20×4=80，与 `total_scored_frames:80` 一致。
- 且与 §4 `L58` 的既有 R2 诊断帧（082623 f119/124/192/231/232、082717 f140/f263、082906 f94）**无重叠**，`excluded_diagnosis_context_frames` 也未挤占已列诊断帧。
- `L56` 明确“历史已见、严格不称独立新数据”，返工读取则标 REUSED_REGRESSION。**闭环成立。**

### P2-1（跨仓阻断爆炸半径）→ **已解决，并已独立核实依赖存在**
V2 §3 `L50`：依赖缺失/SHA 不符“阻断整条 Python 动作链（E0/E3/E4 及 1934 帧账本），不是单个小片段；JS E1/E2 在自身绑定有效时仍可独立诊断”，并把核对项扩为 background.npz/background.json/manifest.json/八个 registration。我核实该目录确实存在，含 `background.npz`、`background.json`、`manifest.json` 及全部八个 `cap_20261013_08xxxx_registration.json`，且 `cap_20261013_131958/` 存在；`background.json` `tolerance_m=0.054923896541511696`（=54.924mm，与 §5 `L88` 一致）、fit 33/cal 32/holdout 32、`never_updated_from_action:true`。**闭环成立。**

### P2-2（评分器耦合 HF-REAL-04/S1）→ **已解决**
V2 §3 `L43`：明确 score_background_ab.py “仅适用于 JS 的原两 sid/S1 输出，不能直接评分 action_output；动作链另在薄实验适配器中计算通用源行统计”。与 `score_background_ab.py:15/23-25/30` 的硬编码证据一致。**闭环成立。**

### P2-3（094333 无人体分母）→ **已解决**
V2 §4 `L60`：094333 标 `PROXY_ONLY_DIAGNOSTIC`，人体 GT 分母 0，只报旧 target proxy/几何变化。与 `FINAL_REPORT:73` 一致。**闭环成立。**

### P3-1（config 175227 vs 实际 131958）→ **已解决**
V2 §3 `L50` 说明 175227 为历史字段，实际 reference 由 manifest/background.json 决定、目前为 131958。旁证：`background.json.source_sha256.meta=ae72aea0…` 不等于八动作任一 meta，符合独立参考。**闭环成立（reference 字段本身因截断未直读，记为已旁证）。**

### P3-2（JS/Python 范围差异未列）→ **已解决**：V2 §5 `L88` 显式“JS 范围 0.35–25m；Python 单独保持 0.2–15m”。与 `human_pipe_lib.js:27-28`、`config.yaml:8-9` 一致。

### P3-3（E1 高度未拆 + 地板吸收）→ **已解决**：V2 §5 `L87` 改为“建图0.10/−0.25 × 提取0.10/−0.25 的 2×2 矩阵”，并写明降低建图下限会把更多地板纳入背景吸收、不预设更好。与 `human_pipe_lib.js:148-149,162,281` 一致。

### P3-4（E3 参考支撑对 background_removed 恒真）→ **已解决**：V2 §5 `L92` 明确“不是重复 dist≤tau”，改用参考 FIT 逐体素帧覆盖/局部厚度法向/CAL 距离分布，HOLDOUT 不参与，取不到标 MISSING。与 `actions.py:137`、`background.json` 一致。

---

## 二、新发现的必要修订（均为 P3 澄清，不阻断 PLAN_PASS）

- **N1（P3）PR07c 未标适用分支**：`L122` 只写“已绑定家具标签子项”，但八动作分支 `manifest.json` 全部 `human_identity_gt:"MISSING"`，绑定 FURNITURE 标签仅存在于 JS/S8（`gt_store/cap_20261010_180557/GT_V1.json`）。建议在 `L122` 标注“仅 JS/S8 可评；Python 分支固定 NOT_EVALUATED”，避免读者误以为 Python 有家具分母。
- **N2（P3）PR07b “对应旧基线”未指定臂**：`L121` 与哪一旧臂比较（A_P 因果 / B 冻结 / C v2）未定。建议具名基线臂，否则“不退化”口径可选。
- **N3（P3）80 帧双重角色**：这 80 帧既在 PR05 的 1966 帧主回归内，又是 PR07a 的验证子集。建议在 §4/§6 加一句“回归计量与验证报告角色分离、分别列示”，防止同一批帧被当作两次独立证据。
- **N4（可选）**：CONTEXT_HOLDOUT 仅取 8 会话中的 4 段，属同数据上下文留出，不支撑跨场景/跨人泛化——PR11 已 BLOCKED 覆盖，可一句话点明。

---

## 三、已核且无需修订项

- ponytail 路径本轮读取成功，计划“复用加载与聚类、不复制整 r01、薄适配器、不新建 r02 页面”（`L45,L48`）符合 ponytail ladder（复用优先、最小新码）；§7 的契约检查也符合“留下一个可跑检查”的要求。
- Python 域 −0.25（`config.yaml:10`）、JS 0.10（`human_pipe_lib.js:31`）、KS1 在 `background_ab.js:70` 三臂禁用——计划 §2 `L19` 表述属实。
- R3 边界（仅当前 FG、不救背景删除点）与 R3 报告一致。
- “数值配准≠物理资格”“拒绝采纳 C01 leveling 因果断言”（`L142`）与 leveling FINAL_REPORT 一致。
- 输出独占拒绝覆盖（`L46`）与 `actions.py:30` 的 `open(...,'x')` 一致；端口 8944 与现页一致。

---

## 四、实现 NOT_RUN 边界

- PR01–PR10、PR07a/b/c 全部 **NOT_RUN**；PR11（完整人体召回/家具纯度/解剖精度/泛化）、PR12（生产晋级/confirmed/设备部署/物理验收）**BLOCKED**。
- 设备/物理/部署/采集/训练/提交推送/GT/板端/网络驱动均 **未授权、NOT_RUN**。
- 本审核为**计划批准**：无权将任何工单标 ACCEPTED，无权批准生产晋级；V2 的 PLAN_PASS 不等于实现授权，实现需另行明确授权。