# 实现前诊断

branch master / HEAD 3fc1338fc306444959433a41bdeaeefd705f58ec。原工作树与相关 tracked/untracked 文件见 00/01；原录制快照见 02。Codex 唯一 writer，已读 C:/Users/30680/.codex/skills/ponytail/SKILL.md。

根因：Handler._api_sessions 在 _board_get 返回后才扫描本地，panel.refresh_sessions 只请求这一端点，故不可达板端阻塞列表。冻结控制台把 DEST_ROOT 改成 cwd/captures/remote，桌面快捷方式 WorkingDirectory 实查为 pc_apps/console/dist，该处 remote 为空，仓根实际有会话。

最小修复：既有 /api/sessions 加 scope=local 分支（无 board 调用）；面板先请求本地、显示后再合并板端，GET 有超时，刷新有版本号防旧响应覆盖；console 冻结版从 exe 向上寻找仓根，独立移动版使用 exe 所在目录。保留原 sid 文件加载、远端合并、手动选择、同步和只读回放。

| 入口/转换 | 实际位置 | 预期与验收 |
|---|---|---|
| startup、打开、刷新 × 板端慢/离线 | refresh_sessions → scope=local → render_sessions | 本地先列，O1/O2 |
| 本地点击 × 远端仍 pending/失败 | render_sessions → load_by_sid → __load_session_sid | 本地加载不受板端影响，O2 |
| 刷新期间再次刷新 × 新/旧响应顺序交错 | refresh_sessions 请求代数 | 旧返回无副作用，O3 |
| 同一会话重新列出/板端恢复 | render_sessions 保留 selected_sid，server 原合并 | 不重复 sid，选中项保持，O3 |
| 空本地/损坏 meta/缺 bin | _local_sessions 既有行为 | 空列表正常、缺文件不列；不扩大格式契约，O1/O5 |
| 源码、exe 从任意 cwd 启动、独立移动 exe | _start_replay_server | 正确 DEST_ROOT，O4 |
| 全流程 | 原捕获前后快照、相关回归 | O5/O6 |

本轮不改变外参绑定、帧格式/点内容/算法，HF/GL caller mutation 和物理资格组合不适用。真实板端连接不作操作，D1 NOT_RUN。
