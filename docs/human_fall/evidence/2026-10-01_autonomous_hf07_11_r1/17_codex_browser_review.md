# Codex实际浏览器复审

2026-10-01 06:55–07:06，IAB访问板上8090预览，8765 foxglove_bridge。
URL带/hf07_verify/与/hf07_verify/points，为合成80点输入；非真人验证。

- 连接10.0–10.2Hz，丢帧0，只订阅指定点云；原设备IMU约226–227Hz。
- release接受：unselected，位置/距离清空，基线idle；发现未选目标预测行仍显示实测，Codex修为未选目标。
- 点候选select接受：t0002 locked，基线idle(target_changed)。
- capture_baseline：pending接受后3s ready接受，状态upright；标定ground-only-f6e0227005dfec91，未声称物理标定。
- 初次手动断开发现页面旧upright/valid/可用不消失。Codex修复连接回调清上下文/能力/状态与每500ms静默超时检查。
- 刷新部署后连接恢复upright；手动断开实际变unknown/unknown，位置/距离/基线/预测清空，请求通道不可用，候选清空；截图16_codex_disconnected.jpg。随后补顶部频率/到达时刻清--，最终部署再检查。

独立回归177/177、节点组合5/5、时序18/18、网页纯协议12/12，13–15日志保留。JS语法检查通过。ROS source/devel/install与实际请求链由02/03/09等板上证据覆盖。
拖框手势未实际自动化（当前浏览器API未提供拖拽），仅几何投影/相交逻辑测试和实际候选按钮链验证；不可写成实测拖框通过。
真实安装、地面、IMU和人工跌倒标签未验收，confirmed/融合保持禁用。
