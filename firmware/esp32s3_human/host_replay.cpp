#include "human_tracker.hpp"

#include <chrono>
#include <cstdio>
#include <cstdlib>
#include <cstring>
#include <vector>

#ifdef _WIN32
#include <fcntl.h>
#include <io.h>
#endif

namespace {

#pragma pack(push, 1)
struct FrameHeader {
    uint32_t seq;
    float dt_sec;
    uint32_t count;
};

struct CellRecord {
    uint16_t cell;
    uint16_t reserved;
    float x;
    float y;
    float z;
};
#pragma pack(pop)

static_assert(sizeof(FrameHeader) == 12, "FrameHeader must be 12 bytes");
static_assert(sizeof(CellRecord) == 16, "CellRecord must be 16 bytes");

// Static workspace mirroring ESP32-S3 SRAM/PSRAM static allocation (zero malloc in loop)
static human_s3::Point3f g_points[human_s3::kCells];
static uint16_t g_cur_range_mm[human_s3::kCells];
static uint16_t g_bg_far_mm[human_s3::kCells];
static uint16_t g_prev_range_mm[human_s3::kCells];
static uint8_t g_cell_flags[human_s3::kCells];
static uint16_t g_bfs_queue[human_s3::kCells];

}  // namespace

int main(int argc, char** argv) {
#ifdef _WIN32
    _setmode(_fileno(stdin), _O_BINARY);
#endif

    human_s3::Config cfg{};
    bool has_gravity = false;
    float pitch_deg = 0.0f;
    float roll_deg = 0.0f;

    for (int i = 1; i < argc; ++i) {
        if (std::strcmp(argv[i], "--pitch-deg") == 0 && i + 1 < argc) {
            pitch_deg = std::strtof(argv[++i], nullptr);
        } else if (std::strcmp(argv[i], "--roll-deg") == 0 && i + 1 < argc) {
            roll_deg = std::strtof(argv[++i], nullptr);
        } else if (std::strcmp(argv[i], "--gravity") == 0 && i + 3 < argc) {
            cfg.gravity_up.x = std::strtof(argv[++i], nullptr);
            cfg.gravity_up.y = std::strtof(argv[++i], nullptr);
            cfg.gravity_up.z = std::strtof(argv[++i], nullptr);
            has_gravity = true;
        }
    }
    if (!has_gravity) {
        cfg.gravity_up = human_s3::Config::gravity_up_from_pitch_roll(pitch_deg, roll_deg);
    }

    human_s3::Workspace ws{};
    ws.points = g_points;
    ws.cur_range_mm = g_cur_range_mm;
    ws.bg_far_mm = g_bg_far_mm;
    ws.prev_range_mm = g_prev_range_mm;
    ws.cell_flags = g_cell_flags;
    ws.bfs_queue = g_bfs_queue;

    human_s3::HumanTracker tracker(ws, cfg);

    std::printf("{\"type\":\"init\",\"workspace_bytes\":%zu,\"tracker_object_bytes\":%zu,"
                "\"gravity_up\":[%.6f,%.6f,%.6f]}\n",
                human_s3::HumanTracker::workspace_bytes(),
                human_s3::HumanTracker::tracker_object_bytes(),
                cfg.gravity_up.x, cfg.gravity_up.y, cfg.gravity_up.z);

    std::vector<CellRecord> buf;
    FrameHeader hdr{};
    human_s3::FrameResult res{};

    while (std::fread(&hdr, sizeof(hdr), 1, stdin) == 1) {
        if (hdr.count == 0xFFFFFFFFu) {
            break;
        }
        if (hdr.count > human_s3::kCells * 4u) {
            std::fprintf(stderr, "invalid cell count %u\n", hdr.count);
            return 2;
        }
        buf.resize(hdr.count);
        if (hdr.count > 0) {
            if (std::fread(buf.data(), sizeof(CellRecord), hdr.count, stdin) != hdr.count) {
                std::fprintf(stderr, "truncated frame payload\n");
                return 3;
            }
        }

        const auto t0 = std::chrono::steady_clock::now();
        tracker.begin_frame();
        for (const auto& rec : buf) {
            tracker.set_cell(rec.cell, rec.x, rec.y, rec.z);
        }
        tracker.step(hdr.dt_sec, res);
        const auto t1 = std::chrono::steady_clock::now();
        const double step_us =
            std::chrono::duration<double, std::micro>(t1 - t0).count();

        std::printf("{\"type\":\"frame\",\"seq\":%u,\"frame\":%d,\"step_us\":%.1f,"
                    "\"valid_cells\":%d,\"fg_seeds\":%d,\"candidates\":%d,\"tracks\":[",
                    hdr.seq, res.frame_index, step_us,
                    res.valid_cells, res.fg_seed_cells, res.candidate_count);
        for (int i = 0; i < res.track_count; ++i) {
            const auto& tr = res.tracks[i];
            if (i > 0) std::printf(",");
            std::printf(
                "{\"id\":%u,\"locked\":%s,\"measured\":%s,\"pts\":%d,\"age\":%d,\"miss\":%d,"
                "\"box\":[%d,%d,%d,%d],\"xyz_m\":[%.4f,%.4f,%.4f],\"range_m\":%.3f,"
                "\"height_m\":%.3f,\"horiz_m\":%.3f,\"aspect\":%.2f,"
                "\"h_p05\":%.3f,\"h_p50\":%.3f,\"h_p95\":%.3f,"
                "\"base_ok\":%s,\"base_top\":%.3f,\"drop_m\":%.3f,"
                "\"vel\":%.3f,\"acc\":%.3f,\"pk_dv\":%.3f,\"pk_da\":%.3f,\"pk_ba\":%.3f,"
                "\"hspd\":%.3f,\"disp\":%.3f,\"low_s\":%.2f,\"still_sec\":%.2f,"
                "\"state\":\"%s\",\"reason\":\"%s\"}",
                tr.track_id, tr.locked_human ? "true" : "false",
                tr.measured_this_frame ? "true" : "false",
                tr.point_count, tr.age_frames, tr.miss_frames,
                tr.box_r0, tr.box_c0, tr.box_r1, tr.box_c1,
                tr.center.x, tr.center.y, tr.center.z, tr.range_m,
                tr.height_m, tr.horiz_span_m, tr.aspect,
                tr.h_p05, tr.h_p50, tr.h_p95,
                tr.baseline_ready ? "true" : "false", tr.baseline_top_h, tr.drop_top_m,
                tr.vel_top_mps, tr.acc_top_mps2,
                tr.peak_down_vel_mps, tr.peak_down_acc_mps2, tr.peak_brake_acc_mps2,
                tr.horiz_speed_mps, tr.net_disp_m, tr.low_posture_sec, tr.still_sec,
                human_s3::fall_state_name(tr.fall_state),
                human_s3::fall_reason_name(tr.fall_reason));
        }
        std::printf("]}\n");
    }

    std::fflush(stdout);
    return 0;
}
