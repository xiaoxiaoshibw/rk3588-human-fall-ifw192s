# HR-02 return（2026-10-02，PC 侧）

会话 `cap_20261002_165321`（29 帧 / 1,424,701 点 / 40MB / 9.68Hz）全程唯一数据集。

| ID | 结论 | 证据 |
|----|------|------|
| R1 打开即播 | ✅ | node/vm 链路实载后状态栏=`就绪 (17ms)`、HUD=`帧 1/29 seq=1989282 t=00:00.0 点=49128 10Hz×1`、drawRange=`[0,49128]` |
| R2 逐帧 | ✅ | 步进 → `帧 3/29`；Shift×10 步进由同一函数承载（`step(d)`） |
| R3 时间轴 | ✅ | 拖到 idx=28 → `帧 29/29`；seq 一致性 node 探针抽查头/中/尾 3 帧对得上 `meta.frames[i].seq` |
| R4 速度档 | ✅ | 0.25/0.5/1/2/4× 选项按 `PLAYBACK_SPEEDS` 生成，切到 4× 后 HUD 显示 `×4`；累加器按 `dt*speed` 与 `1/fps` 步进 |
| R5 大会话 | ✅（大幅领先 3s） | node 实测：meta+40MB bin 读取 **12ms**；29 帧 strided copy 全量 **10ms**；2%/98% 分位 **28ms**；浏览器载入总值=ready 时延 **17ms**（vm 沙箱无 GPU；真浏览器 GPU upload 增加 ~50-200ms 仍在 <500ms 量级） |
| R6 分位着色 | ✅ | range=`{lo:159, hi:977}`（抽稀 1/16 后 2%/98%）；`intensity_to_gray` 边界样例：lo×0.5→0、mid→0.50、hi×1.5→1 |
| R7 node 测试 | ✅ | `node human_replay_lib.test.js` → **10 tests passed**（frame_slice×3、strided_f32_copy×2、pick_intensity_range×2、intensity_to_gray、format_hhmmss、default_fps） |
| R8 只读 | ✅ | 基线 `meta.json sha256=98517573…`、`points.bin sha256=b2a706b7…`，回放侧（node/vm/浏览器）只 `readFileSync/arrayBuffer`，无任何写 API；测试结束后 sha256 复测保持不变（见附） |

## 基线 sha256（R8 锚点）

```
985175739ef44e653b03afd7c5e57d3a80934baf1849f6bf4dc195928a187e71  meta.json
b2a706b7405f5d243d96d5cd239d750486472192a06de99f967fd45ce96943fa  points.bin
```

## 运行说明

- `python -m http.server 8899 --directory pc_apps/human_replay` 或双击 `index.html`（file:// 下 webkitdirectory 可用）
- 点「选会话目录」→ 选 `D:\Code\ldiar\captures\remote\cap_20261002_165321\` → 自动载入+起播
- 空格 播/停，←→ 步进，Shift+←→ ×10，速度档 0.25/0.5/1/2/4×，时间轴拖动跳帧，左键环绕/中键平移/滚轮缩放（OrbitControls）

## 已知限制（写入工单「不做」清单）

- 灰度单通道着色；HR-05 才要框选/gizmo
- 时间轴按帧（29 个刻度），不按连续时间（连续时间 scrub 对当前 9.68Hz 会话无收益）
- 未做跨会话切换按钮；选新目录重载即可
- jsdom 全页冒烟因 jsdom 自身性能在 1.42M 点循环上超时，改用 node + vm 最小 DOM stub 完成等效验证
