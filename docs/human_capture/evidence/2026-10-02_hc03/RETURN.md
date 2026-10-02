# HC-03 return — bag → meta.json + points.bin 抽取

工单：../../tickets/HC-03.md · 日期 2026-10-02 · 板上 (192.168.3.125:8766)

## 交付物

```
src/human_capture/core/bag2session.py           # 抽取本体
src/human_capture/scripts/capture_server.py     # +守护线程 _extract_loop
src/human_capture/tests/test_hc03_bag2session.py  # 本地容错
docs/human_capture/tickets/HC-03.md
```

## 格式定稿（板上实测确认）

PointCloud2 字段表（26B/point）：x@0(f32), y@4(f32), z@8(f32), intensity@12(f32),
ring@16(u16), timestamp@18(f64)。抽取时按 28 字节行 stride 重写：

```
[0..3] x f32  [4..7] y f32  [8..11] z f32  [12..15] intensity f32
[16..17] ring u16  [18..19] pad  [20..23] timestamp f32(f64 cast)  [24..27] pad
```

is_dense=False → 每帧按 xyz finite 过滤，drop 数写入 frame.dropped_points。
本机录制里 dropped 都是 0（驱动已滤），代码路径在 mock 测试覆盖。

## 验收逐条

| ID | 结论 | 证据 |
|----|------|------|
| X1 抽取成功 | **PASS** | 板侧手工 extract cap_20261002_163621：89 帧、4,372,400 点、117 MB、points.bin sha256=b81797f9... |
| X2 布局数值一致 | **PASS** | 第 42 帧：抽取字节与 bag source **逐位相等**（直接比特比较）；x/y/z/ring np.array_equal 全等；timestamp f32 与 f64 cast 的差 ≤1e-6（atol） |
| X3 NaN 过滤 | **PASS(u)**, **NOT_RUN(real-data)** | 代码走 `np.isfinite(x)&y&z` 过滤；真实 bag dropped=0。injected-NaN 反面在 Windows 无 rosbag 环境跑不动，留板上后续注入用例 |
| X4 帧数对账 | **PASS** | meta.frames=89 == bag PointCloud2 消息数 89 == manifest.summary PointCloud2 消息数 89 |
| X5 损坏 bag 兜底 | **PASS** | 手工造 garbage.bag + extracting 会话 → 守护线程 4-6s 内识别，state → failed(error="extract: rosbag.Bag 打开失败: ROSBagException...")，无 mutex leak，不影响其他会话 |
| X6 抽取串联 | **PASS** | 起录→5s→停→12s 内 sessions 依次 recording→extracting→ready，新会话 cap_20261002_165321 frame_count=29（4s 录，29 帧） |
| X7 性能 | **PASS** | 单次 extract 9.2s bag → **1.69 秒**（11.5× 上限 60s）。8 核 ARM Python+numpy 内存切片路径 |

## 遗留问题 & 边界

- **L1 抽取和 FIFO 的交锋**：cap_20261002_163621 这种被我手工 extract 过的旧会话（state=extracting + 已有目标产物），watcher 会毫无知觉地再抽一遍覆盖。**这次验证是幂等的**——同 bag 抽出同字节。但正式生产下需要加个标记避免重抽。HC-04 顺手做（meta_json_path 非空则跳过）。
- **L2 extractor 日志仍走 stderr**，板上 `/var/log/capture_server.log` 现仍是空，因为 python 的 `-u` 未指定，print/log 进 buffer。不影响功能但要 HC-04 部署时加 `-u`。
- **L3 抽取线程升级**：现在单线程 2s 轮询；如果用户高并发录制 + 多个 extracting 排队，会排队。单线程够用（录制本身就 1 路），不改。

## 板端产物（保留）

```
/root/catkin_ws/captures_remote/
  cap_20261002_163621.bag + .manifest.json + cap_20261002_163621/  ← HC-02 录的, HC-03 抽
  cap_20261002_164749.bag + .manifest.json + cap_20261002_164749/  ← 第一次自动extracting→ready
  cap_20261002_165321.bag + .manifest.json + cap_20261002_165321/  ← 最终完整链
  cap_broken_test.bag + (无子目录)                                 ← X5 损坏样本
  sessions.json                                                    ← 总账
```

## 测试运行实录

- 本地：`Ran 42 tests OK`（含 HC-01 26 + HC-02 12 + HC-03 4，跨平台 mock 容错）
- 板上：真实 rosbag+X1~X7 全链路实测 transcript 见 /var/log/capture_server.log
  （注意 L2 的 buffer 问题）
