# 2026-10-08 五段新会话离线诊断（r1）

状态：**SUBMITTED（诊断完成），不宣告 W03/HR-RET-V2 ACCEPTED**。用户交付五段会话并确认：雷达、门、家具、支架均未移动；人体四段全程静立。

## 结果

五段自动配平均推荐 TLS；三帧独立留出全部通过现行配平门。新空场 cap_20261008_114819（29.44s / 285 帧）作参考。

| 会话 | sid 后六位 | inlier | XY 覆盖 | fit / holdout p50（cm） | gate |
|---|---|---:|---:|---:|---|
| 配准复测_C1_中央空处静立 | 114205 | 49.38% | 77.90% | 0.79 / 0.38 | WARN |
| 配准复测_C1_右桌前静立 | 114254 | 49.51% | 83.11% | 0.87 / 0.34 | WARN |
| 配准复测_C1_左隔板旁静立 | 114340 | 52.85% | 89.15% | 0.47 / 0.27 | PASS |
| 配准复测_C1_中央空处静立举左手 | 114422 | 50.88% | 79.82% | 1.18 / 0.64 | PASS |

两段 WARN 的唯一不通过项均为 inlier_ratio < 0.50（SPARSE_CORRESPONDENCE）。该比例是固定诊断调度中**裁剪后对应数 / 静态源点数**，不能解释成其余点全部配错；调度、匹配与 gate 门槛均未改动。

**质量 PASS 与 loader VALID 是两件事。** 本轮只调用固定算法与质量测量，不调用 publish/writeJob；未创建、重签或安装 registration artifact。新 pair 的生产 loader 仍应为 UNAVAILABLE，不具备启用条件。

## 人体区域与链路

所有对照在同一已配准坐标系中运行，P 是用于隔离融合差异的在线-only 对照臂，不是浏览器未配准生产路径的实测。

圆柱半径固定 0.45m，z∈[0.10,2.30]，圆心由新数据中三帧残留点云定位；它是空间代理，**不是逐点人体 GT**。保留率是各臂点数 p50 / 原区域点数 p50。WARN pair 只跑 P/REF 诊断，V2/UNION 留 BLOCKED。

| sid | P 区域保留 | REF 区域保留 | V2 区域保留 | V2 粗几何候选帧 | V2 有确认轨道帧 |
|---|---:|---:|---:|---:|---:|
| 114205 | 0.30% | 100.00% | BLOCKED | BLOCKED | BLOCKED |
| 114254 | 0.16% | 99.97% | BLOCKED | BLOCKED | BLOCKED |
| 114340 | 0.43% | 91.96% | 91.92% | 281/281 | 230/281 |
| 114422 | 0.34% | 100.00% | 100.00% | 195/195 | 0/195 |

- 隔板旁：V2 区域保留 91.92%，低于 95% 区域目标；相对 P/UNION 的 0.43% 已恢复大部分区域点，281 帧都有粗几何候选，230 帧有确认轨道。参考臂自身仅 91.96%，损失主要发生在参考匹配，非融合新增删除。中间帧参考删除 185 点，全部集中在 Y=0.23–0.36m 的圆柱家具侧边缘（与主立人体结构分开）；可能是混入区域的家具点，需人工 GT，不能直接称为人体损失 8%。cleanup 在 5 帧各删 1 个区域点，身份同样未标注。

- 举左手：V2 区域保留 100%，195 帧都有粗几何候选，但确认轨道 0。联合判定为 NON_HUMAN 183 帧 / HUMAN_CANDIDATE 9 帧 / CONFIRMED_HUMAN 3 帧，未形成 3/5 确认。中间帧 spread_cv=0.104，被旧证据规则 SOLID_UNIFORM 判为均匀体；这是分类/确认问题，不是前景点被吞。

- 中央普通静立与右桌前：REF 区域保留 100% / 99.97%，而在线-only 臂仅 0.30% / 0.16%；V2 因 gate WARN 不跑。纯 REF 下中央普通静立也未确认，右桌前 268/271 帧确认，说明姿态/形状证据门仍有独立局限。

- 新空场 identity-reference V2 函数层检查：0 candidate 帧 / 0 confirmed 帧。此项不证明跨会话生产链已经可用。

## 家具窗诊断

固定两个空间窗（不是人工标注桌面）：X=[0.8,3.5], Y=[0.45,1.8], Z=[0.65,1.30]；X=[1.8,3.5], Y=[−1.8,−1.05], Z=[0.65,1.30]。分别抽第 0、中间、最后帧。三维欧氏最近距离对比 occ≥0.5 的参考体素形心，搜索上限 0.60m；本轮所有窗内点均找到邻居。

| sid | 正 Y 家具窗距离 p90（cm） | 正 Y 参考删除率 | 负 Y 家具窗距离 p90（cm） | 负 Y 参考删除率 |
|---|---:|---:|---:|---:|
| 114205 | 16.1–17.6 | 71.3–78.4% | 7.3–7.5 | 99.8–100.0% |
| 114254 | 12.1–13.7 | 83.6–89.5% | 10.0–10.9 | 91.7–92.4% |
| 114340 | 9.9–10.0 | 94.7–95.3% | 7.3–7.4 | 99.9–100.0% |
| 114422 | 9.6–9.7 | 95.3–95.6% | 7.6–7.7 | 99.9–100.0% |

PASS 两段的抽样家具窗 p90 约 7–10cm，参考删除约 95–100%；WARN 两段正 Y 窗尾部仍约 12–18cm。global point-to-plane p50 小于 1.2cm 不等于桌区全点三维距离 <12cm；本轮也没有物理测量或全桌面 GT，不能宣布桌子整体合格。

## 边界、验收与证据

- 唯一验收表仍为 R3.7 06_test_matrix.md v1 / HRRETV2_ACCEPTANCE.md v1；SHA 与本轮逐 ID PASS/FAIL/NOT_RUN/BLOCKED 状态见 acceptance_status.json。新数据人体验收受 GT 缺口阻塞；不覆盖历史验收表或历史证据，不改变 W03 REWORK_REQUIRED。
- 命令：python -B -W error level_sessions.py；node --max-old-space-size=8192 diagnose_registration.js / retention_diagnostic.js / audit_regions.js；python -X utf8 -B -W error plot_preview.py / plot_region_audit.py；均 exit 0。所有输出为本目录独占新文件。
- 收尾完整性首轮 exit 1：把本轮已创建的 leveling.run.log（启动时空、运行后增长）误纳入保护旧文件。首轮日志 finalize.run.log 保留；修正为保护本轮目录之外的起始文件，最终 finalize_r2.run.log 为准；数据/算法未重跑或改变。
- 五套回归：human_pipe_lib 38/0；registration 23 个 PASS ID（T37-20 未跑）；human_replay_lib 45；panel O1/O5；human_detect_lib 11/0，均 exit 0。T38/T39 原 gold/shadow/生产集成本轮 NOT_RUN，不能被这些数字替代。
- 名义配平参数 26°/0°/1.14m 仅复用已有工作台输入，非本次安装角或坐标原点高度的物理核验；TLS 自动拟合结果亦不作外参核验。
- 原始 captures 与生产文件保持只读；branch/HEAD/全 git tracked+untracked SHA 基线见 00_baseline.json，忽略的本轮原始会话由 meta/bin SHA 额外绑定。前缀完整性见 integrity.json。未 commit/push/deploy/capture/调阈值/改算法/重签/开启旗标。
- ponytail 实读：C:/Users/30680/.codex/skills/ponytail/SKILL.md；matplotlib 实读：C:/Users/30680/.codex/skills/scientific-toolkit-skill/references/scientific-skills/matplotlib/SKILL.md。
- 本轮新工具共 7 个小脚本，复用原 L.run_job、fixedICP、measure、PL 函数；配平派生数据仅位于 evidence/leveling，不注册到 captures/leveled。

![点云对照](pointcloud_preview.png)

![圆柱边缘点审计](region_audit.png)

后续可评审两个独立事项：为质量 PASS 的两对生成并安装新的绑定 artifact；人工标注隔板旁区域边缘及审查静立/举臂形状判定。两段 WARN 仍需对应集/质量契约层的设计评审，不能靠本轮诊断自行降低门槛。
