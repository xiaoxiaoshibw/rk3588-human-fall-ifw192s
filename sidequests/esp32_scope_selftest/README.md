# ESP32-S3 示波器自检固件（Arduino 版）

原稿是 ESP-IDF 程序，被塞进 Arduino IDE 编译，所以链接失败。这个目录是改好的 Arduino 版本 +
一份可以脱离 IDE 复现编译检查的脚本。

## 1. 为什么报 `undefined reference to setup()/loop()`

```
core.a(main.cpp.o): undefined reference to `setup()'
core.a(main.cpp.o): undefined reference to `loop()'
```

`cores/esp32/main.cpp:55` 的 `loopTask()` 里只调用 `setup()` 和 `loop()`，而原稿定义的是
`app_main()`：

- Arduino 核**自己**提供了 `app_main()`（就在同一个 `main.cpp` 里，它负责建 loopTask），
  所以你不能、也不需要再写一份；
- 你把 `app_main` 写进 `.ino`，编译器把它当普通函数编，`setup()/loop()` 依旧不存在，于是 ld 报错。

两条路，任选：

| 路线 | 做法 | 适合 |
|---|---|---|
| **A. 留在 Arduino**（本目录） | 初始化搬进 `setup()`，`loop()` 里 `vTaskDelay(portMAX_DELAY)`；其它 IDF 驱动 API 照用（Arduino 3.x 就是 IDF 5.3） | 手头只有 Arduino IDE，想直接烧 |
| B. 换 ESP-IDF | 保留 `app_main`，`idf.py create-project`，**并把 `CONFIG_FREERTOS_HZ` 改成 1000** | 想要 menuconfig / 组件化 / 正式工程 |

B 的关键在最后一句：ESP-IDF 默认 `CONFIG_FREERTOS_HZ=100`，`pdMS_TO_TICKS(1)` 会变成 **0 tick**，
`vTaskDelayUntil` 立刻返回，1 kHz 任务退化成死循环。Arduino 核把它设成了 1000（本机
`sdkconfig.h` 里 `#define CONFIG_FREERTOS_HZ 1000`，已核对），所以路线 A 不受影响。脚本和
`.ino` 都加了 `#if configTICK_RATE_HZ < 1000` 的编译期拦截。

## 2. 怎么用

```
sidequests/esp32_scope_selftest/
├── scope_selftest/scope_selftest.ino   # 打开这个（文件夹名必须和 .ino 同名）
├── build_check.ps1                     # 命令行编译检查（不链接、不烧写）
├── build_check.log                     # 最近一次的检查输出
└── README.md
```

Arduino IDE 2.x → 打开 `scope_selftest.ino` → 板子选 **ESP32S3 Dev Module** → 串口 115200。
`Tools → Core Debug Level` 保持默认即可（报告走 `Serial`，不看 log 级别，见 §3）。

## 3. 除链接错误外，原稿还有这些坑（都已改）

| # | 原稿 | 后果 | 现在 |
|---|---|---|---|
| 1 | `tick_task` 里 `ESP_LOGI` 每秒一次 | 115200 下约 110 字符 ≈ **9.5 ms**，每秒给 1 kHz 挖一个 9 ms 的坑，`per_max` 会稳定显示 ~9000+ µs | 统计经 `xQueueOverwrite` 交给低优先级 `log1s` 任务打印，1 kHz 任务里不碰串口 |
| 2 | 同上，日志用 `ESP_LOGx` | `Tools → Core Debug Level` 默认 **None**，`ESP_LOGx` 编译期整段裁掉（实测 `TAG` 变成 unused 变量）；本机 `CONFIG_LOG_MAXIMUM_LEVEL` 也只有 1(ERROR) → **一条都打不出来** | 改用 `Serial.printf`，与 log 配置无关 |
| 3 | `xTaskCreatePinnedToCore` | IDF 5.x 把它挪到了 `freertos/idf_additions.h`，不 include 直接 `not declared in this scope`（编到这里就会卡住） | 显式 include |
| 4 | CAN `TWAI_MODE_NORMAL`，台架单节点 | 没人回 ACK，TEC 每帧 +8，**32 帧（100 Hz 下 ≈0.32 s）** 就到 bus-off，之后 TX 全停；NORMAL 模式也不会自己恢复 | 默认 `TWAI_MODE_NO_ACK`（不要求 ACK、不进 bus-off），并加 bus-off 自动恢复；上真总线改回 `NORMAL` |
| 5 | `twai_transmit(&m, pdMS_TO_TICKS(5))` | 总线异常时每轮 = 5 ms 阻塞 + 10 ms delay → 实际 **≈66 Hz**，不是 100 Hz | 超时 0，失败计入 `tx_fail`；用 `vTaskDelayUntil` 按绝对时刻排 10 ms，节拍不漂 |
| 6 | 注释说心跳 100 Hz | 每帧翻转一次 = **50 Hz 方波**（100 个边沿/秒） | 注释改成 50 Hz 方波，别在示波器上按 100 Hz 判读 |
| 7 | `d[7] = crc8(d, 7)` | 若接收端按 AUTOSAR E2E Profile 1 校验，CRC 输入还要先拼 2 字节 DataID（`A0 01`），现在这版是自定义 CRC | 保留你现在的定义，README 这里点一句，跟接收端对齐即可 |
| 8 | `per_min` 首帧 | 第一帧含任务启动/首次调度，前 1 s 的 min 偏小 | 保留（只影响开机第一秒），知道就行 |

CRC 算法本身是对的：CRC-8/SAE-J1850，poly `0x1D`、init `0xFF`、xorout `0xFF`，
校验值 `"123456789"` → `0x4B`（已用同算法的脚本核对）。

`busy()` 加了 `noinline`，结果写进 `volatile` 全局，避免被优化器整段删掉或被常量折叠。

## 4. 编译验证

没有 Arduino IDE 也能验证（本机没装 `arduino-cli`，所以脚本直接调 IDE 用的那套工具链）：

```powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass -File build_check.ps1
```

脚本复刻 `platform.txt` 的 `recipe.cpp.o.pattern`：`@flags/cpp_flags` + `-iprefix <sdk>/include/` +
`@flags/includes` + 板型宏，只编译不链接。最近一次结果见 `build_check.log`：

```
response file: 22 lines
compiler : ...\esp-x32\2405\bin\xtensa-esp32s3-elf-g++.exe
sdk      : ...\esp32-arduino-libs\idf-release_v5.3-cfea4f7c-v1\esp32s3
exit=0
OK  no warnings  object: 71776 bytes
```

即 `-Wall -Wextra -O2` 零告警。**注意这只能证明能编译**，波形和时序要靠上板实测。

## 5. 接线

| 固件引脚 | 接到 | 说明 |
|---|---|---|
| GPIO4 | 示波器 CH1 | 1 kHz / 3.3 V / 50%，作为时基基准 + 触发源 |
| GPIO5 | CH2 | WCET 脉冲，高电平 = `busy()` 执行时间 |
| GPIO6 | CH4（可选） | 心跳，50 Hz 方波 |
| GPIO7 | 收发器 TXD（有的标 CTX/D） | ESP32 发 → 收发器 |
| GPIO8 | 收发器 RXD（有的标 CRX/R） | 收发器 → ESP32 |

- 收发器 5 V 供电、逻辑侧 3.3 V 兼容（TJA1050 之类 3.3 V 逻辑可以直连；5 V-only 的 PCA82C250 要分压/电平转换）。
- CANH/CANL 双绞，两端各 120 Ω；台架单节点也建议接一个 120 Ω，波形干净、反射少。
- 一定要共地（ESP32 GND ↔ 收发器 GND ↔ 示波器地）。
- 引脚选择没问题：GPIO19/20 是 USB，GPIO0/3/45/46 是 strapping，GPIO26–37 被 flash/PSRAM 占了，4/5/6/7/8 都空着。

## 6. 示波器上应该看到什么

- **CH1**：稳定 1 kHz 方波。LEDC 分频 = 80 MHz / (1000 × 1024) = 78.125，小数分频能精确做到，
  所以周期是 1000.0 µs（长期稳定度跟 40 MHz 晶振走）。
- **CH2**：脉宽在 **约 3–50 µs** 之间三角扫（`nop` 循环每次迭代约 4 个周期 ≈ 16.7 ns @240 MHz，
  200→3000 次），每 1 ms 走一步、140 步一个单程，一个来回 ≈ **280 ms**。看包络用余辉/峰值检测，
  时基 50–100 ms/div；看单脉冲用 10 µs/div + CH1 触发。
- **CH3（GPIO7）**：CAN 单端波形，500 kbit/s；解码设 11 位 ID、500k、采样点 75–80%。
  NO_ACK 模式下 ACK slot 是隐性（解码器会报 "no ACK"），帧内容本身正常。
- **CH4**：50 Hz 方波；丢帧会表现为周期突然变长。
- 1 kHz 任务和 LEDC 是两套时基（都锁同一颗晶振），相对相位会缓慢滑动，属正常现象。

## 7. 串口输出怎么读

```
=== ESP32-S3 scope selftest ===
freq=240 MHz, tick=1000 Hz, CAN=NO_ACK(台架), 1 kHz=1 ms
[1kHz] 周期 min/avg/max = 1000/1000/1003 us | WCET 3..51 us | 晚拍(>1500us) 0/1000
[can]  seq=1234 tx_ok=1234 tx_fail=0
```

- `周期 max` 偶尔 1001–1005 正常（tick 量化 + 中断）；出现 ~2000 说明丢了一拍；
  出现 ~9500 说明又有东西在 1 kHz 任务里阻塞。
- `WCET` 应随三角波线性变化；`晚拍` 长时间非 0 就要查是谁占了 core1。
- `tx_fail` 一直涨：检查收发器供电/接线，或（接真总线时）确认有人回 ACK。

## 8. 边界

- 只在宿主机上做了编译检查（`-Wall -Wextra` 零告警），**没有上板**：波形、抖动、bus-off 时间都是按
  数据手册/代码推算的，实测以你的板子为准。
- 这个目录是独立 sidequest，没有改仓库其它任何内容，也不属于 HF/GL/HC/HR 主线。
- 要 ESP-IDF 版（`app_main` + `idf.py`）可以再补一份；这边没装 IDF，补了也没法在这里编译验证，
  所以暂时只给 Arduino 版。