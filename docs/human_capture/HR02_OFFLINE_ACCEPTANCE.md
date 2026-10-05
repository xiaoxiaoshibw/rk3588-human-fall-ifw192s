# HR-02 本地会话优先 / 验收 v1

2026-10-05 用户要求：连不上板子时使用本地会话。PC HR-02 支线，Codex 唯一 writer；不改变 HF/GL 工单、算法、板端或原录制。

| ID | 要求与可观察预期 | 检查 | 当前结果 |
|---|---|---|---|
| O1 | 打开面板/刷新，先列本地完整会话，不等待板端 | local-only HTTP 禁止 board 调用；panel 延迟远端检查 | PASS 作者自验 |
| O2 | 板端失败/一直无响应，本地列表仍可点击载入；提示离线，录制禁用 | panel 超时/拒绝检查；实际浏览器回放 | PASS 作者自验 |
| O3 | 板端恢复合并远端列表；重复刷新不会被旧请求覆盖，选中项保持 | panel 延迟响应、恢复、刷新检查 | PASS 作者自验 |
| O4 | 源码与仓内打包版使用仓根 captures/remote；桌面快捷方式不读 dist 空目录，独立移动版按 exe 目录找数据 | console 源码/冻结路径测试，打包 HTTP 检查 | PASS 作者自验 |
| O5 | 原 meta/bin 内容与时间不变；保留用户差异，driver/webui/算法无本轮改动 | 前后 SHA/mtime、范围差异 | PASS 作者自验 |
| O6 | 相关已有回放与控制台回归通过 | JS/Python 检查原始日志 | PASS 作者自验 |
| D1 | 真实板端断开/恢复 | 本轮不操作板端；mock 不代替设备结论 | NOT_RUN |

状态：SUBMITTED。证据：[本轮回传](returns/HR-02_OFFLINE.md)、[本轮目录](evidence/2026-10-05_hr02_offline_r1/)。独立外部复审未授权，本轮只报作者自验，不标 ACCEPTED。
