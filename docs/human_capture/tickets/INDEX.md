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
| HR-09 | IFW192S 自采姿势数据集 → 重训 RF v0′ | 📋 **已立案（封存）** | 同日复测证死跨域；唯一正路见工单；**不主动开工**，等用户现场录数后激活 |

**2026-10-03 用户拍板**: limb+ml 支线永久关闭； 主线回归 GL-03/GL-04。

**2026-10-03 晚 用户再授权**: 仅写 HR-09 计划文档，**写完即封存**——不改代码、不录数、不开工。HR-08 全部代码/模型归档原样留仓，未来激活时零改动复用。
