# HC-04 return — 板端控制网页

工单：../../tickets/HC-04.md · 日期 2026-10-02 · URL http://192.168.3.125:8090/human_capture/

## 交付物

```
webui/human_capture/
  index.html            # 页面骨架 + 样式
  capture.js            # UI 层（fetch/poll/DOM）
  capture_lib.js        # 可测纯函数（UMD，node 可跑）
  capture_lib.test.js   # node 测试，28 断言
docs/human_capture/tickets/HC-04.md
```

部署：已通过 `docker cp` 落到 `/root/catkin_ws/webui/human_capture/`，由既有 8090 python http.server 自动托管，无需改 8090 服务本体。

## 验收逐条

| ID | 结论 | 证据 |
|----|------|------|
| W1 加载 | **PASS** | `curl http://192.168.3.125:8090/human_capture/{index.html,capture.js,capture_lib.js}` 均 200，size 匹配 |
| W2 状态栏 | **PASS(代码级)** | `pollStatus` 1s 轮询 /api/v1/status，把 ros/disk/sessions_total/recording 渲染到 header；服务端 `ros:"up"` 时 UI 显示绿点"在线"（代码逻辑断言覆盖在 lib 测试里，浏览器实际显示需用户亲验） |
| W3 录制控制台 | **PASS(代码级)** | `startRecord` POST → 禁用按钮+重拉；`stopRecord` 同理；录制中渲染红色脉冲徽章+elapsed 表+session_id；停止后轮询转 extracting→ready 状态变化 |
| W4 会话列表 | **PASS(代码级)** | 按 created_iso 倒序，8 列字段对得上 store 的 SessionMeta；空态显示"暂无会话" |
| W5 触发下载 | **PASS** | 手工 `curl -X PATCH`（同 UI 代码同款调用）→ 板端 sessions.json `download_requested:true` 已写，state 保持 ready，UI 显示"已请求"（重新渲染时会从 dl_req 切到已请求态） |
| W6 容错 | **PASS(代码级)** | `fetchJson` 失败路径把 `recErr/sessErr` 显示到 UI；`serverUp=false` 时状态栏红点+禁用 start 按钮；CORS 已预检 204 通过（8090 fetch → 8766） |
| W7 node 测试 | **PASS** | `node capture_lib.test.js` → **28 passed, 0 failed**，覆盖 fmtBytes/fmtDuration/fmtElapsed/stateBadgeHtml/sortSessionsDesc/canRequestDownload/elapsedSec |

## 主要设计落点（票里没明说的）

- **不嵌 3D 点云视图**：8090 旧页本身就是实时预览（已有 Three.js 渲染），新页只放"↗ 实时预览(8090)"链接，避免维护两份 ws 订阅代码。你按一下链接就在新标签看实时效果。
- **轮询策略**：status 1s / sessions 2s / current 仅 recording 时 1s。按钮点击后 1.5s 冷却避免重复 POST。
- **跨端口 CORS**：capture_server.py 已开 `Access-Control-Allow-Origin:*`，加 OPTIONS 预检 204 支持（HC-01 起就有）。
- **elapsed 走表**：本地 `Date.parse(created_iso) → now()` 计算，即便 1s 轮询中间空隙，表也连续走。
- **lib/UI 分离**：capture_lib.js 是纯函数（UMD），node 可以 require 跑测试；capture.js 是 DOM 层。和 human_fall_preview/human_fall_lib 同构。

## 已知边界（HC-04 v2）

- W2/W3/W4/W6 的"浏览器里真的长啥样"无法 curl 实测，需要你打开 `http://192.168.3.125:8090/human_capture/` 亲眼确认。
- 不嵌实时 3D；如果你想在一个页面里既看 3D 又按按钮，需要 v2 把 index.html 的 three.js 那套也搬过来（~500 行），目前 ROI 不高。
- 不做"删除会话"按钮——后端有 DELETE /sessions/{id}，故意没暴露到 UI，防误删。
- 不做会话过滤/搜索；会话 ≤ 20 时不需要。

## 浏览器手动验证 checklist（给你）

打开 http://192.168.3.125:8090/human_capture/：
- [ ] 顶栏 ROS=在线、服务=在线、盘余 ≈ 20.4 GB、会话数=N
- [ ] 按"● 开始录制" → 红色脉冲徽章 + elapsed 表走 + session_id 显示
- [ ] 再按"■ 停止" → 徽章变"抽取中"，~5s 内变"就绪"，下面会话列表多一行
- [ ] 找到 ready 的行，按"请求下载" → 该列变"已请求"（实际下载要等 HR-01）
- [ ] 链接"↗ 实时预览(8090)"应打开旧页面（工作不变）
