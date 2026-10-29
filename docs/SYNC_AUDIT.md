# 离线双路同步审计

`tools/sync_audit.py` 独立读取联合录制会话，只写新伴随 JSON。没有生产调用者，不连接设备，不改变控制台、W1/W2、演示页面、事件标签或原始会话。

无锚即可运行（仓库根目录）：

```powershell
python -B -W error tools/sync_audit.py --session data/sessions/<sid> --out docs/evidence/<new_run>/AUDIT.json
```

记录 meta、points、joint、相机索引、MJPEG 的字节数/SHA256及工具版本 SHA；缺文件保留为 INCOMPLETE。逐帧报告 bag/header/相机接收时钟的无效值、重复、回退和正间隔；相机索引全量核对字节边界、连续性及 JPEG 首尾标记，标记检查不等于图像完整解码。提取器自报丢帧/丢点单列，不能据间隔倒推出实际采样丢帧。

相机 `recv_unix_ns` 是主机接收时刻，bag 时间是另一条接收记录，header 又可能是未锚定设备时钟。工具不混合这些时钟推算物理同步；没有双路独立证据时偏移、延迟与物理误差保持 UNKNOWN。

可选 `--alignment <file.json>` 接受以下格式。下例全部为**合成说明值**，不得拿来补写旧会话：

```json
{
  "schema": "sync_alignment_v1",
  "convention": "lidar_s = video_s + offset_s",
  "lidar_clock": "explicit LiDAR clock and origin",
  "video_clock": "explicit video clock and origin",
  "adopted_offset_s": 10.0,
  "adoption_source": "fit anchor motion-1",
  "uncertainty_s": 0.1,
  "uncertainty_source": "frame bracketing on both streams",
  "anchors": [
    {"id": "a", "physical_event_id": "motion-1", "role": "fit", "lidar_s": 11.0, "video_s": 1.0, "lidar_source": "frame 1", "video_source": "frame 10"},
    {"id": "b", "physical_event_id": "motion-2", "role": "check", "lidar_s": 12.05, "video_s": 2.0, "lidar_source": "frame 2", "video_source": "frame 20"}
  ]
}
```

时间单位为秒，原始时间必须使用所声明的时钟/原点；`lidar_source`、`video_source` 指出可定位的双路证据。工具核对字段与绑定，不能认证提供的锚是否真的对应同一物理动作。

自动建议偏移只取 fit 锚的 `lidar_s-video_s` 中位数，不自动采用。采用偏移必须显式提供及说明来源；不确定度也需提供来源。每个锚保存原始双路时刻及 `lidar_s-video_s-adopted_offset_s` 残差，fit/check 分列，不将拟合锚的零残差当成独立误差测量。重复物理事件 ID、重复原始时间对拒绝。两个不同时刻的 check 锚才输出其跨度内的漂移 `(Δlidar/Δvideo)-1`；单锚或同视频时刻不推漂移，不推全段上限。

提供采用偏移、不确定度和独立检查锚时状态为 RECORDED，含义仅为记录齐全，**不是同步达标或人体效果通过**。检查残差超过声明不确定度会单独标明，不能隐藏。缺任一项保持 UNKNOWN。

后续重查使用新输出文件：

```powershell
python -B -W error tools/sync_audit.py --session data/sessions/<sid> --alignment <alignment.json> --previous <old_audit.json> --out docs/evidence/<new_run>/RECHECK.json
```

任一源文件、锚文件（含参考时钟/偏移/不确定度）或工具内容变动使旧审计 STALE，逐项列出变化；原审计不修改。运行期间输入发生变化则拒绝生成结果。输出禁止位于 session/data/captures 内，禁止覆盖已存在工件。旧 session 未提供锚时不回填猜测。

验证入口：`python -B -W error -m unittest discover -s tools -p test_sync_audit.py -v`。

与 W2 的同输入测量来源/既有规则旁路现已整合为独立 [RANGE_EXPERIMENTS.md](RANGE_EXPERIMENTS.md) 入口；本同步工具源码保持。联合入口另检查五源 alignment 绑定及整数纳秒时钟，不自动施加时间偏移。本地 Python 3.8.10/NumPy 1.17.4 下同步 11 项和联合 26 项运行时测试、386 帧 CLI 已通过；不是设备或物理同步通过。
