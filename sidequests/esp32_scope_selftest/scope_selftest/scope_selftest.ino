/* ESP32-S3 示波器自检固件（Arduino-ESP32 3.x 版）
 *
 * 原稿是 ESP-IDF 程序（app_main + driver/twai.h），放进 Arduino IDE 必然链接失败：
 *   Arduino 核的 main.cpp 只调用 setup()/loop()，链接器找不到这两个符号；
 *   而且 app_main 已经由 Arduino 核提供，你不能再定义一份。
 * 这里把初始化原样搬进 setup()，app_main/loopTask 交给 Arduino 核。
 *
 * 信号（接示波器）：
 *   GPIO4  1 kHz 硬件方波（LEDC，10 bit / 50%），CH1 + 触发源
 *   GPIO5  WCET 脉冲，高电平 = 任务体执行时间，CH2；约 280 ms 三角扫 200..3000 次迭代
 *   GPIO6  心跳：每发一帧 CAN 翻转一次 → 50 Hz 方波（100 个边沿/秒）
 *   GPIO7  CAN_TX → 收发器 TXD，CH3 可做 500 kbit/s 协议解码
 *   GPIO8  CAN_RX ← 收发器 RXD
 *
 * 相对原稿的实际修正（详见同目录 README.md）：
 *   1. 1 kHz 任务里不再串口打印：115200 下 100 字符 ≈ 9 ms，每秒都会把 1 kHz 打出一个大坑。
 *      统计值经 queue 交给低优先级 log 任务输出。
 *   2. 日志改用 Serial.printf：Arduino IDE 的 Tools → Core Debug Level 默认 None，
 *      ESP_LOGx 在编译期被整段裁掉（实测 TAG 会变成 unused 变量）；本机 sdkconfig 的
 *      CONFIG_LOG_MAXIMUM_LEVEL 也只有 1（ERROR）。所以那条 1 s 统计原本根本打不出来。
 *   3. CAN 默认 NO_ACK：台架上没有第二个节点回 ACK，NORMAL 模式 TEC 很快溢出进 bus-off，
 *      CAN 波形半秒后就停了；同时加了 bus-off 自动恢复，接真总线时改回 TWAI_MODE_NORMAL。
 *   4. CAN 发送超时从 5 ms 改成 0：原来总线异常时 tx 阻塞 5 ms + delay 10 ms，实际只有 66 Hz。
 *   5. 周期统计加"超 1.5 ms"计数，1 kHz 抖动/丢拍能直接看出来。
 *   6. IDF 5.x 把 xTaskCreatePinnedToCore 挪到了 freertos/idf_additions.h，不 include 直接编译报错。
 */

#include <Arduino.h>
#include "freertos/FreeRTOS.h"
#include "freertos/task.h"
#include "freertos/queue.h"
#include "freertos/idf_additions.h"   /* IDF 5.x：xTaskCreatePinnedToCore 搬到这里了 */
#include "driver/gpio.h"
#include "driver/ledc.h"
#include "driver/twai.h"
#include "esp_timer.h"

/* 1 kHz 任务靠 pdMS_TO_TICKS(1) 定时；节拍低于 1000 Hz 时它退化成 0 tick，任务变成死循环。
 * Arduino-ESP32 3.x 固定 1000 Hz；纯 ESP-IDF 默认 100 Hz，要自己在 sdkconfig 里开 1000。 */
#if configTICK_RATE_HZ < 1000
#error "configTICK_RATE_HZ 必须 >= 1000（Arduino-ESP32 默认就是 1000）"
#endif

#define PIN_REF    GPIO_NUM_4   /* 1 kHz 硬件方波（基准） */
#define PIN_WCET   GPIO_NUM_5   /* 任务体：高电平 = 执行时间 */
#define PIN_ALIVE  GPIO_NUM_6   /* CAN 心跳 */
#define PIN_CAN_TX GPIO_NUM_7   /* 接收发器 TXD */
#define PIN_CAN_RX GPIO_NUM_8   /* 接收发器 RXD */

/* 台架自检（只有一块板）：NO_ACK 不需要别人回 ACK，也不会进 bus-off。
 * 接上真实 CAN 总线后改成 TWAI_MODE_NORMAL。 */
#define CAN_MODE        TWAI_MODE_NO_ACK
#define CAN_ID          0x1A0
#define CAN_PERIOD_MS   10      /* 100 Hz */
#define TICK_PERIOD_MS  1       /* 1 kHz */
#define LATE_US         1500    /* 周期超过它就记一次"晚拍" */

/* ---------- CRC-8/SAE-J1850：poly 0x1D, init 0xFF, xorout 0xFF ----------
 * 校验值：输入 "123456789" 应得 0x4B。 */
static uint8_t crc8_j1850(const uint8_t *d, size_t n)
{
    uint8_t crc = 0xFF;
    for (size_t i = 0; i < n; i++) {
        crc ^= d[i];
        for (int b = 0; b < 8; b++)
            crc = (crc & 0x80) ? (uint8_t)((crc << 1) ^ 0x1D) : (uint8_t)(crc << 1);
    }
    return (uint8_t)~crc;
}

/* ---------- 硬件 1 kHz 方波作为时间基准 ---------- */
static void ref_init(void)
{
    ledc_timer_config_t t = {
        .speed_mode      = LEDC_LOW_SPEED_MODE,
        .duty_resolution = LEDC_TIMER_10_BIT,
        .timer_num       = LEDC_TIMER_0,
        .freq_hz         = 1000,
        .clk_cfg         = LEDC_AUTO_CLK,
    };
    ESP_ERROR_CHECK(ledc_timer_config(&t));

    ledc_channel_config_t c = {
        .gpio_num   = PIN_REF,
        .speed_mode = LEDC_LOW_SPEED_MODE,
        .channel    = LEDC_CHANNEL_0,
        .intr_type  = LEDC_INTR_DISABLE,
        .timer_sel  = LEDC_TIMER_0,
        .duty       = 512,          /* 10 bit 下 50% */
        .hpoint     = 0,
    };
    ESP_ERROR_CHECK(ledc_channel_config(&c));
}

/* ---------- 可控负载：后面换成真实的包络/仲裁代码 ----------
 * noinline + volatile sink：保证循环不会被优化掉，也不会被常量折叠。 */
static volatile uint32_t g_sink;

static __attribute__((noinline)) uint32_t busy(uint32_t n)
{
    uint32_t acc = 0;
    for (uint32_t i = 0; i < n; i++) {
        __asm__ __volatile__("nop");
        acc += i;
    }
    return acc;
}

/* ---------- 统计值经队列交给 log 任务，1 kHz 任务里绝不碰串口 ---------- */
typedef struct {
    int64_t  per_min, per_avg, per_max;   /* 周期 us */
    int64_t  wc_min, wc_max;              /* 任务体 us */
    uint32_t late;                        /* 周期 > LATE_US 的次数 */
    uint32_t samples;
} tick_stats_t;

typedef struct {
    uint32_t tx_ok, tx_fail;
    uint16_t seq;
} can_stats_t;

static QueueHandle_t s_tick_q;   /* 深度 1，用 xQueueOverwrite 覆盖写 */
static QueueHandle_t s_can_q;

/* ---------- 1 kHz 任务 ---------- */
static void tick_task(void *arg)
{
    (void)arg;
    TickType_t last = xTaskGetTickCount();
    int64_t t_prev  = esp_timer_get_time();

    int64_t per_min = INT64_MAX, per_max = 0, per_sum = 0;
    int64_t wc_min  = INT64_MAX, wc_max  = 0;
    uint32_t n = 0, late = 0;
    uint32_t iters = 200;
    int32_t  dir   = 1;

    for (;;) {
        gpio_set_level(PIN_WCET, 1);
        int64_t t0 = esp_timer_get_time();

        g_sink = busy(iters);              /* ← 换成你的包络/仲裁 */

        int64_t t1 = esp_timer_get_time();
        gpio_set_level(PIN_WCET, 0);

        int64_t wc = t1 - t0;
        if (wc < wc_min) wc_min = wc;
        if (wc > wc_max) wc_max = wc;

        vTaskDelayUntil(&last, pdMS_TO_TICKS(TICK_PERIOD_MS));   /* 1 ms */

        int64_t t2  = esp_timer_get_time();
        int64_t per = t2 - t_prev;
        t_prev = t2;
        if (per < per_min) per_min = per;
        if (per > per_max) per_max = per;
        if (per > LATE_US) late++;
        per_sum += per;

        /* 三角波扫 200..3000：示波器余辉下能看到脉宽包络（约 280 ms 一个来回） */
        if (dir > 0) { iters += 20; if (iters >= 3000) dir = -1; }
        else         { iters -= 20; if (iters <= 200)  dir =  1; }

        if (++n >= 1000) {                 /* 每 1 s 交一次统计 */
            tick_stats_t s = {
                .per_min = per_min,
                .per_avg = per_sum / (int64_t)n,
                .per_max = per_max,
                .wc_min  = wc_min,
                .wc_max  = wc_max,
                .late    = late,
                .samples = n,
            };
            xQueueOverwrite(s_tick_q, &s);  /* 不阻塞 */
            n = 0; late = 0; per_sum = 0;
            per_min = INT64_MAX; per_max = 0;
            wc_min  = INT64_MAX; wc_max  = 0;
        }
    }
}

/* ---------- bus-off 后自动恢复：否则一次总线故障之后 TX 永久发呆 ---------- */
static void can_recover_if_bus_off(void)
{
    uint32_t alerts = 0;
    if (twai_read_alerts(&alerts, 0) == ESP_OK && (alerts & TWAI_ALERT_BUS_OFF)) {
        Serial.println("[can] bus-off，发起恢复");
        twai_initiate_recovery();
        return;
    }

    twai_status_info_t st;
    if (twai_get_status_info(&st) == ESP_OK && st.state == TWAI_STATE_BUS_OFF) {
        Serial.println("[can] bus-off（状态轮询），发起恢复");
        twai_initiate_recovery();
    }
}

/* ---------- 100 Hz CAN 任务 ---------- */
static void can_task(void *arg)
{
    (void)arg;
    uint16_t seq   = 0;
    uint8_t  alive = 0;
    uint32_t tx_ok = 0, tx_fail = 0;
    uint32_t frames = 0;
    TickType_t last = xTaskGetTickCount();

    for (;;) {
        uint8_t d[8] = {0};
        d[0] = (uint8_t)(seq & 0xFF);
        d[1] = (uint8_t)(seq >> 8);
        d[2] = (uint8_t)(alive & 0x0F);   /* alive counter */
        d[3] = 0;                         /* source: 0=主控 */
        d[4] = 0;                         /* AEB 等级 */
        d[5] = 0;                         /* δ_cmd 低字节 */
        d[6] = 0;                         /* δ_cmd 高字节 */
        d[7] = crc8_j1850(d, 7);

        twai_message_t m = {0};
        m.identifier       = CAN_ID;
        m.data_length_code = 8;
        memcpy(m.data, d, 8);

        /* 超时给 0：总线异常时也不拖慢 100 Hz；丢帧由 tx_fail 统计出来 */
        esp_err_t e = twai_transmit(&m, 0);
        if (e == ESP_OK) tx_ok++;
        else             tx_fail++;

        gpio_set_level(PIN_ALIVE, alive & 1);   /* 每帧翻转 → 50 Hz 方波 */
        alive = (alive + 1) & 0x0F;
        seq++;

        can_recover_if_bus_off();

        if (++frames >= 100) {                      /* 每 100 帧 = 1 s 交一次统计 */
            can_stats_t c = { .tx_ok = tx_ok, .tx_fail = tx_fail, .seq = seq };
            xQueueOverwrite(s_can_q, &c);
            frames = 0;
        }

        vTaskDelayUntil(&last, pdMS_TO_TICKS(CAN_PERIOD_MS));   /* 100 Hz，按绝对时刻排程 */
    }
}

/* ---------- 低优先级 log 任务：串口只在 core0 的普通任务里出现 ---------- */
static void log_task(void *arg)
{
    (void)arg;
    for (;;) {
        vTaskDelay(pdMS_TO_TICKS(1000));

        tick_stats_t t;
        if (xQueueReceive(s_tick_q, &t, 0) == pdTRUE) {
            Serial.printf("[1kHz] 周期 min/avg/max = %lld/%lld/%lld us | WCET %lld..%lld us | 晚拍(>%dus) %lu/%lu\n",
                          (long long)t.per_min, (long long)t.per_avg, (long long)t.per_max,
                          (long long)t.wc_min, (long long)t.wc_max,
                          LATE_US, (unsigned long)t.late, (unsigned long)t.samples);
        } else {
            Serial.println("[1kHz] 这一秒没拿到统计（1 kHz 任务被饿死？）");
        }

        can_stats_t c;
        if (xQueuePeek(s_can_q, &c, 0) == pdTRUE) {
            Serial.printf("[can]  seq=%u tx_ok=%lu tx_fail=%lu\n",
                          (unsigned)c.seq, (unsigned long)c.tx_ok, (unsigned long)c.tx_fail);
        }
    }
}

void setup()
{
    Serial.begin(115200);
    delay(200);   /* 等 USB 串口枚举 */

    Serial.println("\n=== ESP32-S3 scope selftest ===");
    Serial.printf("freq=%u MHz, tick=%d Hz, CAN=%s, 1 kHz=%d ms\n",
                  (unsigned)getCpuFrequencyMhz(), (int)configTICK_RATE_HZ,
                  (CAN_MODE == TWAI_MODE_NO_ACK) ? "NO_ACK(台架)" : "NORMAL",
                  TICK_PERIOD_MS);

    ref_init();

    gpio_config_t io = {
        .pin_bit_mask = (1ULL << PIN_WCET) | (1ULL << PIN_ALIVE),
        .mode         = GPIO_MODE_OUTPUT,
        .pull_up_en   = GPIO_PULLUP_DISABLE,
        .pull_down_en = GPIO_PULLDOWN_DISABLE,
        .intr_type    = GPIO_INTR_DISABLE,
    };
    ESP_ERROR_CHECK(gpio_config(&io));

    twai_general_config_t g = TWAI_GENERAL_CONFIG_DEFAULT(PIN_CAN_TX, PIN_CAN_RX, CAN_MODE);
    g.alerts_enabled = TWAI_ALERT_BUS_OFF | TWAI_ALERT_ERR_PASS;
    twai_timing_config_t  t = TWAI_TIMING_CONFIG_500KBITS();
    twai_filter_config_t  f = TWAI_FILTER_CONFIG_ACCEPT_ALL();
    ESP_ERROR_CHECK(twai_driver_install(&g, &t, &f));
    ESP_ERROR_CHECK(twai_start());

    s_tick_q = xQueueCreate(1, sizeof(tick_stats_t));
    s_can_q  = xQueueCreate(1, sizeof(can_stats_t));
    configASSERT(s_tick_q && s_can_q);

    /* 1 kHz 放 core1 高优先级（Arduino loopTask 也在 core1，优先级 1，不挡它）；
     * CAN 放 core0。注意 ESP_TASK_WDT 检查的是 core0 的 idle，所以 core0 上别写死循环。 */
    xTaskCreatePinnedToCore(tick_task, "tick1k", 4096, NULL, 20, NULL, 1);
    xTaskCreatePinnedToCore(can_task,  "can100", 4096, NULL, 10, NULL, 0);
    xTaskCreatePinnedToCore(log_task,  "log1s",  4096, NULL,  1, NULL, 0);
}

void loop()
{
    /* 活儿都在上面的任务里，loopTask 让位即可（也可以 vTaskDelete(NULL) 回收 8 KB 栈） */
    vTaskDelay(portMAX_DELAY);
}