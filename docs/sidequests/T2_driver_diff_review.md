# T2 驱动 diff 审查报告

审查对象：`src/inno_lidar_ros/src/source/publish_manager.cpp` 未提交工作区 diff（+68/-12）
归因工单：HF-02（时间对齐、IMU 语义与数据失效），R1/R2 两轮执行，R3 仅 C++ 未改
审查日期：2026-10-02

## 1. 逐 hunk 审查表

| hunk | 语义 | 与 HF-02 归因一致性 | 风险 |
|---|---|---|---|
| `+#include <cmath>` | 引入 `std::isfinite` | 一致（HF-02.md 第 40 行） | 无 |
| `deviceStampToRos` 新增（static） | 有限性/负值/超界检查，fraction×1e9 进位，ROS1/ROS2 秒上限分支 | 一致（HF-02.md 第 40、96 行 R5 闭合说明） | 无；防御性边界，对常见样本无可观察影响 |
| `toRosDeviceStatus` 调用 helper | DeviceStatus header stamp 统一走 `deviceStampToRos` | 一致（HF-02.md 第 40 行"三处转换"） | 无 |
| `POINT_TYPE_SOURCE` 拼写修复 `*iter_timestamp = point.timestamp;ros_msg` → 删去杂散 `ros_msg` | 用户原有修复，HF-02 保留 | 一致（HF-02.md 第 5、85 行） | 该分支不在板端编译路径（板上 POINT_TYPE=XYZI_TIME） |
| `toRosMsg(PointCloud2)` 调用 helper | 点云 header stamp 统一走 helper | 一致 | 无 |
| `toRosMsg(IMU)` 调用 helper | IMU header stamp 统一走 helper | 一致 | 无 |
| IMU `orientation_covariance` 清零后 `[0]=-1` | ROS 约定声明"不提供姿态" | 一致（HF-02.md 第 40 行） | 无；消费者已按 `-1` 判不可用 |

## 2. 哈希与 diff 一致性核验

| 项目 | 值 | 说明 |
|---|---|---|
| 当前工作区 sha256sum | `1b3d57939dca511874eb66b42fd5d57132ad95220f85224d1dd090ed3edcb787` | Windows 工作区实际字节哈希 |
| 当前工作区 git hash-object | `a49b835e235c902de8d139a737215f98cfca90695` | Git blob 哈希（与 diff index `a49b835` 一致） |
| HF-02.md R1 记录 sha256 | `b9c4e706fa80216bb9c0d8eded2f051c5448a0ffd64cb6acd7e90952dc69d394` | R1 完成时（2026-09-30 16:31） |
| HF-02.md R2 记录 sha256 | `1b3d57939dca511874eb66b42fd5d57132ad95220f85224d1dd090ed3edcb787` | R2 完成时（2026-09-30 晚） |
| R2 变更表记录 | `1b3d5793…b787` | 与当前 sha256sum 完全一致 |
| R3 未改动声明 | `publish_manager.cpp 仍 1b3d5793…b787，本轮未重建` | 确认 R3 未改 C++ |

**结论**：当前工作区文件与 HF-02 R2 最终态 sha256 完全一致。diff 从 R1 的 `59ef8d7` 演进到 R2 的 `a49b835` 是预期的返工结果，非异常。R1 的 `02_driver_diff.txt` 记录的是 R1 中间态，当前 diff 为 R2 叠加修改后的最终态。

## 3. 板端 SSH 探测

`ssh -o ConnectTimeout=5 -o BatchMode=yes ldiar-wel "echo OK"` → 连接超时（192.168.3.125:22），板端仍不可达。

## 4. 消费者对齐核验

| 消费者 | 位置 | 对齐情况 |
|---|---|---|
| `sensor_health.py::orientation_covariance_flags` | scripts/ | `values[0] == -1.0` → `not_provided` |
| `sensor_quality.py::orientation_report` | core/ | 复用上述，`not_provided` 时返回 `usable=False` |
| `sensor_quality.py` docstring | core/ | 明确 `covariance[0] == -1` 判不可用，不伪造四元数 |

驱动新行为与 HF 包消费语义完全一致。

## 5. 安全结论

| 话题 | 影响 | 结论 |
|---|---|---|
| `/innolidar_points` | header stamp 统一；frame_id 不变 | 兼容 |
| `/inno_imu` | stamp 统一；covariance[0] 全零→-1，符合 ROS 约定 | 更规范，兼容 |
| `/device_status` | stamp 统一 | 兼容 |

ROS1/ROS2 双分支：helper 内 `#if` 区分 uint32/int32 秒上限；Codex 已验证 ROS2 `3e9` 越界被拒；ROS2 全包 NOT_RUN。

性能：helper 仅在 header 处每帧一次，新增 `isfinite/floor/比较` 可忽略；covariance 循环 9 元素仅 IMU 帧执行。

## 6. 归档提案

### 建议 commit 批次

`publish_manager.cpp` 应与 HF-02 软件部分（`core/timebase.py`、`core/sensor_quality.py`、测试、回传、证据）同批或紧邻批次归档。

### commit message 建议

仓库惯例为短中文行动句。建议：

```
HF-02: 统一驱动时间戳转换并声明IMU姿态不可用
```

或更短：

```
修复驱动时间戳进位与IMU姿态声明
```

建议在 commit body 中注明归因：HF-02 工单、执行者 OpenCode DeepSeek v4.1 Flash、Codex 三轮审查 R1–R5 闭合（软件 PASS）、板上 ROS1 隔离构建 exit 0、48→67→72 项回归全通过。

### ROS2 构建未实测（NOT_RUN）注明建议

**需要在 commit body 中注明**。建议：`ROS2 全包构建未实测（NOT_RUN），仅类型级三变体边界检查通过。`

### `src/CMakeLists.txt` 处理建议

- 当前状态：Windows 下显示为 `M`（git 无法哈希 catkin 顶层软链接），实际未改动。
- 建议：归档时**不要包含 `src/CMakeLists.txt`**，使用 `git add -- <具体路径>` 精确添加。
- 若必须处理，可在 commit 前 `git update-index --skip-worktree src/CMakeLists.txt` 标记忽略。

## 7. 综合结论

当前未提交 diff 为 HF-02 R2 返工后的最终正确态，与工单记录完全一致。消费者语义对齐，性能无回归，ROS1/ROS2 双分支边界已闭合。建议按上述提案归档，并在 commit 中注明 HF-02 归因与 ROS2 NOT_RUN。

完成：T2
