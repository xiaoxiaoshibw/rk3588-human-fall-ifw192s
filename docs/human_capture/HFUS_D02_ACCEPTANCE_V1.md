# HFUS-D02 唯一开发验收表

v1 · 2026-10-11 · 当前用户离线实施授权，统一计划v2为依据。此表为开发验收，非规划验收。标准冻结，结果写return；工程/算法/人工/设备分开。

| ID | 层级/入口 | PASS预期与负例 | 初始状态 |
|---|---|---|---|
| D02-01 | 绑定与导出 | 真实帧/逐点raw及compact映射、meta/points/GT/帧/pointset SHA；最终使用D01冻结版本，禁止改原GT。 | NOT_RUN |
| D02-02 | 覆盖包 | S6 128/129/130/171/187/188及邻帧；S4/S8>=20秒连续窗；S5/S7低覆盖；S1首中末及变化点；S9双人真实成员/身份待审。 | NOT_RUN |
| D02-03 | 人工状态 | 自动建议DRAFT_UNREVIEWED/UNKNOWN；label source、独立复核状态、完整窗/有效范围/已知负例明确；无人工不签reviewed。 | NOT_RUN |
| D02-04 | 划分 | 同session仅一fold，crossfold exactduplicate=0；不复制负例、不泄漏未来帧，不把9会话称独立盲测。 | NOT_RUN |
| D02-05 | 复核入口 | 可复跑待审包/本地逐点复核页面或复用现有协议，输入绑定可校验，不修改原始GT。 | NOT_RUN |
| D02-06 | 语义资格 | train/val/test负例资格及S9身份须真实独立人工证据；缺证据BLOCKED，继续工程交付。 | NOT_RUN |
| D02-07 | 交接 | 所有权/命令/SHA/逐ID证据/失败/范围/ponytail与新return。 | NOT_RUN |
| D02-DEV | 设备/采集/部署 | 本轮无授权，保持NOT_RUN | NOT_RUN |
| D02-PHY | 物理/生产/独立新场景 | 缺充分证据与另行授权，保持BLOCKED | BLOCKED |

证据目录：`evidence/2026-10-11_hfus_d02_r1/`；回传：`returns/HFUS-D02.md`。每ID使用PASS/FAIL/NOT_RUN/BLOCKED并链接实证。
