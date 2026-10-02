# T5 板端 WebUI 运维通道盘点（只读，2026-10-02)

## 1. open_webui.bat 逐行(共 4 行,无 chcp 65001)

- L1 `@echo off` — 关回显。
- L2 `rem` — 注释:打开雷达 WebUI,服务没起就先在板上拉起。
- L3 `curl -s -o NUL --max-time 2 http://192.168.3.125:8090 \|\| ssh wel@192.168.3.125 "docker exec -d slam-localization python3 -m http.server 8090 --directory /root/catkin_ws/webui"` — 先 2 秒探测板端 8090;失败则 SSH 进板,在 `slam-localization` 容器内后台起 python http.server 8090。
- L4 `start "" http://192.168.3.125:8090` — 默认浏览器打开页面。

凭据核对:`~/.ssh/config` 中 `Host ldiar-wel 192.168.3.125`(同一条目两个 pattern)→ HostName 192.168.3.125 / User wel / IdentityFile `~/.ssh/id_ed25519_ldiar_wel` / IdentitiesOnly。bat 里 `ssh wel@192.168.3.125` 的目标串 `192.168.3.125` 能命中该 Host 块的第二个 pattern,因此实际仍会用到同一把专用密钥,不会退化成密码登录;只是没写 alias 名 `ldiar-wel`。功能等价,无认证差异。（另有 `nano3` Host 同 IP 但 user=jetson,是遗留条目,不受影响。)

## 2. 三个页面的连接目标

- `webui/index_board_20261001.html` 存在;Foxglove WebSocket v1 客户端,默认 `ws://<location.hostname>:8765`(hostname 为空时回退 `192.168.3.125`)。
- `webui/human_fall/index.html` 同款:默认 `ws://<location.hostname>:8765`,回退 `192.168.3.125`,带自动重连。
- `webui/human_fall_preview/index.html` 与 human_fall 同构,同样默认 8765。
- 三页均无硬编码 http:// 数据地址;数据面全部走 8765,8090 仅静态托管。

## 3. 与板端既有部署的关系(hardware_inventory.md 既有事实)

- 板端(容器 `slam-localization`,network=host)已常驻 `python3 -m http.server 8090 --directory /root/catkin_ws/webui` 与 `/foxglove_bridge`(8765),由 systemd `lidar-stack.service` 自启拉起。
- bat 的兜底命令与既有部署指向同一容器、同一目录、同一端口:正常情形下 curl 探测直接成功,兜底分支不会执行;仅在 8090 进程死掉时才补拉,此时是"恢复"而非冲突。若 8090 被其他进程占用而 curl 又失败,补拉会因端口占用静默失败,`start` 依旧打开一个打不开的页面(无错误提示)。

## 4. 结论

- SSH 探测(`ssh -o BatchMode=yes -o ConnectTimeout=5 ldiar-wel echo OK`)2026-10-02 复核:port 22 Connection timed out,exit=255。与早间结果一致,**板端当前不可达,此通道 NOW BLOCKED**(8090/8765 同在板上,浏览器直连同样不可达)。
- 板端恢复后可用性:bat 本身逻辑可用,大概率直接走"已起服务→开浏览器"路径;SSH 认证与 ssh config 的 ldiar-wel 条目实际指向同一密钥,无凭据漂移风险。
- 风险点:(a) bat 明文写 IP/用户,config 若改 HostName 不同步;(b) 8090 被占用且 curl 失败时补拉静默失败、无报错;(c) bat 只保证 8090,不检查 8765 foxglove_bridge,页面能开但无数据时无提示。
- 最小改进建议(至多 3 条,不实施):
  1. `ssh wel@192.168.3.125` 改成 `ssh ldiar-wel`,凭据/地址单点维护。
  2. 兜底分支的 ssh 输出重定向到 `%TEMP%` 日志或 `-o BatchMode=yes`,失败时 echo 一句提示再 exit。
  3. 起服后追加一次 `curl --max-time 3` 复查 8765(或页面内置 bridge 未连横幅提示已够,此条可省)。

完成:T5
