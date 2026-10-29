# pc_apps/range_fall — PC离线逐帧运行与回放

当前发行入口为 `python -B -W error pc_apps/range_fall/release.py --help`，版本0.1.0。使用明确声明的空场前缀，串起 W1/W2、特征与规则，支持全帧核对及源节奏动态页面。运行、打包与边界见 [RANGE_RELEASE_0_1.md](../../docs/RANGE_RELEASE_0_1.md) 和 [RANGE_RUNTIME.md](../../docs/RANGE_RUNTIME.md)。不自动采集、拟合、部署或更换生产默认。

以下为原126帧展示参照入口的说明；其整段非因果背景和地面拟合不能作为新逐帧运行时的因果验证。当前发行不调用该生成入口，仅复用其显示工具。

把一段 **联合录制会话**（`data/sessions/<sid>/`：`points.bin` + `meta.json` + `camera.mjpeg` +
`camera_frames.jsonl`）渲染成一个可直接双击打开的离线页面：

- 左：标定 192×256 距离图 → 场景点云，**绿点/绿框 = 被跟踪的单个目标**（W2 关联结果）；
- 右：与该雷达帧“最近接收时刻”的相机画面；
- 下：目标高度中位曲线、逐帧状态色条、跌倒嫌疑区间、时间轴与逐帧指标；
- 报警条在 `suspected` 帧变红并给原因码。

没有任何新检测算法：链路是既有 W1/W2/特征/状态机，见 `session_compare.py` 顶部注释。

## 运行

```bash
python -B pc_apps/range_fall/session_compare.py \
    --session data/sessions/cap_20261023_221125 \
    --out docs/evidence/2026-10-23_single_person_fall_compare
```

参数：`--limit N`（只跑前 N 帧，背景统计随之变化，仅调试）、`--title`、`--no-preview`。

产物（全部写在新目录，不覆盖）：

| 文件 | 内容 |
|---|---|
| `index.html` | 单页对比（内联样式/脚本，无 CDN、无 three.js） |
| `data/frames.js` | `window.FRAMES=[...]`，显示坐标（x 前向 / y 左 / z 上，厘米整数） |
| `camera/cNNN.jpg` | 从 `camera.mjpeg` 按 `camera_frames.jsonl` 切出的相机帧 |
| `FRAMES.jsonl` | 逐帧账本（不含显示采样点），机器可读 |
| `GROUND.json` | 本会话拟合的地面（带源 SHA 绑定，`physical_verified=false`） |
| `SUMMARY.json` | 源/地面/背景/跟踪/跌倒/相机配对/边界声明 |
| `PREVIEW.png` | 四个时刻的联络图（站立 / 过渡 / 报警 / 恢复） |

## 页面怎么看

- 绿色框是**实测点集的外框**，不是人体语义识别，也没有身份真值；
- 灰蓝点是场景（按高度着色），青点是传感器原点，地面网格 0.5 m；
- 拖动旋转、滚轮缩放、双击复位；`←/→` 逐帧、空格播放/暂停、点时间轴跳帧、`跳到报警`；
- 相机画面下方显示 `接收时刻 - 雷达帧时刻`，说明配对误差来源。

## 边界（页面与 SUMMARY 同时声明）

1. **背景非因果**：会话没有空场前缀，因此用整段逐射线 98 分位作背景。生产 W1 的契约是显式空场前缀，
   这里只是回放可视化，不进入效果结论。
2. **地面是本会话点云 RANSAC 拟合**（阈值 2 cm，最小二乘精修），`physical_verified=false`，
   不是标定或物理地面认证。
3. **相机与雷达无硬件同步、无外参**：按主机接收时刻取最近帧，所以不把点云投影到相机画面上。
4. **没有人工真值**：人体语义、跌倒真值、召回/误报、物理资格、板端性能一律 `UNKNOWN`；
   状态机的 `confirmed` 关闭，最高只到 `suspected`（跌倒嫌疑），不等于“确实摔倒”。

## 测试

```bash
python -B -W error -m unittest discover -s pc_apps/range_fall -p "test_*.py"
node test_page.js        # 在 pc_apps/range_fall 下运行
```

Python 侧覆盖：地面拟合（含天花板竞争）、背景分位与稀有单元、显示基正交/地面归零、体素采样确定性、
厘米量化、相机索引校验与最近帧、输出目录守卫，以及一次真实会话端到端（本机有该会话时运行）。
JS 侧用最小 DOM 桩验证：首帧绘制、报警变色与原因码、播放/键盘/跳转、无相机降级、无目标不崩溃、
拖拽缩放、时间轴点击。

## 后续可复用展示入口（2026-10-24）

用户指定本页布局为最终展示形态。新增 `replay_compare.py` / `replay_template.html`：可只重绘已保存样例，或消费已审计因果W2+规则账本，不调用拟合/背景/跟踪/状态更新。原生成器保留其独立离线实验用途。运行方式及本轮结果见 [RANGE_REPLAY_VIEW.md](../../docs/RANGE_REPLAY_VIEW.md)。

```powershell
python -B -W error -m unittest discover -s pc_apps/range_fall -p test_replay_compare.py
node pc_apps/range_fall/test_replay_page.js
```
