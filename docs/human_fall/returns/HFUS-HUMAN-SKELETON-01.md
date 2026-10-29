# HFUS-HUMAN-SKELETON-01 回传（人体 + 骨架持续标定：BLOCKED）

## 本轮信息

- 工单 / 轮次 / 执行者 / 时间：HFUS-HUMAN-SKELETON-01 / r1 / 本会话 DSH agent / 2026-10-17 23:0x–23:2x (+08:00)。
- 验收表：`docs/human_fall/evidence/2026-10-17_hfus_human_skeleton_r1/ACCEPTANCE_V1.md`（K01–K08）；协议 V1/V2 均已冻结。
- 执行方式 / 模型：本机离线单会话；模型按环境声明 deepseek-flash，未切换。
- 状态：**BLOCKED**（K03 合成门未通过）；不是 ACCEPTED，也不是通过。
- ponytail 实际路径：`C:/Users/30680/.codex/skills/ponytail/SKILL.md`；策略：RESEARCH（人体/骨架与在线标定）+ ENGINEERING（复用 r01/r04 链、回放）。
- 未改 data/、旧证据、冻结配置/模型/GT；无 Git 写；未训练、未下载、未激活 HR09、未做设备/采集/部署。

## 集中诊断与根因覆盖

| 尝试 | 方法 | 结果 | 保留 |
|---|---|---|---|
| v1 | 参数化 16 段模型 + 关节位置线性最小二乘（交替分配/求解），段长用"跨度 − 2r" | 0–1/16 容差内，未收敛 | `PILOT_R1.json` |
| v2 | 可辨识模型（9 段 + 2 宽），全局 `|v|` 躯干带 + 肢体两段折线 | 0/11，TRUNK 估 1.30–1.36 m（真值 0.66–0.72） | `PILOT_V2.json` |
| v3 | 0.03 m 栅格 + 膨胀 + Zhang-Suen 细化 + DT 脊线，图→人体拓扑分类 | 细化出梳状/格状图（约 100 个度≥3 节点），无法分类 | `STATUS.md` |
| v4 | 时序跟踪（上一帧姿态作初值）+ 每帧数据侧段长/宽度测量 + 在线标定状态机 | 最好 5/11 容差内，从未进入 CALIBRATED | `PILOT_V4.json` |

**根因（可辨识性，不是调参）**：单视角、每帧约 0.5–1.2k 点、无关节 GT、禁止训练/外部模型时，同肢两段的关节位置不可辨识，段长测量存在系统偏差；v4 的部分成功（躯干 6 mm、上臂 9–13 mm、宽度 16 mm）恰好集中在"可辨识"的量上。

## 实际变更

| 文件 | 用途 | SHA |
|---|---|---|
| `sidequests/hfus_tcms_02/realdev/r07/s5core.py` | 新工单根、继承输入、排他写 | 见 FINAL_SEAL |
| `…/body.py`、`body2.py` | v1/v2 合成人体（真值只在评分） | 同上 |
| `…/fit.py`、`chain.py` | v1 交替最小二乘；v2 可辨识测量 + 标定状态机 | 同上 |
| `…/skel.py`、`human.py` | v3 骨架化与人体拓扑分类 | 同上 |
| `…/track.py`、`synthetic_track.py` | v4 时序跟踪 + 在线标定 | 同上 |
| `docs/human_fall/evidence/2026-10-17_hfus_human_skeleton_r1/**` | 协议 v1/v2、验收、三次 pilot、STATUS、封存 | 见 MANIFEST |

## 逐条验收（本条为 BLOCKED 而非通过）

| ID | 状态 | 说明 |
|---|---|---|
| K01 输入绑定 | PASS | S3 transform/domain/M0/S4 逐 SHA 重核；旧模块只读 |
| K02 前景与参数 | PASS | 复用 r01 候选；新增测量只读；未改 DEFAULTS/tau/关联/TTL/生长 |
| K03 合成标定门 | **FAIL** | v4 最好 5/11（门槛 9/11），3/4 场景收敛未达成 |
| K04 真实数据 | NOT_RUN | K03 未通过，按协议不得进入真实数据阶段 |
| K05 状态机 | FAIL | 从未进入 CALIBRATED；DRIFT 复位逐次记录（v4：9–21 次） |
| K06 提取器不读真值 | PASS | 生成器与提取器分离，真值只在评分模块 |
| K07 浏览器 | NOT_RUN | 依赖 K03/K04 |
| K08 预算/封存/回传 | PASS（本条） | 本回传 + FINAL_SEAL（status=BLOCKED） |

## 未闭合与限制

- **K03 阻塞**：解除条件（任一，均需用户/物理输入）：①一帧人工或用户委托的 AI 种子；②关节标注/GT（哪怕少量）；③多视角或更高密度采集授权；④外部参数化人体模型或训练授权（当前禁止）。
- 真实数据精度 UNKNOWN；未做任何关节/物理高度/身份结论；未进浏览器阶段。
- 未降低验收门、未改写协议门；v1–v4 全部失败保留。

## 交给 Codex 独立复审

- 入口：`docs/human_fall/evidence/2026-10-17_hfus_human_skeleton_r1/STATUS.md`（含可辨识性分析）与 `PILOT_R1/V2/V4.json`。
- 复审重点：四条路线是否都被公平实现；门的严格度是否未被降低；阻塞结论是否成立（若复审认为仍有一条未试的可行纯几何路线，应指出并重新派发）。
- 下一步：等待用户选择解除条件；本项停写，不自动进入真实数据/浏览器阶段。
