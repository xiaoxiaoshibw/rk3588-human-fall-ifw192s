# HC-JOINT-LOCAL-01 R1 回传

- 用户授权：总控制台USB和雷达同时录制，数据直接本机，不放3588。
- Codex唯一writer；2026-10-13；SUBMITTED，独审NOT_RUN，未ACCEPTED。
- 唯一验收：[v1](../evidence/2026-10-13_hc_joint_local_r1/ACCEPTANCE_V1.md)。逐项与限制：[报告](../evidence/2026-10-13_hc_joint_local_r1/REPORT.md)。
- 起始分支master、HEAD 026e06303f60ed1bbe4ddc4d037836db68da6d27；console_gui/html/tests/README起时已有用户修改。新增块与文件按报告列出，未恢复旧Git版本。首读关键源码SHA记录在SOURCE_SHA.json。
- ponytail实际读取C:/Users/30680/.codex/skills/ponytail/SKILL.md。
- 根因：原控制台仅相机预览/板端录制；现直接读两路既有流，在PC统一编排并流式落盘。不使用板端staging/下载流程。
- 新增本机录制服务/页/测试；控制台实例端口、退出收尾、EXE/ZIP入口保持既有快捷方式目标。
- 26项自验通过；真实自动/手动两段、现有回放列表读取、冻结启动/浏览器验证。设备短录制PASS，时空标定/动作/长时/同步准确度NOT_RUN或NOT_EVALUATED。
- 真实链路已发现雷达设备跨度与接收跨度差异，详情LIVE_CHECK.json；保存原时钟与原消息，不伪造相机曝光时间或跨模态GT。
- 保持板端服务/配置/驱动/模型/GT/旧证据/旧会话，不提交推送。样本与源码/发布包SHA见SOURCE_SHA.json与RELEASE_CHECK.json。

## R2 用户真实超时返工（2026-10-13）

- 用户两次失败反馈授权修复；用户已关闭总控制台以更新EXE。Codex唯一writer，SUBMITTED未ACCEPTED，独审NOT_RUN。
- [唯一R2 v1](../evidence/2026-10-13_hc_joint_local_r2/ACCEPTANCE_V1.md)、[诊断/逐项报告](../evidence/2026-10-13_hc_joint_local_r2/REPORT.md)。
- 相机末帧后3秒超时，雷达仍在接收；板端maxsize4队列踢客户端但连接保持的机制与现象吻合，实际日志不可读，归因不冒称证实。
- 最小本机修复：相机传输有界重连、断段事件、明确错误来源、失败不吞文件写错误、元数据写完再发布终态。板端保持不变。
- 28项软件自验通过；真实30秒899相机/139雷达帧无超时，另手动停止通过。实际相机重连仅合成验证，独立保留本轮首个竞态失败。
- 雷达实际缺号126和时钟跨度差异保留，网络吞吐/完整性/精确同步未通过；本修复不宣称无丢帧。旧两段失败会话保留原状。
- 最终新EXE/ZIP、冻结启动与SHA在R2证据。技能路径C:/Users/30680/.codex/skills/ponytail/SKILL.md。无部署/服务重启/模型GT/commit/push。
