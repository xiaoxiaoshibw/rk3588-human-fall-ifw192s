# human_capture 工单索引

| ID | 主题 | 状态 | 备注 |
|---|---|---|---|
| HC-01 | capture_server REST + 状态机 (42 测） | ✅ 板上 | commit 8a5a2b2 |
| HC-02 | 录制/FIFO/自动停 | ✅ 板上 | 调现成 record_session.py |
| HC-03 | bag→meta+bin (28B/点） | ✅ 板上 | numpy 切片 |
| HC-04 | 控制网页 8090 | ✅ 板上 | node 28 测 |
| HR-01 | fetch.py PC 拉会话 + sha256 校验 | ✅ PC | commit 2f5385a |
| HR-02 | 回放器 webui （本地 8901 服务） | ✅ PC | 28 lib 测试 |
| HR-03..05 | 剪辑/导航/人工 box 标注 | ✅ PC | commit cbd0be1 |
| HR-06 | PC PCL env 预热 (conda human_pcl) | ❌ **关闭**未实施 | 关 limb 连带关闭 |
| HR-07 | PC 四肢实时识别支线 （纯几何） | ❌ **关闭**永久 | v1..v6 + AI 判读均失败——判为「场景天花板」 |
| HR-08 | LiDAR ML 支线 (LI-DATA + IFW192S ML) | ❌ **关闭**永久 | 域内 98.6% 但跨域 100% fail ——跨域不可行 |
| HR-09 | IFW192S 自采姿势数据集 → 重训 RF v0′ | 🔄 **激活进行中** | 2026-10-09 用户授权开启 (12 段站立已配平); 本批只做 person/noperson 2 类, **return** 见 [returns/HR-09.md](../returns/HR-09.md); 另 5 类 (walk/sit/squat/lying/fall) 待补采 |

**2026-10-03 用户拍板**: limb+ml 支线永久关闭； 主线回归 GL-03/GL-04。

**2026-10-03 晚 用户再授权**: 仅写 HR-09 计划文档，**写完即封存**——不改代码、不录数、不开工。HR-08 全部代码/模型归档原样留仓，未来激活时零改动复用。


## 2026-10-08 新工单（仅计划登记）

| ID | 主题 | 状态 | 唯一验收表 |
|---|---|---|---|
| [HR-SEM-SHADOW](HR-SEM-SHADOW.md) | 静立/举臂，真实整簇全帧语义旁路及确认审计 | DRAFT_READY_FOR_DISPATCH；用户转发开工后执行离线范围 | [HR_SEM_SHADOW_ACCEPTANCE.md v1](../HR_SEM_SHADOW_ACCEPTANCE.md) |

不改变W03/HR-RET-V2历史判定，不解封HR-07/08/09，不授权生产切换、配准治理或部署采集。


## 2026-10-08 下一阶段骨架离线工单（仅制定）

| ID | 主题 | 状态 | 唯一验收表 |
|---|---|---|---|
| [HR-SKELETON-OFFLINE](HR-SKELETON-OFFLINE.md) | 人工确认人体簇上的标准化、5–7粗结构节点与独立时序可行性 | DRAFT_READY_FOR_DISPATCH；未开工 | [HR_SKELETON_OFFLINE_ACCEPTANCE.md v1](../HR_SKELETON_OFFLINE_ACCEPTANCE.md) |

正式W04/W05和旧HR-07是不同范围；不改变旧关闭决定、W03/SEM BLOCKED或生产边界。实施以新的明确用户开工授权为准。
