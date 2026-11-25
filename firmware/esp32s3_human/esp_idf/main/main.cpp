#include <algorithm>
#include <array>
#include <cinttypes>
#include <cmath>
#include <cstdio>
#include <cstring>
#include <new>

#include "driver/uart.h"
#include "esp_attr.h"
#include "esp_heap_caps.h"
#include "esp_rom_crc.h"
#include "esp_timer.h"
#include "freertos/FreeRTOS.h"
#include "freertos/queue.h"
#include "freertos/task.h"

#include "geometry.hpp"
#include "human_tracker.hpp"
#include "w5500.hpp"
#include "wire.hpp"

namespace {

using namespace ifw192s;
constexpr int kFrameBuffers = 2;
constexpr auto kPsram = MALLOC_CAP_SPIRAM | MALLOC_CAP_8BIT;
constexpr auto kInternal = MALLOC_CAP_INTERNAL | MALLOC_CAP_8BIT;
constexpr size_t kCalBytes = sizeof(RangeCalibration) + kFrameRecords * 2 * sizeof(double);
constexpr uint32_t kMaxReplayPackets = 200'000;
constexpr float kDefaultMountPitchDeg = 26.0f;
constexpr float kDefaultMountRollDeg = 0.0f;

struct TaggedGrid {
    int slot;
    FrameBoundary boundary;
};

struct PackedPoint {
    uint16_t source_row;
    uint16_t width;
    uint16_t range_low;
    uint16_t area_low;
    uint16_t high_bytes;

    static PackedPoint pack(const WireRecord& point, uint16_t row) {
        return {row, point.pulse_width, static_cast<uint16_t>(point.range_ticks),
                static_cast<uint16_t>(point.pulse_area),
                static_cast<uint16_t>((point.range_ticks >> 16) | ((point.pulse_area >> 16) << 8))};
    }

    WireRecord unpack(uint16_t cell) const {
        return {static_cast<uint8_t>(cell), static_cast<uint8_t>(cell >> 8), width,
                range_low | (uint32_t{high_bytes & 0xffu} << 16),
                area_low | ((uint32_t{high_bytes} & 0xff00u) << 8)};
    }
};
static_assert(sizeof(PackedPoint) == 10);

struct LiveState {
    QueueHandle_t free_slots = nullptr;
    QueueHandle_t ready = nullptr;
    TaskHandle_t owner = nullptr;
    PackedPoint* input_frames[kFrameBuffers]{};
    RangeCalibration calibration{};
    Direction* measured_rays = nullptr;
    human_s3::Workspace workspace{};
    human_s3::HumanTracker* tracker = nullptr;
    human_s3::FrameResult* result = nullptr;
    bool live = false;
};

LiveState state{};

template <class T>
T* allocate(size_t count, bool prefer_internal = false) {
    void* out = prefer_internal ? heap_caps_malloc(sizeof(T) * count, kInternal) : nullptr;
    if (!out) {
        out = heap_caps_malloc(sizeof(T) * count, kPsram);
    }
    return static_cast<T*>(out);
}

bool read_exact(void* buffer, size_t size) {
    auto* next = static_cast<uint8_t*>(buffer);
    while (size) {
        const auto got = uart_read_bytes(UART_NUM_0, next, size, pdMS_TO_TICKS(8000));
        if (got <= 0) {
            return false;
        }
        size -= static_cast<size_t>(got);
        next += got;
    }
    return true;
}

void uart_start() {
    uart_config_t config{};
    config.baud_rate = 2'000'000;
    config.data_bits = UART_DATA_8_BITS;
    config.parity = UART_PARITY_DISABLE;
    config.stop_bits = UART_STOP_BITS_1;
    config.flow_ctrl = UART_HW_FLOWCTRL_DISABLE;
    config.source_clk = UART_SCLK_DEFAULT;
    ESP_ERROR_CHECK(uart_param_config(UART_NUM_0, &config));
    ESP_ERROR_CHECK(uart_driver_install(UART_NUM_0, 16 * 1024, 0, 0, nullptr, 0));
    setvbuf(stdout, nullptr, _IONBF, 0);
}

bool init_storage() {
    for (auto& buffer : state.input_frames) {
        buffer = allocate<PackedPoint>(kFrameRecords, false);
        if (!buffer) {
            return false;
        }
    }
    state.workspace.points = allocate<human_s3::Point3f>(human_s3::kCells, false);
    state.workspace.cur_range_mm = allocate<uint16_t>(human_s3::kCells, true);
    state.workspace.bg_far_mm = allocate<uint16_t>(human_s3::kCells, false);
    state.workspace.prev_range_mm = allocate<uint16_t>(human_s3::kCells, false);
    state.workspace.cell_flags = allocate<uint8_t>(human_s3::kCells, true);
    state.workspace.bfs_queue = allocate<uint16_t>(human_s3::kCells, false);

    const auto& w = state.workspace;
    if (!w.points || !w.cur_range_mm || !w.bg_far_mm || !w.prev_range_mm ||
        !w.cell_flags || !w.bfs_queue) {
        return false;
    }

    void* tracker_mem = allocate<human_s3::HumanTracker>(1, true);
    void* result_mem = allocate<human_s3::FrameResult>(1, true);
    if (!tracker_mem || !result_mem) {
        return false;
    }

    human_s3::Config cfg{};
    cfg.gravity_up = human_s3::Config::gravity_up_from_pitch_roll(
        kDefaultMountPitchDeg, kDefaultMountRollDeg);
    state.tracker = new (tracker_mem) human_s3::HumanTracker(state.workspace, cfg);
    state.result = new (result_mem) human_s3::FrameResult{};
    return true;
}

void prepare_rays(const uint8_t* calibration) {
    std::memcpy(&state.calibration, calibration, sizeof(state.calibration));
    const uint8_t* cursor = calibration + sizeof(state.calibration);
    for (uint32_t cell = 0; cell < kFrameRecords; ++cell) {
        double az, el;
        std::memcpy(&az, cursor, sizeof(az));
        std::memcpy(&el, cursor + sizeof(az), sizeof(el));
        cursor += sizeof(az) + sizeof(el);
        state.measured_rays[cell] = ray_from_calibration(static_cast<float>(az), static_cast<float>(el));
    }
}

bool wait_for_calibration() {
    uint8_t header[16];
    if (!read_exact(header, sizeof(header)) || std::memcmp(header, "CAL2", 4) != 0 ||
        ifw192s::read_u32(header + 4) != 0 || ifw192s::read_u32(header + 8) != kCalBytes) {
        return false;
    }
    auto* data = allocate<uint8_t>(kCalBytes, false);
    if (!data) {
        return false;
    }
    const bool okay = read_exact(data, kCalBytes) &&
                      esp_rom_crc32_le(0, data, kCalBytes) == ifw192s::read_u32(header + 12);
    if (okay) {
        prepare_rays(data);
    }
    heap_caps_free(data);
    return okay;
}

void materialize_human_grid(const PackedPoint* frame, human_s3::HumanTracker& tracker) {
    constexpr float kMinRangeM = 0.35f;
    constexpr float kMaxRangeM = 8.00f;
    const auto* rays = state.measured_rays;
    const auto cal = state.calibration;

    tracker.begin_frame();
    for (int ring = 0; ring < kRings; ++ring) {
        const uint32_t row_base = static_cast<uint32_t>(ring) << 8;
        const PackedPoint* row_points = frame + row_base;
        const Direction* row_rays = rays + row_base;
        for (int col = 0; col < kColumns; ++col) {
            const auto& pt = row_points[col];
            if (pt.width == 0) {
                continue;
            }
            const uint16_t wire_cell = static_cast<uint16_t>(row_base | static_cast<uint32_t>(col));
            const float range = live_measured_range(pt.unpack(wire_cell), cal);
            if (range < kMinRangeM || range > kMaxRangeM) {
                continue;
            }
            const uint16_t tcell = static_cast<uint16_t>(row_base | static_cast<uint32_t>(255 - col));
            const auto& ray = row_rays[col];
            const uint16_t r_mm = static_cast<uint16_t>(range * 1000.0f + 0.5f);
            tracker.set_cell_range_mm(tcell, range * ray.x, range * ray.y, range * ray.z, r_mm);
        }
    }
}

void track_frames() {
    auto& tracker = *state.tracker;
    auto& result = *state.result;
    uint64_t prev_read_us = 0;
    bool have_prev = false;

    for (;;) {
        TaggedGrid input{};
        xQueueReceive(state.ready, &input, portMAX_DELAY);
        if (input.slot < 0) {
            return;
        }
        const auto& frame = input.boundary;
        if (!frame.complete) {
            xQueueSend(state.free_slots, &input.slot, 0);
            std::printf("{\"type\":\"frame\",\"seq\":%" PRIu32 ",\"state\":\"UNKNOWN\",\"records\":%" PRIu32 "}\n",
                        frame.final_sequence, frame.records);
            continue;
        }

        materialize_human_grid(state.input_frames[input.slot], tracker);
        const int64_t grid_ready = esp_timer_get_time();
        xQueueSend(state.free_slots, &input.slot, 0);

        float dt_sec = 0.104f;
        if (have_prev && frame.final_packet_read_us > prev_read_us) {
            dt_sec = static_cast<float>(frame.final_packet_read_us - prev_read_us) * 1e-6f;
        }
        have_prev = true;
        prev_read_us = frame.final_packet_read_us;

        const int64_t start = esp_timer_get_time();
        tracker.step(dt_sec, result);
        const int64_t ready = esp_timer_get_time();

        int locked_count = 0;
        int tentative_count = 0;
        int fall_suspected_count = 0;
        for (int i = 0; i < result.track_count; ++i) {
            const auto& tr = result.tracks[i];
            if (tr.locked_human && tr.measured_this_frame) {
                ++locked_count;
                if (tr.fall_state == human_s3::FallState::kFallSuspected) {
                    ++fall_suspected_count;
                }
            } else if (tr.measured_this_frame) {
                ++tentative_count;
            }
        }

        std::printf(
            "{\"type\":\"frame\",\"seq\":%" PRIu32
            ",\"state\":\"active\",\"warmup\":0,\"locked\":%d,\"candidates\":%d,\"tentative\":%d"
            ",\"valid_cells\":%d,\"fg_seeds\":%d,\"fall_suspected\":%d"
            ",\"tail_read_us\":%" PRIu64 ",\"grid_ready_us\":%" PRId64
            ",\"tracker_start_us\":%" PRId64 ",\"result_ready_us\":%" PRId64 "}\n",
            frame.final_sequence, locked_count, result.candidate_count, tentative_count,
            result.valid_cells, result.fg_seed_cells, fall_suspected_count,
            frame.final_packet_read_us, grid_ready, start, ready);

        for (int i = 0; i < result.track_count; ++i) {
            const auto& tr = result.tracks[i];
            if (!tr.locked_human || !tr.measured_this_frame) {
                continue;
            }
            std::printf(
                "{\"type\":\"track\",\"seq\":%" PRIu32 ",\"id\":%" PRIu32
                ",\"box\":[%d,%d,%d,%d],\"xyz_m\":[%.4f,%.4f,%.4f],\"points\":%d"
                ",\"range_m\":%.3f,\"height_m\":%.3f,\"h_p95\":%.3f,\"horiz_m\":%.3f"
                ",\"aspect\":%.3f,\"drop_m\":%.3f,\"vel_mps\":%.3f,\"acc_mps2\":%.3f"
                ",\"peak_down_vel\":%.3f,\"peak_down_acc\":%.3f,\"low_sec\":%.2f,\"still_sec\":%.2f"
                ",\"baseline_ready\":%s,\"fall_state\":\"%s\",\"fall_reason\":\"%s\"}\n",
                frame.final_sequence, tr.track_id,
                tr.box_c0, tr.box_r0, tr.box_c1, tr.box_r1,
                tr.center.x, tr.center.y, tr.center.z, tr.point_count,
                tr.range_m, tr.height_m, tr.h_p95, tr.horiz_span_m,
                tr.aspect, tr.drop_top_m, tr.vel_top_mps, tr.acc_top_mps2,
                tr.peak_down_vel_mps, tr.peak_down_acc_mps2, tr.low_posture_sec, tr.still_sec,
                tr.baseline_ready ? "true" : "false",
                human_s3::fall_state_name(tr.fall_state),
                human_s3::fall_reason_name(tr.fall_reason));
        }
    }
}

void worker(void*) {
    track_frames();
    xTaskNotifyGive(state.owner);
    vTaskDelete(nullptr);
}

struct FrameSink {
    int slot = -1;
    uint32_t no_buffer = 0;
    uint32_t queue_full = 0;
    uint32_t complete = 0;
    uint32_t unknown = 0;

    void begin_frame() {
        slot = -1;
        xQueueReceive(state.free_slots, &slot, 0);
    }

    void record(const WireRecord& point, uint32_t row) const {
        if (slot >= 0) {
            const uint16_t cell = (uint16_t{point.ring} << 8) | point.column;
            state.input_frames[slot][cell] = PackedPoint::pack(point, static_cast<uint16_t>(row));
        }
    }

    void end_frame(const FrameBoundary& frame) {
        complete += frame.complete;
        unknown += !frame.complete;
        if (slot < 0) {
            ++no_buffer;
            return;
        }
        const TaggedGrid ready{slot, frame};
        if (!xQueueSend(state.ready, &ready, 0)) {
            xQueueSend(state.free_slots, &slot, 0);
            ++queue_full;
        }
        slot = -1;
    }

    void discard_partial() {
        if (slot >= 0) {
            xQueueSend(state.free_slots, &slot, 0);
        }
        slot = -1;
    }
};

void usb_replay(WireAssembler& wire, FrameSink& sink, uint32_t count) {
    uint8_t payload[kPacketBytes];
    for (uint32_t i = 0; i < count; ++i) {
        if (!read_exact(payload, sizeof(payload))) {
            break;
        }
        wire.push(payload, sizeof(payload), esp_timer_get_time(), sink);
    }
}

void ethernet_live(WireAssembler& wire, FrameSink& sink, uint32_t hz) {
    W5500 nic;
    nic.init();
    if (nic.version() != 4 || !nic.configure(W5500::kIsolatedMac)) {
        nic.reset();
        std::puts("{\"type\":\"error\",\"message\":\"W5500 init failed\"}");
        return;
    }
    const int64_t wait_link_until = esp_timer_get_time() + 8'000'000;
    while (!(nic.phy() & 1) && esp_timer_get_time() < wait_link_until) {
        vTaskDelay(pdMS_TO_TICKS(25));
    }
    if (!(nic.phy() & 1) || !nic.open_udp()) {
        nic.reset();
        std::puts("{\"type\":\"error\",\"message\":\"W5500 link or socket failed\"}");
        return;
    }
    if (hz == 80'000'000) {
        nic.drive(GPIO_DRIVE_CAP_0);
        nic.read_dummy_bits(1);
    }
    if (nic.version(hz) != 4) {
        nic.reset();
        std::puts("{\"type\":\"error\",\"message\":\"W5500 SPI clock failed\"}");
        return;
    }

    uint8_t* buffers[2]{};
    for (auto& buffer : buffers) {
        buffer = static_cast<uint8_t*>(
            heap_caps_malloc(W5500::kBufferBytes, MALLOC_CAP_DMA | MALLOC_CAP_INTERNAL));
    }
    if (!buffers[0] || !buffers[1]) {
        heap_caps_free(buffers[0]);
        heap_caps_free(buffers[1]);
        nic.reset();
        std::puts("{\"type\":\"error\",\"message\":\"SPI DMA buffer allocation failed\"}");
        return;
    }

    uint32_t burst_errors = 0;
    const auto process_batch = [&](const uint8_t* batch, size_t available, uint64_t batch_read_us) {
        size_t cursor = 0;
        while (available - cursor >= 8) {
            const auto* p = batch + cursor;
            const size_t length = (uint16_t{p[6]} << 8) | p[7];
            if (length > available - cursor - 8) {
                break;
            }
            cursor += 8 + length;
            const uint8_t sensor[] = {192, 168, 1, 10, 0x1b, 0x58};
            if (std::memcmp(p, sensor, sizeof(sensor)) == 0) {
                wire.push(p + 8, length, batch_read_us, sink);
            }
        }
        if (cursor != available) {
            ++burst_errors;
            sink.discard_partial();
            wire.reset_alignment();
        }
    };

    unsigned next = 0;
    size_t previous_size = 0;
    uint64_t previous_read_us = 0;
    nic.acquire();
    for (;;) {
        const size_t size = nic.pending_ifw192s();
        if (!size) {
            if (previous_size) {
                process_batch(buffers[next ^ 1], previous_size, previous_read_us);
                previous_size = 0;
            }
            continue;
        }
        nic.start_pop(buffers[next], size);
        if (previous_size) {
            process_batch(buffers[next ^ 1], previous_size, previous_read_us);
        }
        previous_read_us = nic.finish_pop();
        previous_size = size;
        next ^= 1;
    }
}

}  // namespace

extern "C" void app_main() {
    uart_start();
    state.measured_rays = allocate<Direction>(kFrameRecords, false);
    if (!state.measured_rays) {
        std::puts("{\"type\":\"error\",\"message\":\"Cannot allocate calibration rays\"}");
        return;
    }
    std::puts("\n{\"type\":\"ready\",\"protocol\":2,\"profile\":\"human_kinematic_v4\"}");
    if (!wait_for_calibration() || !init_storage()) {
        std::puts("{\"type\":\"error\",\"message\":\"Calibration or frame storage failed\"}");
        return;
    }
    state.free_slots = xQueueCreate(kFrameBuffers, sizeof(int));
    state.ready = xQueueCreate(1, sizeof(TaggedGrid));
    state.owner = xTaskGetCurrentTaskHandle();
    if (!state.free_slots || !state.ready) {
        std::puts("{\"type\":\"error\",\"message\":\"Frame queue allocation failed\"}");
        return;
    }
    for (int slot = 0; slot < kFrameBuffers; ++slot) {
        xQueueSend(state.free_slots, &slot, 0);
    }
    std::printf(
        "{\"type\":\"calibrated\",\"internal_free\":%zu,\"psram_free\":%zu,"
        "\"workspace_bytes\":%zu,\"tracker_bytes\":%zu,\"mount_pitch_deg\":%.1f}\n",
        heap_caps_get_free_size(kInternal), heap_caps_get_free_size(kPsram),
        human_s3::HumanTracker::workspace_bytes(),
        human_s3::HumanTracker::tracker_object_bytes(),
        kDefaultMountPitchDeg);

    uint8_t command[8];
    const bool have_command = read_exact(command, sizeof(command));
    const auto argument = have_command ? ifw192s::read_u32(command + 4) : 0;
    const bool from_ethernet = have_command && std::memcmp(command, "UDP2", 4) == 0;
    state.live = from_ethernet;

    if (xTaskCreatePinnedToCore(worker, "human_tracker", 12288, nullptr, 4, nullptr, 1) != pdPASS) {
        std::puts("{\"type\":\"error\",\"message\":\"Cannot start tracker task\"}");
        return;
    }

    WireAssembler wire(from_ethernet ? PacketLayout::detect : PacketLayout::aligned);
    FrameSink sink;
    if (have_command && std::memcmp(command, "USB2", 4) == 0 && argument > 0 &&
        argument <= kMaxReplayPackets) {
        usb_replay(wire, sink, argument);
    } else if (from_ethernet && (argument == 40'000'000 || argument == 80'000'000)) {
        ethernet_live(wire, sink, argument);
    } else {
        std::puts("{\"type\":\"error\",\"message\":\"Invalid run command\"}");
    }

    sink.discard_partial();
    const TaggedGrid finished{-1, {}};
    xQueueSend(state.ready, &finished, portMAX_DELAY);
    ulTaskNotifyTake(pdTRUE, portMAX_DELAY);
    std::printf(
        "{\"type\":\"summary\",\"packets\":%" PRIu64 ",\"missing\":%" PRIu64
        ",\"malformed\":%" PRIu64 ",\"late\":%" PRIu64 ",\"complete\":%" PRIu32
        ",\"unknown\":%" PRIu32 ",\"no_buffer\":%" PRIu32 ",\"queue_full\":%" PRIu32
        ",\"first_missing_seq\":%" PRIu32 ",\"invalid_cells\":%" PRIu32
        ",\"duplicate_cells\":%" PRIu32 "}\n",
        wire.stats().packets, wire.stats().missing, wire.stats().malformed,
        wire.stats().duplicate_or_late, sink.complete, sink.unknown, sink.no_buffer,
        sink.queue_full, wire.stats().first_missing_sequence, wire.stats().invalid_cells,
        wire.stats().duplicate_cells);
}
