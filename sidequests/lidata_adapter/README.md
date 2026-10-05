# LI-DATA 适配支线（lidata_adapter）

归属：支线，对应 `docs/sidequests/T4_dataset_survey.md`（数据集调研可用性）的落地。**不属于主线 GL-xx 任何产物，不参与主线/支线推荐，独立存放。**

## 这是什么

把网络上的 "Blender+LiDAR 1000 poses" 合成数据集适配成 `fall_replay.py` 能读的 `.npz`，并渲染成可视化帧序列 PNG。数据集本体（`ML/LI-DATA/`）**不进 git**。

## 结论（诚实版）

- ✅ 转换器可用：936 条 pose 序列可逐帧导出，坐标映射 `ros_x=|XYZ|(真斜距) / ros_y=-X / ros_z=Z(上)`，CSV 的 `distance` 列带 +5 m 偏移弃用。
- ❌ **喂不进 HF-06 跌倒判定主链路**：虚拟雷达贴地（传感器 z≈0），而 HF 的 ground-relative 高度跌落模型要求 `offset_m>0`（高装俯视）。注入 `z=0` 地平面后状态机全程 `unknown`。这是几何配置差异，不是代码 bug。
- 因此本支线产出仅限：**可视化回放** 与 **坐标映射回归基准**。不能调 `perception.yaml`、不能作 GL-02 验收证据。

## 文件

| 文件 | 作用 |
|---|---|
| `tools/lidata_to_replay.py` | zip → `.npz` 转换器（惰性读 zip，处理乱序帧/变长帧/坏行） |
| `tools/render_lidata.py` | zip → 多帧侧视 PNG（按语义角色着色，palette 经 dataviz 校验） |
| `tests/test_lidata_to_replay.py` | 6 个单测，纯 stdlib+NumPy，不需真实数据集 |
| `../../docs/sidequests/lidata_pointcloud.png` | 渲染产物示例（fall vs no-fall 侧视） |

## 用到但改了主线的一处

`src/human_fall_detection/scripts/fall_replay.py::_load_frames` 增加了 ragged per-frame 云兼容（检测 object dtype 走 `allow_pickle` 分支），dense 路径不变、主线 306 测试保持 `OK`。这是转换产物能被 replay 消费所必需的最小改动。

## 跑法

```bash
# 转换一条序列
python sidequests/lidata_adapter/tools/lidata_to_replay.py \
  --zip "ML/LI-DATA/Dataset (Blender+LiDAR)1000poses.zip" \
  --pose "Dataset (Blender+LiDAR)1000poses/Fall Data 500 poses/50FallData_PoseSet_part2/Pose_021_arms_back_arms_front_bent_straight" \
  --output /tmp/pose021.npz

# 支线测试
python -B -W error -m unittest discover -s sidequests/lidata_adapter/tests -v
```
