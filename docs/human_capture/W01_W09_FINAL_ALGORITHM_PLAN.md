# W01–W09 最终算法架构计划书

> 登记：2026-10-06（Asia/Shanghai）。来源：用户当轮给出的计划书原文；本文件仅做 Markdown 排版，未改动算法意图。
>
> 状态：**PLAN_RECORDED（仅记录）**。不构成实施 / 采集 / 部署授权；**W03 未冻结**；开工以用户后续明确指令为准。
>
> 关联现状（事实引用）：W03-R2 动态背景链落地于 `pc_apps/human_replay/human_pipe_lib.js`；R2.1–R2.6 实测与「3D 清理破坏 XY bridge → cluster split → 新 green」拓扑回归见 `docs/human_capture/evidence/2026-10-06_hrw03_r1/README.md`。

## 一、最终算法架构

最终链路建议固定成：

```text
Raw LiDAR Point Cloud
        ↓
[W01] 输入与坐标规范
        ↓
[W02] 地面 / 配平
        ↓
[W03] 静态背景抑制 + 前景提取 + 聚类
        ↓
[W04] 人体 Track 点云标准化
        ↓
[W05] LiDAR 人体骨架
        ↓
[W06] 姿态识别
        ↓
[W07] 跌倒时序识别
        ↓
[W08] GT / Benchmark / ROC / PR / 参数标定
        ↓
[W09] WebUI / 工程化 / 最终验收
```

现在最重要的是：

**W03 还不能冻结**

因为目前：

- 墙
- 静态机器人摆件
- 固定结构

仍然会漏进前景，甚至产生人体框。

## 二、W03 重新拆分

### W03-R2：现有动态背景链

目前已经基本完成：

| 模块 | 状态 |
|---|---|
| workspace crop | 完成 |
| XYZ voxel background | 完成 |
| supported weak-static | 完成 |
| joint_status | 完成 |
| 3/5 temporal confirmation | 完成 |
| isolated cleanup | 已发现 topology regression |

所以先完成：

### W03-R2.6b Topology-Preserving Cleanup

解决：

```text
3D 清理点
    ↓
破坏 XY bridge
    ↓
cluster split
    ↓
新 green
```

验收核心：

- cleanup-induced split = 0
- cleanup-induced new green = 0

## 三、W03-R3：固定场景 Reference Static Map

这是现在最应该新增的一层。

你的场景是固定 LiDAR，而且：

- 墙不会动
- 机器人摆件不会动
- 大部分设备不会动

这种场景完全没必要只靠在线 occupancy 猜"这个是不是静态"。

应该建立：

**REFERENCE STATIC MAP**

### R3.1 无人环境基准采集

使用无人环境录制：

20~60 秒

包含：

- 墙
- 机器人摆件
- 桌柜
- 柱子
- 固定设备
- 地面残余

但不能有人。

多帧累计后构建：

`reference_static_voxels`

每个 voxel 至少保存：

- voxel key
- occupancy ratio
- mean centroid
- centroid covariance / jitter
- point density
- confidence

## 四、R3.2 静态背景匹配

运行时每个点先判断：

```text
current point
      ↓
reference static lookup
      ↓
是否命中高可信背景区域
```

不要要求坐标一模一样。

因为 LiDAR 点会有轻微抖动。

建议逻辑：

- exact voxel
- +
- limited neighboring voxel support

最终：

**REFERENCE_STATIC**

匹配成功的点优先删除。

这样：

- 墙
- 机器人摆件
- 固定设备

应该在进入聚类之前就消失。

## 五、Reference Map 和在线背景模型不是二选一

最终背景逻辑：

```text
                   Reference Static Map
                          │
Raw cloud ────────────────┼────→ background
                          │
                   Online Static Model
```

即：

```text
background =
    reference_static
    OR
    online_static
```

Reference Static Map 负责：

- 墙
- 机器人摆件
- 固定环境

Online model 负责：

- 传感器噪声
- 轻微环境变化
- 偶发静态残余

两者职责不同。

## 六、R3.3 Reference Map 必须冻结

Reference Map 建好以后，不允许在线无限更新。

否则会发生：

```text
人站着不动
    ↓
逐渐被写入静态地图
    ↓
人消失
```

所以：

**Reference Static Map = calibration artifact**

一旦标定完成：

**LOCKED**

运行阶段只读。

如果场景发生实际变化：

- 移动柜子
- 移动机器人摆件
- 换房间
- LiDAR 重新安装

应该：

**重新标定**

而不是偷偷在线改 map。

## 七、R3.4 场景变化检测

虽然 Reference Map 冻结，但最好增加：

**scene mismatch diagnostics**

例如：

- reference miss ratio
- unexpected static region ratio

如果长期大量点与 Reference Map 不一致：

**SCENE_CHANGED**

WebUI 显示：

⚠ 静态环境与标定场景不一致
建议重新标定背景

但第一版只告警，不自动重建。

## 八、R3.5 墙体 / 静态结构诊断

还可以加入诊断性结构特征：

- planarity
- linearity
- vertical plane
- extent
- persistence

比如 PCA：

λ1 ≥ λ2 >> λ3

说明：

**高平面性**

这类区域可以标记：

**STATIC_PLANAR_STRUCTURE**

但：

不建议第一版直接"看到平面就删除"。

因为人体可能贴墙。

主背景抑制仍由：

**Reference Static Map**

完成。

## 九、W03 最终验收

在进入骨架以前，至少要求：

**空场**

- 墙 → 0 human candidate
- 机器人摆件 → 0 human candidate
- 固定设备 → 0 human candidate

最好做到：

**confirmed human track = 0**

**有人**

加入真人后：

- 墙 → background
- 机器人摆件 → background
- 人 → foreground

且：

**human cluster retained**

## 十、W04：人体 Track 点云标准化

W03 完成以后再进入。

输入：

- track_id
- cluster points
- ground plane
- timestamp

转换成：

**human local frame**

例如：

- XY：以人体质心为中心
- Z：以地面为 0

输出：

- normalized_points
- height
- width
- depth
- vertical_span
- horizontal_span
- centroid_height
- principal_axis
- body_axis

这是骨架输入。

## 十一、W05：LiDAR 骨架

第一版不要做 COCO 17 joints。

你的目标是跌倒检测，应该先做：

**5~7 个结构关键点**

建议：

- HEAD
- UPPER_TORSO
- CHEST
- PELVIS
- LEFT_LOWER
- RIGHT_LOWER

第一版几何算法：

```text
normalized human cloud
        ↓
按 Z 分层
        ↓
区域密度
        ↓
robust centroid
        ↓
局部 PCA
        ↓
人体主轴
        ↓
粗骨架节点
```

重点是：

- 稳定
- 可解释
- 允许 UNKNOWN

不是关节点越多越好。

## 十二、W05 骨架可信度

每个点：

- x
- y
- z
- valid
- confidence

例如：

- head.valid = true
- head.confidence = 0.92

如果没有证据：

valid = false

禁止硬猜。

## 十三、W05 时序骨架

独立建立：

**SkeletonTracker**

不要改原有 human Tracker。

处理：

- EMA
- velocity gate
- maximum jump
- confidence weighted smoothing
- missing handling

最终得到：

**stable skeleton**

## 十四、W06：姿态分类

第一版建议：

- UPRIGHT
- BEND
- CROUCH_OR_SIT
- LYING
- UNKNOWN

Walking 单独属于：

**motion_state**

不要和 pose 混在一起。

输入：

- head height
- pelvis height
- body axis angle
- torso angle
- vertical span
- horizontal span
- centroid height

先做：

**rule-based baseline**

然后才考虑：

- Random Forest
- XGBoost
- MLP

## 十五、W07：跌倒时序

最终不能：

**LYING = FALL**

要识别：

```text
正常站立
    ↓
快速下降
    ↓
人体主轴旋转
    ↓
头 / 骨盆高度快速下降
    ↓
水平跨度增大
    ↓
LYING
    ↓
持续
    ↓
FALL_CONFIRMED
```

建议状态机：

```text
NORMAL
    ↓
DESCENDING
    ↓
TRANSITION
    ↓
GROUND_POSTURE
    ↓
FALL_CONFIRMED
```

还要支持：

**RECOVERY**

## 十六、W08：最后才系统标定

从 W04 开始采真人数据。

但是 W08 才统一做：

- ROC
- PR
- Precision
- Recall
- F1
- Confusion Matrix
- False Alarm Rate
- Detection Latency

最终才系统调整：

- background occupancy
- static jitter
- human shape
- skeleton confidence
- pose thresholds
- fall velocity
- fall angle
- fall duration

## 十七、真正最终主线

```text
W03-R2.6b
Topology preserving cleanup
        ↓
W03-R3.1
Reference static map builder
        ↓
W03-R3.2
Reference matching
        ↓
W03-R3.3
Reference + online background fusion
        ↓
W03-R3.4
Scene-change diagnostics
        ↓
W03 FINAL VALIDATION
        ↓
FREEZE W03
        ↓
W04
Human normalization
        ↓
W05
Geometric skeleton
        ↓
Temporal skeleton
        ↓
W06
Pose
        ↓
W07
Fall state machine
        ↓
W08
GT / ROC / PR
        ↓
W09
Engineering
```

---

> 登记附记：本文件仅为用户计划书登记；未改生产代码、未采集数据、未启动 W03-R2.6b / W03-R3 实施。后续实施步按用户明确指令与仓库流程单独授权、单独记录证据。
