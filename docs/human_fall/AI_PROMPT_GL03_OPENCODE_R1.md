# GL03 R1：实际点配平几何、消费者一致性与大候选证据

工作目录D:\Code\ldiar。用户2026-10-02“开始开发”授权本单及返工；指定模型opencode-go/deepseek-v4.1-flash。你是唯一生产写入者，Codex独立验收。GL02已经获审，不重做。只GL03，不GL04/部署/采集/联网/commit/push/reset，不触driver、Windows src/CMakeLists.txt、默认/geometry冻结资产/UI/原CSV/tgz/旧证据/physical/confirmed。

先完整阅读：AGENTS.md、WORKFLOW.md、GL03_ACCEPTANCE.md v1、tickets/GL-03_candidates_geometry.md、GEOMETRY_CONTRACT.md、INTERACTION_CONTRACT.md、GL00 r4/25_contract_extension_draft.json、RETURN_TEMPLATE.md、C:/Users/30680/.codex/skills/ponytail/SKILL.md。GL02状态只需读R7 CODEX_REVIEW摘要，不再注入全部历轮历史。当前源码按调用链分段查lidar_candidates._reference_block/build_snapshot→tracking.candidate_view→node_runtime._state_payload/_mask_unobservable/status_state与replay/features。

先集中诊断到evidence/2026-10-02_gl03_r1/00_diag.md：全表和每一矩阵行的已有覆盖/缺检查/失败，最小根因和保留行为；再最小实现。

已知：reference ragged中心形状/只变换两角；ground只是GDID没实际点框/中心；node没新字段且reference轨迹预测可能误当source。严格继承获审source/reference原义，ground逐实际candidate点min/max/median，不把旋转source median当ground median；bbox_ground_from=actual_points/unavailable。支持transform有/无/unknown、derived完整/无/损坏/from-frame或ground-parent错配，源索引经过滤/采样可回溯且caller不变。旧无derived摘要不破坏；新完整derived共享严格validator。node当前实测透传、prediction/release/不观测/版本切换绝不假当前ground actual geometry；尤其reference prediction要还原source坐标，仍保留既有reference优先追踪，不随意改tracker契约。

大候选：使用GL00 r1现有两CSV来源，archive全景sample是跨47帧XYZ池，ROI CSV仅有受限ROI的逐帧索引。不能称全景逐帧重放。保留原文件，只在新证据写探索性分析：配置/数据hash、成员/水平cell连接/疑似平面支持消融，缺全集/身份/实测地面则明确BLOCKED，不强开trusted、空场或物理flags。

分离：先有连接证据再改造。若做可信synthetic桥接软件原型，只允许最小、显式默认关闭且支持可信gate；地面点可不当连接边，但不能无条件删近地厚层导致脚/低卧/完全近地证据丢失。保留原点云、候选原索引与有限诊断；无法区分就保守fallback并记录。无可信支持/auto AABB/no derived/disabled必须旧行为。不要发明通用人体分割/新学习依赖。

允许修改lidar_candidates.py、必要node_runtime/pipeline/features/tracking共享消费者、相关测试、独立perception参数/几何兼容说明、新本轮证据/诊断工具和returns/GL-03.md。保持GL02校验/基线/缓存/ACK、选择/会话/源时间/新鲜度守卫。需动其他文件先把与已有条目关系写诊断，再按最小范围推进，不向用户发问。

Python3.8/NumPy1.17 API；Windows只跑纯函数。留至少一个能暴露原缺陷的有效回归。先针对完整矩阵，再fall全回归、GL02独立12方法+pending版本2方法、follow/UI静态等受影响证据。命令exit与日志写新目录，源码manifest含所有新增/未跟踪文件。未跑板端/物理不宣称PASS。

最后按RETURN_TEMPLATE追加“OpenCode GL03 R1”到returns/GL-03.md（没有则创建），逐ID/入口/状态、真实命令/exit、SHA、数据层级/限制报告SUBMITTED/BLOCKED；不能自判ACCEPTED。写完停止，让Codex直接读取复审。控制上下文：读必要片段，测试日志落盘只返回失败/摘要，不重复全量历史；接近120k先停止写入交Codex压缩，不硬顶200k重试。
