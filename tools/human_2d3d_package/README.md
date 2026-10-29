# 2D 距离图 → 3D 人体目标 · 算法包 1.0.0

本包只包含**算法**：从一帧 LiDAR 测量行出发，先建立 2D 距离图并做逐射线空场背景、
前景连通域，再把 2D 候选区域的**同源行号**提升为 3D 点，完成单目标跟踪、几何特征、
姿态旁路、区域骨架和身体部位假设。

不含：网页 / Qt / 录制 / ROS 节点 / 会话数据 / 模型权重 / 板端部署脚本 / 地面拟合。
纯 stdlib + NumPy，Python 3.8+，Windows 与 Linux 同一份代码。

> 语义诚实：本包输出的是**几何候选**，不是"这是人"的识别结果，也没有身份或跌倒真值。
> `confirmed` 在运行时被禁用，跌倒状态最高只到 `suspected`。合成 demo 只证明链路可运行，
> 不构成准确率、召回、误报或物理有效性的任何证据。

## 1. 快速开始

```powershell
cd <本包目录>
python -B -W error run.py check     # 校验 MANIFEST 全部 SHA + 运行环境
python -B -W error run.py demo      # 合成场景：空场前缀 → 合成人体轮廓 → 目标锁定
python -B -W error run.py test      # 包内单测（无外部数据）
```

`demo` 逐帧打印 JSON 小结；锁定失败时退出码为 2。加 `--body` 会额外输出身体部位假设。

已有 28 字节测量行（`.npy` 结构化数组，或裸 `.bin`，28 B/点）时：

```powershell
python -B -W error run.py run --packed f0000.npy f0001.npy ... --dt 0.1 --ground --out frames.json
```

前 N 帧必须是**调用方显式声明的空场**，`--prefix` 默认 50。

## 2. API

```python
import human_2d3d
from core.capture_input import ROW_DTYPE   # 28 字节行布局

algo = human_2d3d.Human2D3D(session='site-a', empty_prefix_frames=50, body_parts=True)
algo.install_ground(normal=(0, 0, 1), offset_m=0.0)   # 声明，不是拟合

for index, (rows, stamp) in enumerate(stream):        # rows: ROW_DTYPE 一维数组或 28B 字节
    result = algo.feed(rows, stamp, index)
    if result['target3d']['trackId']:
        print(result['target3d']['sourceRows'].size, result['fall']['state'])
```

- `Human2D3D(calibration_dir=None, *, session, frame_id, empty_prefix_frames, body_parts, detailed)`
- `feed(rows, stamp_s, frame_index)` → 结果字典（见 §4）；帧号必须从 0 开始且严格递增，
  时刻必须严格递增，否则抛 `ValueError`（换会话请新建实例，不做静默重绑）。
- `encode_points(xyz, ring=None, intensity=0, timestamp=0)` → 28 字节行。
  `ring=None` 时在整张角表上按 (方位, 仰角) 找最近方向；本机角表每条 ring 的方位跨度
  不同，所以不能用“仰角中位数”猜 ring。不在角表方向上的点仍按最近方向编码，但解码时会计入
  `rejected.unknown_direction_rows`，不会被补造到任何格子。
- `install_ground(normal, offset_m, frame_id=None)` / `clear_ground()`：地面是输入。
- `summary(result)` → 严格 JSON 安全的小结（不含点坐标与距离图）。

## 3. 输入契约

| 项 | 约定 |
|---|---|
| 点记录 | `core.capture_input.ROW_DTYPE`，28 B：`x,y,z`(f4) `intensity`(f4) `ring`(u2) `timestamp`(f4)，单位米 |
| `ring` | 标定表的行号；来自传感器时直接用 |
| 帧号 | 从 0 开始、严格递增；空场前缀必须是 0..N-1 |
| 时刻 | 设备源秒（无 UTC 标签），严格递增 |
| 角表 | 包内 `calibration/ifw192s_azimuth_192x256.csv` / `..._elevation_...csv`；换传感器传入自己的角表目录 |
| 地面 | 可选；`status='valid'`、单位法向、有限 offset、坐标 `RAW/<frame_id>` |

## 4. 输出契约（每帧一个字典）

| 键 | 内容 |
|---|---|
| `status` | `prefix_warmup` / `ready` / `background_invalidated` / `insufficient_valid_cells` / `background_requires_explicit_rebind` |
| `image2d.rangeM` / `valid` / `labels` | 192×256 距离图、有效格、连通域标签（-1 = 非前景） |
| `image2d.components[]` | `id, cells(2D 平铺索引), sourceRows, xyz, points, retained`；`xyz` 就是 2D→3D 提升结果 |
| `image2d.rejected` | 非有限 / 过近 / ring 越界 / 方向不在角表 / 重复回波的计数 |
| `target3d` | `trackId, sourceRows, xyz, pointCount, center/bbox, heightM, horizontalExtentM, axis, tentative` |
| `skeleton` | `reason, nodes{name:{xyz, sourceRows, supportCount, imageXY}}, edges`；区域骨架，不是解剖关节 |
| `bodyParts` | `method, parts[]`；每个部位 `state` 为 `visible` 或 `uncertain`，未支撑的部位点集为空 |
| `fall` | `state, reasonCodes, confirmedEnabled=false, posture{state, reason, durationSec}` |
| `tracks` | 本帧所有轨迹的 id / 状态 / 点数（含未选中） |
| `timings` | 各阶段耗时（毫秒，本机测量，不等于端到端延迟） |

## 5. 重要口径

1. **2D→3D 不是投影反推。** 3D 点集来自 2D 连通域中每个格子记录的**原始测量行号**，
   因此是同一测量的来源行提升；不插值、不补点、不跨帧补关节。
2. **背景必须显式声明。** 空场前缀建立逐射线中位/MAD 背景；未知射线不冒充前景也不冒充空场。
   前缀不连续、换源、换角表都会进入 `background_requires_explicit_rebind`，需新建实例。
3. **地面是输入。** `install_ground` 只是把调用方声明的平面绑定进特征计算，
   不做拟合、不做物理认证；没有地面时高度与姿态为 `UNKNOWN`，低姿态判断不可用。
4. **部位是假设。** `body_branches` 用可见轮廓的拓扑分支给出头/躯干/四肢候选，
   切分点是观测弧长比例，不命名为解剖肘/膝；`1/2` 是帧内编号，不是左右。
5. **没有模型。** 全链路是标定角表 + 逐射线背景 + 连通域 + 几何，没有训练、没有权重。
6. **性能口径。** `timings` 是本机单帧算法耗时；板端 ARM、端到端显示延迟、真实场景
   准确率/召回率一律 `UNKNOWN`。

## 6. 文件与来源

```
Human2D3D-1.0.0/
  run.py cli.py human_2d3d.py synthetic.py   入口 / 命令行 / 唯一 API / 合成场景
  core/            原样复制的算法模块（含 __init__.py 的 scripts 路径引导）
  scripts/         sensor_health.py（core 的纯函数依赖，非 ROS 运行）
  calibration/     IFW192S 192×256 方位/仰角角表
  body_branches.py 2D 距离图身体部位拓扑分支（原样复制）
  tests/           无外部数据的自检
  ALGORITHM.md     逐阶段算法说明、参数与失效模式
  MANIFEST.json    每个文件的 SHA-256 + 来源路径 + 角表 SHA
```

`core/`、`body_branches.py`、`scripts/sensor_health.py` 与主仓库对应文件**逐字节相同**
（构建脚本复制，不手改），来源路径写在 `MANIFEST.json` 的 `sources` 里；
`MANIFEST.json` 的 `files` 覆盖包内其余全部文件，`run.py check` 会逐个校验。

## 7. 测试

```powershell
python -B -W error run.py test
# 等价于：python -B -W error -m unittest discover -s tests -v
```

覆盖：显式空场前缀与出生窗口、2D 连通域→3D 来源行一致性、标签/前景计数、原始字节输入、
非法行/时刻/帧号拒绝、前缀不连续拒绝、声明地面与非法平面、骨架/部位只使用锁定行、
两次相同输入完全一致、`encode_points` 回环、小结严格 JSON。