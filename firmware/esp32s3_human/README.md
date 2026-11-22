# ESP32-S3 无空场人体运动学与跌倒检测核心 (`esp32s3_human_core`)

`human_kinematic_v3` 包含纯 C++17 的 IFW192S 人体跟踪与运动学跌倒候选核心、用于 ESP32-S3 + W5500 的 ESP-IDF 固件，以及用于 RK3588 的 Protocol 2 实时看板。跟踪循环使用 `float32` 和预分配缓冲区。

## 设计要点

1. **无空场预热**。第 0 帧初始化背景与上一帧距离图。背景差分用于发现和生长点簇，帧间深度变化用于人体运动门槛。BFS 覆盖归属于最终关联的轨迹。未通过确认的短时假设过期后，稳定近距回波会逐步并入背景。
2. **免地面拟合**：仅需重力向上单位向量 `gravity_up`（来自 IFW192S 内置 IMU 或标称安装 pitch/roll），无需 25+3 帧空场地面拟合或绝对地面 offset；跌倒基于目标相对自身直立基线的头顶落差（P95 高度，128 桶 2 cm 直方图 $O(N)$ 计算，无排序）。
3. **运动学 + 体态三联跌倒状态机**：$\alpha$-$\beta$-$\gamma$ 滤波器平滑 10 Hz 头顶垂向速度/加速度，结合下落速度、加速度冲击（或慢倒兜底持续下坠）、身体坍塌（高度 $\le 0.55\text{ m}$ 且高宽比 $\le 0.55$）与持续低位保持（$\ge 1.2\text{ s}$），过滤弯腰与持续蹲姿。
4. **人体锁定与时效**。初次锁定要求直立高度 0.90–2.15 m、水平跨度 0.15–1.15 m、高宽比至少 1.05，并在 1.3 秒内有至少 3 次连续合格测量。还需有至少两帧支持的同向运动，净位移至少 0.11 m。高于传感器且紧贴扫描边缘的簇不参与首次锁定。已锁轨迹可用较小的连贯位移或可靠的头顶高度改变续期，距上次续期达到 25 秒时释放。低位或起身关联仍要求水平和深度一致。实测直立恢复结束疑似状态，疑似状态最多保留 12 秒。连续 1–2 帧缺测期间保留运动学历史与姿态状态，暂停累计低位证据。单次帧间隔超过 0.35 秒时切断旧轨。串口仅发布当前帧实测锁定，Web 显示固件 profile 和距上次续期的秒数，目标消失 20 秒后清理轨迹及曲线。
5. **ESP32-S3 内存预算**
   - `Workspace` 为 1,032,192 B（约 **0.98 MiB**）。`cur_range_mm` 与 `cell_flags` 优先放内部 SRAM，其余缓冲区放 PSRAM。
   - `HumanTracker` 对象约 5 KB，包含静态 8 条轨迹和每轨 20 帧的运动学环形缓冲

## 本机编译与验证

```powershell
New-Item -ItemType Directory -Force firmware/esp32s3_human/build | Out-Null
g++ -O3 -std=c++17 -Wall -Wextra -Werror firmware/esp32s3_human/human_tracker.cpp firmware/esp32s3_human/host_replay.cpp -o firmware/esp32s3_human/build/human_host.exe
python -B -W error -m unittest discover -s firmware/esp32s3_human -p "test_human_tracker.py" -v
python -B -W error -m unittest discover -s firmware/esp32s3_human/web -v
```

离线回放需要 NumPy 和 `data/sessions/` 中的本地录制。按 `run_sessions.py` 的 `DEFAULT_SESSIONS` 准备六段录制后运行：

```powershell
python -B -W error firmware/esp32s3_human/run_sessions.py --out-dir "$env:TEMP/human_s3_replay"
```

`SUMMARY.json` 包含实测锁定、主 ID 覆盖率、ID 切换、疑似首帧和起身区间的同轨恢复。使用 `--compare-dir` 指定同一组输入的历史回放目录可做逐段对照。`--bird-jsonl` 与 `--baseline-bird-jsonl` 可加入已有的双鸟逐帧结果。录制和机器验证产物保存在本地。

## 固件与看板

安装 ESP-IDF 5.5.3 后，从仓库根目录构建固件：

```sh
idf.py -C firmware/esp32s3_human/esp_idf -D IDF_TARGET=esp32s3 build
```

构建输出为 `firmware/esp32s3_human/esp_idf/build/esp32s3_human_fall.bin`。固件默认面向 16 MiB Flash、Octal PSRAM 的 ESP32-S3，W5500 的引脚和网络参数见 `esp_idf/main/w5500.hpp` 与 `esp_idf/main/main.cpp`。

在 RK3588 上用 Python 3.8+ 和 `pyserial` 运行看板。填入目标 S3 的串口设备和对应雷达的 SDK 几何标定文件（786,448 B）：

```sh
python3 -B firmware/esp32s3_human/web/human_s3_web.py \
  --port /dev/serial/by-id/your-device \
  --calibration /path/to/calibration_sdk_geometry.bin \
  --http-port 8896
```

服务提供 `/`、`/api/snapshot` 和 SSE `/events`。使用随附的 systemd 用户服务时，在 `~/.config/esp32s3-human-web.env` 配置 `HUMAN_S3_PORT` 与 `HUMAN_S3_CALIBRATION`，两项均填绝对路径。

## v3 验证摘要

- 六段开发回放共 1,417 帧，固定区间主 ID 切换由 5 次降至 0 次。三段指定跌倒片段的疑似首帧为 f73、f156、f110，同轨恢复直立分别为 f136、f209、f197。
- 780 帧双鸟归档回放中，锁定和疑似均为 0。ESP32-S3 实流短测为 9.65 Hz，跟踪 P95 31.33 ms，尾包到结果 P95 84.14 ms。

## 边界说明

- 本实现为纯几何 + 运动学候选（上限 `FALL_SUSPECTED`，无 `confirmed`）。
- 6 段真实会话为开发对照集，无逐帧人体/跌倒真值，真实准确率、召回率和误报率仍为 `UNKNOWN`。
- 静止超过保持时间、始终未在合格尺寸下运动或只被局部扫到的人，可能没有锁定。人体尺寸且连贯移动的物体仍可能满足几何门槛。
