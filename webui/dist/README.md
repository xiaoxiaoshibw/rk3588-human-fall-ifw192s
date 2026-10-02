# IFW192S WebUI 最小部署包

给外部人员用来在自己板端网络里访问 InnoSense IFW192S 雷达 / 跌倒检测状态。

## 包内容

```
webui-minimal/
├── index_board_20261001.html   主入口（点云 / IMU / 设备状态总览）
├── three.min.js                主页面 Three.js 依赖
├── OrbitControls.js            主页面相机控制器
├── teamview/
│   └── teamview.html           团队视图（跌倒检测面向展示页，依赖上级两个 JS）
└── README.md                   本说明
```

## 前置要求（在板端）

对方需要先把数据面跑起来（这是雷达 SDK 自己的事情，不在本包内）：

1. 启动 ROS1 驱动：`roslaunch inno_lidar_ros ros1_start.launch`
2. 启动 foxglove_bridge（默认 8765 端口，Foxglove WebSocket v1 协议），需暴露这些话题：
   - `/innolidar_points` （sensor_msgs/PointCloud2）
   - `/inno_imu` （sensor_msgs/Imu，可选）
   - `/device_status` （inno_lidar_msg/DeviceStatus，可选）
   - `/human_fall/state`、`/human_fall/event`（仅 teamview 需要，可选）

`index_board_20261001.html` 只有 `/innolidar_points` 是硬需求，剩下都是缺了显示 `--`。

## 部署方式

直接把整个目录放到任意 HTTP 静态服务器下，例如：

```bash
# 在板上（包所在目录里）
python3 -m http.server 8090
```

然后浏览器打开：

- 主页面：`http://<板子IP>:8090/index_board_20261001.html`
- 团队视图：`http://<板子IP>:8090/teamview/teamview.html`

页面会默认尝试连 `ws://<当前页面所在 hostname>:8765`（即 foxglove_bridge 同主机）。如果 bridge 不在同一台机器，主页面顶栏有 URL 输入框，改成 `ws://<bridge主机>:8765` 再点「连接」即可。

## 备注

- 主页面的「录制」按钮是浏览器本地行为，不会影响板端。
- teamview 页面只渲染，不发任何控制命令；雷达配置 / 跌倒参数都在板端，本包完全只读。
- 若对方要看剪辑好的演示数据（无实雷达），不适用——那是 `webui/human_fall_preview/`，本包未包含。
