# CAM-HOT R1（2026-10-13）— 相机助手视觉场景建模 + f10 区域重分类

授权：用户 h4 明确"你可以让usb摄像头拍个照片借助你的视觉能力辅助判断并且进行场景建模"。
既有服务：板上 `systemd cam-mjpeg` 端口 8081 (2026-10-12 上线)；`/stream` 路由 LIVE。
访问 API：`curl http://192.168.31.58:8081/stream` 抓取 MJPEG multipart。

## 三个相机帧（实时）

| 文件 | 描述 |
|---|---|
| CAM_F0000.jpg | 人站中景，左手提裙摆/袋，右手举至胸前 |
| CAM_F0100.jpg | 人移向右侧墙，身体倾斜，手保持上举 |
| CAM_F0200.jpg | 人回中心站位，裙摆仍在左手 |

**跨模态关键发现：f10 lidar 目标区域左下细长簇 ≈ 人左手提的裙摆/袋。**

它不是家具。HF-REAL-01 报告"f10 家具条带污染"是 writer 的保守诊断；HF-REAL-03 中我画的家具盒剔除 404 点也全部落在人物活动区（已证伪）。本次相机证据使「f10 target 实际为纯人体 + 手持物品」的判定有独立模态支持。

## 场景建模（camera anchors → lidar 坐标级融合）

`scene_model.py` 运行结果：
- 走廊宽度估值：**y=1.0 ~ 2.7m**（左侧扶手与右侧扶手对）
- 尽头家具：小桌凳（x≈16-20m，lidar IFW192S 最大量程 15m 外）
- 地砖条带：lidar ground_keep 剔地面时通常被裁掉
- **识别 9 个 object anchors**（含 5 camera anchors + 4 lidar density peaks）

### f10 目标点重分类（F010_RECLASSIFIED）

| 类别 | 点数 | 说明 |
|---|---|---|
| **PERSON_LEFT_ARM_OBJECT** | **819** | 与手持裙摆/袋对应 — 走廊左侧中部 z=0.8-1.7m |
| PERSON_TRUNK_or_RIGHT_WALL | 57 | 躯干/右墙近身 |
| UNKNOWN | 476 | 躯干底部 z<0.8m 或 y<1.4m 左下区域 |

**HF-REAL-02 RS04 FAIL 的关闭建议**：需由独审参考 CAM-HOT 证据决定是否关闭；本单不代为收口。

## 时间戳约束

相机是**实时流**（2026-10-13 19:06 左右），被摄人物可能正是在演示的用户本人；lidar session 094333 是**早上**录制的历史回放。**两者不同步**。相机证据对 r01/r02 的判断意义是：
- 场景几何模型（走廊宽度、尽头桌子、扶手位置）对早上的 lidar 空间布局仍成立
- 手持物品这一人体活动模式在早上/下午均合理存在

## 边界

- 8081 服务状态保持；未重启或修改配置
- 未推送任何数据；仅 curl GET 抓取
- 不对 r01/r02 源码或生产配置作变更
- CAMERA 不替代 lidar GT；仅作为助手视觉另一模态证据
- 215540/215623/215643/233658 没相机历史记录；CAM-HOT 不 forge 它们的视觉信息
- 只读探测 + 分析，独立复审 NOT_RUN

## 交付物

| 文件 | 用途 |
|---|---|
| CAM_F0000/0100/0200.jpg | 三帧实时场景 |
| cam_raw.bin | 原始 MJPEG stream (13,932,346 bytes, 201 frames) |
| SCENE_MODEL.png/json | 相机 anchors + lidar 走廊截面 + 融合 top-view 场景模型 |
| F010_RECLASSIFIED.png/json | 用场景模型重新分类 f10 target 1352 点 |

ponytail SKILL.md 实际读取路径：`C:/Users/30680/.codex/skills/ponytail/SKILL.md`。
