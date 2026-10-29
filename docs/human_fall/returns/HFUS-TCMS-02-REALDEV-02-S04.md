# HFUS-TCMS-02-REALDEV-02-S04 回传（尾段/近地诊断与 A-B-C-D）

## 本轮信息

- 工单 / 轮次 / 执行者 / 时间：HFUS-TCMS-02-REALDEV-02-S04 / r1 / 本会话 DSH agent（唯一实现 writer）/ 2026-10-17 22:2x–22:5x (+08:00)。
- 验收表路径 / 版本 / SHA：`docs/human_fall/evidence/2026-10-17_hfus_tcms_02_s04_r1/ACCEPTANCE_V1.md` v1（SHA 见 FINAL_SEAL）。
- 执行方式 / 模型：本机离线单会话、单一 writer；模型按环境声明 deepseek-flash，精确 ID 不可得，未切换。
- 状态：**SUBMITTED**；作者自验 H01–H08 PASS；正式独立复审 NOT_RUN。不改 S3 的 `GEOMETRY_VALIDATED_LOCAL`，不产出人体效果。
- 起始 branch/HEAD：`master` / `c9c4ee421cb0c8a3e4590b8f5730828b093c759a`；S3 基线 34,408 文件逐字节复核 0 差异（`PRESERVATION.json`），data 只读。
- ponytail 实际路径：`C:/Users/30680/.codex/skills/ponytail/SKILL.md`。
- 策略：RESEARCH（尾段/接触带根因）+ ENGINEERING（接触层标签、回放、浏览器）。

## 集中诊断与根因覆盖

| 缺陷/验收ID | 根因 | 受影响入口 | 修复位置 | 保留行为 |
|---|---|---|---|---|
| H02 接触层语义 | 首版把“近地”当过滤思路，会诱导删点/改匹配 | 接触带实现 | `CONTACT_DEFINITION.json` 明确 5 项 never | 只打标签与计数 |
| H03 分解公式 | 首版 `valid − bg − members − rejected` 把**生长并入的 bg 成员**重复相减，tail 出现非零余项 | 尾段/f430 分解、SUMMARY.watertight | `run.py::decompose` 改为集合级三重恒等式 | 首版保留为 `FAILED_RUN_V1/`；MAP_BUILDING 帧不适用并单列 `DECOMPOSITION_AUDIT.json` |
| H06 M0 指纹 | S4 自写协议字典的 version 标签不同 → 指纹不等 | 应用链 M0 重建 | 直接复用 r04 `r01_map_protocol` 原字典 | `RUN_FAIL2/` 保留 |
| H01 路径 | `FrozenMap(output)` 会自建 `output/map`，首版传入 `RUN/map` | M0 重建 | 传 `RUN` | `RUN_FAIL1/` 保留 |
| 浏览器 | 页面 `screenOf` 返回对象被当数组、`pickIndex` 在密集点云长搜索 | S4 浏览器检查 | 确定性索引 + 真实鼠标 + 分离约束 | 失败轮次保留在 `BROWSER/` 外的手工调试记录（`diag_click*.js` 在 r04b/r05 源码） |

## 实际变更

| 文件 | 用途 | 与用户差异 | SHA |
|---|---|---|---|
| `sidequests/hfus_tcms_02/realdev/r05/s4core.py` | S4 根、继承输入、排他写、r01/r04 复用 | 全新 | 见 FINAL_SEAL `source_code` |
| `…/r05/run.py` | 780 帧 C + A/B/D 窗口诊断、接触带、分解 | 全新 | 同上 |
| `…/r05/audit.py` | 分解恒等式适用域审计 | 全新 | 同上 |
| `…/r05/server.py`、`index.html`、`app.js`、`browser_check.js` | 只读诊断页面与真实 Edge 检查 | 全新 | 同上 |
| `…/r05/seal_s4.py`、`append_docs.py` | 封存与二进制 LF 追加 | 全新 | 同上 |
| `docs/human_fall/evidence/2026-10-17_hfus_tcms_02_s04_r1/**` | 协议/验收/分解/ABCD/浏览器/报告/封存 | 全新证据目录 | 见 MANIFEST |

## 逐条验收

| ID | 自验 | 关键事实 | 证据 |
|---|---|---|---|
| H01 | PASS | S3 transform/domain/M0 逐 SHA 重核；S4 无新平面；源双 SHA 不变 | `INPUT` 段见 `SUMMARY.json`、`PRESERVATION.json` |
| H02 | PASS | contact/near/clear 三段；5 项 never 全 false | `CONTACT_DEFINITION.json` |
| H03 | PASS | 745–779：35 帧、12 零候选，逐帧 seeds/rejected/contact 计数；窗口 35/35 配平 | `TAIL_DECOMPOSITION.json` |
| H04 | PASS | 420–449：30 帧全部有候选、30/30 配平 | `F430_DECOMPOSITION.json` |
| H05 | PASS | A/B/C/D 同帧同分母；A 尾段 0 次零候选 vs C 12 次 | `ABCD.json` |
| H06 | PASS | `changed=[]`；M0 指纹 `56fa2141…9553` 与 S3 一致 | `RUN/PARAMETER_DIFF.json`、`SUMMARY.map_matches_inherited=true` |
| H07 | PASS | 真实 Edge 5 帧：分带、分解、尾段原因、56 hex 单点分带、相机不变、无效行、版本内嵌 | `BROWSER/BROWSER_RESULTS.json` |
| H08 | PASS | 136.0 s / 1.17 GiB / 197 MiB；行守恒 38,298,918；封存与回传 | `PERFORMANCE.json`、`FINAL_SEAL.json` |

回归：`python -B -W error sidequests/hfus_tcms_02/realdev/r05/run.py` exit 0；`audit.py` exit 0；`browser_check.js` exit 0。

## 未闭合与限制

- **尾段贴地前景保留尚未实现**：本轮只给诊断与标签；实现需要预注册新变体（例如“贴地行必须高于 M0 观测包络才不算背景”），不得以调 tau/生成为手段。
- **身份/轨迹**：本轮无用户或用户委托的 AI 视觉复核，`f439 LOST` 既不能复现也不能否定；身份 BLOCKED。
- 人体效果/GT 指标 NOT_RUN（全 null）；地面身份/物理高度/独立 D 仍 BLOCKED。
- MAP_BUILDING 193 帧的分解恒等式不适用（r01 语义），已在 AUDIT 单列，不当作失败。
- S5 全段交付未派发。

## 交给 Codex 独立复审

- 验收表与变更：`ACCEPTANCE_V1.md`、`PROTOCOL_V1.json`、本回传、`REPORT.md`。
- 根因与失败保留：`FAILED_RUN_V1/`（重复相减）、`RUN_FAIL1/`、`RUN_FAIL2/`（指纹）、`DECOMPOSITION_AUDIT.json`。
- 源码与 SHA：`MANIFEST.json` `source_code`、`FINAL_SEAL.json`。
- 原始日志：`RUN/frames.jsonl`（780 行）、`RUN/frames/*.npz`、`BROWSER/browser_check.log` 与 5 张 PNG、`BROWSER/server.stdout`。
- 下一步：只读独立复审；S4 停写，不自动进入 S5 或骨架里程碑。
