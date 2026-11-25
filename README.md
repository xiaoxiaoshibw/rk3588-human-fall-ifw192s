# ESP32-S3 人体运动学与疑似跌倒识别分支 (`esp32s3`)

本分支为 **ESP32-S3 + W5500 + IFW192S** 单片机独立版本（从 `master` 切分，去除 RK3588 ROS / PC 控制台代码，仅保留 ESP32-S3 固件、纯 C++17 核心、轻量看板与离线回放所需的最小 IFW192S 标定表/解码模块）。

- 完整架构、构建、烧录与验证说明见：[firmware/esp32s3_human/README.md](firmware/esp32s3_human/README.md)
- 分支说明见：[BRANCHES.md](BRANCHES.md)

## 快速编译与单测（主机）

```powershell
New-Item -ItemType Directory -Force firmware/esp32s3_human/build | Out-Null
g++ -O3 -std=c++17 -Wall -Wextra -Werror firmware/esp32s3_human/human_tracker.cpp firmware/esp32s3_human/host_replay.cpp -o firmware/esp32s3_human/build/human_host.exe
python -B -W error -m unittest discover -s firmware/esp32s3_human -p "test_human_tracker.py" -v
python -B -W error -m unittest discover -s firmware/esp32s3_human/web -v
```

## ESP-IDF 固件构建

```sh
idf.py -C firmware/esp32s3_human/esp_idf -D IDF_TARGET=esp32s3 build
```