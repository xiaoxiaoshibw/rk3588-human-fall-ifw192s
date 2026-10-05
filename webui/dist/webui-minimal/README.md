# IFW192S WebUI — 使用说明（最小包）

这是一个**纯静态网页**包，用来在浏览器里**实时看 InnoSense IFW192S 雷达的点云 / IMU / 设备状态**。不装软件、不依赖云端，对方只要有能连到板子的浏览器就行。

## 包内容

```
webui-minimal/
├── index_board_20261001.html   主页面（点云 + IMU + 设备状态 + 录制）
├── three.min.js
├── OrbitControls.js
├── teamview/
│   └── teamview.html           团队展示视图（跌倒检测演示用，可选）
└── README.md
```

---

## 一、板端要准备什么

页面只是渲染端，**数据来自板端跑着的 foxglove_bridge**。对方板子上需要：

1. 雷达驱动：`roslaunch inno_lidar_ros ros1_start.launch`
2. foxglove_bridge：监听 `8765` 端口，协议是 Foxglove WebSocket v1
   - 至少发布 `/innolidar_points`（sensor_msgs/PointCloud2）
   - 可选：`/inno_imu`、`/device_status`、`/human_fall/state`、`/human_fall/event`

只跑驱动没跑 bridge，页面打开会卡在「连接中…」。

---

## 二、把页面挂到 HTTP 服务器

任选一台能访问板子的机器（板子自己也行）：

```bash
cd webui-minimal
python3 -m http.server 8090
```

或任何静态服务器（nginx、IIS、caddy 都行），端口随意，下文以 `8090` 为例。

---

## 三、实时看雷达点云

浏览器打开（推荐 Chrome / Edge）：

```
http://<板子IP>:8090/index_board_20261001.html
```

打开后页面**自动尝试**连 `ws://<当前页面IP>:8765`。状态灯变绿即连上：

- 🟢 绿 = 已连接，正在收点云
- 🟡 黄 = 断线重连中
- 🔴 红 = 未连接

**bridge 不在同一台机器**：把顶栏那个 URL 输入框（默认填好了 `ws://…:8765`）改成实际的 bridge 地址，再点「连接」即可。

### 顶栏说明

| 控件 | 作用 |
|---|---|
| ● 状态灯 | 连接状态 |
| URL 输入框 + 连接按钮 | 改 bridge 地址用 |
| ● 录制 / ■ 停止 | 浏览器内存里攒 MCAP，停止时自动下载 `.mcap` 文件，**Foxglove 桌面版可直接打开回放**。点云 ~12 MB/s，单次建议 ≤2 分钟；连接断开会自动保存 |
| 点云 Hz | `/innolidar_points` 实测帧率 |
| 丢帧 | 浏览器侧丢的帧（bridge 发送队列反压导致，不影响板端） |
| 吞吐 | 收到的字节率 |
| IMU Hz | `/inno_imu` 频率 |

### 3D 视图

- **拖动左键** = 旋转；**滚轮** = 缩放；**右键拖** = 平移
- 顶部「点大小」滑杆调点的像素尺寸
- 「复位视角」回到默认机位
- 点颜色按 intensity 走彩虹色带

### 右侧侧栏

- **IMU 角速度 / 线加速度**：实时滚动曲线
- **设备状态**：收发温度、主板温度、异常标志（来自 `/device_status`）
- **事件 / bridge 状态消息**：连接日志和 bridge 发的状态消息

---

## 四、teamview（团队展示视图，可选）

```
http://<板子IP>:8090/teamview/teamview.html
```

针对跌倒检测场景做了简化：左侧 HUD 显示点云频率 / IMU / 温度 / 设备异常标志；场景里绿点是当前人员目标、黄点是跌倒事件标记。只读，不发任何指令。**没跑 `human_fall_detection` 节点时此页面只有点云可看**，人员/跌倒标记不会出现。

---

## 五、常见问题

**Q: 状态灯一直红 / 一直黄闪？**
A: 板子 8765 端口没通。依次检查：bridge 是否在跑（`rosnode list` 应有 `/foxglove_bridge`）→ 防火墙 → 是不是 NAT/容器端口没映射。

**Q: 点云不动 / 帧率 0？**
A: 看「丢帧」数。如果数字猛涨说明带宽不够（百兆链路 ~12MB/s 已经接近极限），属于 bridge 反压，不影响板端驱动。可以远离 Wi-Fi、用有线、或把页面关掉重连。

**Q: 录出来的 .mcap 在哪？**
A: 浏览器默认下载目录。停止时自动保存，名字形如 `inno-YYYYMMDD-HHMMSS.mcap`。

**Q: 能在手机上用吗？**
A: 主页面没做手机适配（侧栏会挤）；teamview 是触屏优化的，手机上推荐用它。

---

## 技术备注

- 所有页面**只读**：浏览器端没有任何按钮会写话题或改参数，雷达配置完全在板端
- 页面是纯 HTML + JS，没打包器没依赖安装，改完直接刷新即可
- 点云解码假定 PointCloud2 是 `XYZI float32`（`point_step >= 12`），其他点格式主页面不会显示
