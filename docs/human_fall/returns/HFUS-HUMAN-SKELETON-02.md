# HFUS-HUMAN-SKELETON-02 回传（计划 A：只读复用 + 持续标定层）

## 本轮信息

- 工单 / 轮次 / 执行者 / 时间：HFUS-HUMAN-SKELETON-02 / r1 / 本机 DSH agent / 2026-10-18。
- 验收表：docs/human_fall/evidence/2026-10-18_hfus_human_skeleton_02_r1/ACCEPTANCE_V2.md；当前唯一表；V1 仅保留为运行前草稿。
- 协议：PROTOCOL_V1.json、V2.json、V3.json；最终运行使用 V3，SHA 见 INPUT_SHA.json 与 FINAL_SEAL.json。
- 执行方式：本机离线单会话；无外部模型切换；无网络/训练/设备/采集/部署。
- 状态：SUBMITTED；作者自验 A01-A08 PASS；Codex 正式独立复验 NOT_RUN；非 ACCEPTED。
- ponytail SKILL.md 实际读取路径：C:/Users/30680/.codex/skills/ponytail/SKILL.md；策略：CONSOLIDATION 加 RESEARCH。
- 起始 branch master；工作树起始已脏，未做 reset/checkout/clean/commit/push；未写 data/、旧证据、配置、模型、GT。
## 集中诊断与根因覆盖

| 缺陷/验收 ID | 根因 | 修复位置 | 保留行为 |
|---|---|---|---|
| 前序 SKELETON-01 BLOCKED | 自写几何在单视角稀疏点云上不可辨识 | 不在本工单重写；只读复用 r04 estimate | 旧 BLOCKED 证据不改、不降门 |
| A04 真实覆盖 | 107/490 ACTION 帧无 >=30 行候选 | 仅在有候选时 estimate；报告两个分母 | 不用预测/display 填帧 |
| RUN_R2 失败 | 120 样本窗口跨姿态污染 | 改为 20 样本最近窗 | 失败目录保留 |
| RUN_R3 失败 | 未限制绝对 std | 增加 std <=0.02 m，同时 rel std <=5% | 失败目录保留 |
| 浏览器首轮失败 | 固定第 0 个点常不在可视区 | 改为 visibleIndex 后 CDP 点击 | 首轮结果保留 |
| 关联首检失败 | 把候选全局歧义误判为静默赋值 | 按歧义轨迹不得测量检查 | 首检失败保留，R2 通过 |
## 实际变更

| 文件 | 本轮用途与修改 |
|---|---|
| sidequests/hfus_tcms_02/realdev/r08/calibrate.py | 唯一新算法：逐边在线均值/方差、20 样本窗、四态机、episodes 与漂移记录 |
| .../r08/wire.py | 只读 import S3 transform、r01 FrozenMap/Engine、r04 estimate/stabilize_display、association；逐帧候选、显式关联、测量、标定、记录 |
| .../r08/synthetic.py | 4 场景 paired truth 合成验收；生成器只读 |
| .../r08/server.py、index.html、app.js、browser_check.js | 本地 GET-only 浏览器、骨架/标定面板/点选、真实 Edge CDP 检查 |
| .../r08/verify.py | 输入 SHA、复用调用点、状态机、关联、A04 汇总 |
| docs/human_fall/evidence/2026-10-18_hfus_human_skeleton_02_r1/** | 协议/验收/运行/合成/浏览器/报告/封印 |

## 逐条验收

| ID | 状态 | 说明 |
|---|---|---|
| A01 输入与只读绑定 | PASS | INPUT_SHA.json；源双 SHA、transform/domain/M0/candidate 一致；只读模块前后不变；data 零写入 |
| A02 复用证据 | PASS | REUSE_CALLS.json；wire.py:526 estimate、:534 stabilize_display、:305 associate_tracks；无复制实现；display 仅显示 |
| A03 合成标定 | PASS | SYNTHETIC_CALIBRATION_R4.json；4/4 场景、47/47 边在容差内、46/47 CALIBRATED |
| A04 真实数据 | PASS | REAL_EVALUATION.json；317/383=82.77% 有候选 ACTION 帧 >=6 节点；7 条跨窗口稳定边，max 0.012365 m |
| A05 状态机 | PASS | STATE_MACHINE_CHECK.json；四态出现、163 drift reset、全部记录 |
| A06 关联 | PASS | ASSOCIATION_CHECK_R2.json；780/780 显式五字段、220 歧义帧、0 静默赋值 |
| A07 浏览器 | PASS | BROWSER/attempt2/BROWSER_RESULTS.json；Edg/155.0.4283.62、8 帧、56 hex、双 XYZ、相机不变 |
| A08 交付与边界 | PASS | PERFORMANCE/MANIFEST/FINAL_SEAL/回传/DOCUMENT_APPEND；预算通过；独立交接 |

## 未闭合与限制

- A04 全 ACTION 分母为 317/490=64.69%，107 帧无 >=30 行候选；没有用预测/display 值填充。A04 的 PASS 使用可测候选分母，且两个分母都在 REAL_EVALUATION.json 中报告。
- 区域节点不是解剖关节；左右身份、物理高度、人体身份、fall/effectiveness 全部 UNKNOWN/BLOCKED。
- 无人工 GT，不产出 purity、ID-switch、recall、effectiveness 或独立 D。
- 未训练/下载/HR09/设备/采集/部署/网络/Git 写；未改 data/、旧证据、配置、模型、GT。

## 交给 Codex 独立复审

- 当前验收表：ACCEPTANCE_V2.md；协议：PROTOCOL_V3.json；最终运行：RUN_R4/。
- 重点：A04 分母、A05 状态机、A06 歧义契约、A07 8 帧浏览器、失败保留、协议 v1 到 v3 是否只收紧不放宽。
- 入口：FINAL_SEAL.sha256 → FINAL_SEAL.json → MANIFEST.json → REPORT.md / HANDOFF.md。
