#pragma once

#include <cstddef>
#include <cstdint>

namespace human_s3 {

constexpr int kWidth = 256;
constexpr int kHeight = 192;
constexpr int kCells = kWidth * kHeight;
constexpr int kMaxCandidates = 16;
constexpr int kMaxTracks = 8;
constexpr int kKinematicWindow = 20;  // ~2.0 s at 10 Hz
constexpr int kHistBins = 128;        // 2 cm per bin -> 2.56 m span

struct Vec3f {
    float x = 0.0f;
    float y = 0.0f;
    float z = 0.0f;
};

struct Point3f {
    float x = 0.0f;
    float y = 0.0f;
    float z = 0.0f;
};

// All buffers are externally supplied (SRAM / PSRAM on ESP32-S3, static on host).
// Zero heap allocation inside HumanTracker::step().
struct Workspace {
    Point3f* points = nullptr;          // kCells * 12 B = 576 KB (PSRAM)
    uint16_t* cur_range_mm = nullptr;   // kCells * 2 B  =  96 KB (SRAM/PSRAM)
    uint16_t* bg_far_mm = nullptr;      // kCells * 2 B  =  96 KB (PSRAM)
    uint16_t* prev_range_mm = nullptr;  // kCells * 2 B  =  96 KB (PSRAM)
    uint8_t* cell_flags = nullptr;      // kCells * 1 B  =  48 KB (SRAM)
    uint16_t* bfs_queue = nullptr;      // kCells * 2 B  =  96 KB (PSRAM)

    static constexpr size_t total_bytes() {
        return static_cast<size_t>(kCells) *
               (sizeof(Point3f) + sizeof(uint16_t) * 4 + sizeof(uint8_t));
    }
};

struct Config {
    // Unit vector pointing opposite to gravity (upward in world).
    // Supplied by IFW192S IMU low-pass average or known mount pitch/roll.
    // No ground plane offset or empty-room ground fitting is required.
    Vec3f gravity_up = {0.0f, 0.0f, 1.0f};

    uint16_t min_range_mm = 350;
    uint16_t max_range_mm = 8000;
    uint16_t fg_margin_mm = 220;       // Foreground delta vs far-bg or prev-frame
    uint16_t bfs_step_mm = 200;        // Max depth jump between 8-neighbors in BFS
    uint16_t retain_margin_mm = 450;   // Depth gate when retaining locked track

    int min_cluster_points = 80;
    float max_cluster_span_m = 2.35f;  // Prevent wall merging

    // Human lock thresholds (geometry + motion, no empty-room assumption)
    int lock_min_frames = 3;
    int human_min_lock_points = 260;
    int human_max_bottom_row = 98;
    float human_min_upright_h_m = 0.90f;
    float human_max_upright_h_m = 2.15f;
    float human_min_horiz_m = 0.15f;
    float human_max_horiz_m = 1.15f;
    float human_min_vertical_fill = 0.72f;
    float human_max_vertical_gap_m = 0.14f;
    float human_min_iqr_ratio = 0.28f;
    float human_min_third_ratio = 0.10f;
    uint16_t motion_depth_mm = 120;
    float motion_window_sec = 1.30f;
    float motion_lock_disp_m = 0.11f;
    float human_max_speed_mps = 3.5f;
    float still_hold_sec = 25.0f;
    float suspected_hold_sec = 12.0f;

    // Kinematics + posture collapse fall-candidate thresholds
    float fast_down_vel_mps = 0.70f;
    float fast_acc_mps2 = 2.00f;
    float fast_drop_m = 0.75f;

    float slow_down_vel_mps = 0.25f;
    float slow_drop_m = 0.80f;

    float collapsed_min_height_m = 0.14f;
    float collapsed_height_m = 0.55f;
    float collapsed_aspect_max = 0.55f;
    float very_low_height_m = 0.45f;
    float fall_hold_sec = 1.20f;

    float recover_height_m = 1.02f;
    float recover_drop_m = 0.35f;

    // Track association & timeout
    float assoc_horiz_m = 0.85f;
    float assoc_3d_m = 1.15f;
    int max_miss_frames = 8;

    // Helper: construct gravity_up from sensor mount pitch/roll in degrees
    // (pitch > 0 means sensor nose tilted downward toward floor).
    static Vec3f gravity_up_from_pitch_roll(float pitch_deg, float roll_deg);
};

enum class FallState : uint8_t {
    kUnknown = 0,
    kUpright = 1,
    kFalling = 2,
    kFallSuspected = 3,
};

enum class FallReason : uint8_t {
    kNone = 0,
    kFastKinematic = 1,
    kSlowDescent = 2,
};

struct TrackSnapshot {
    uint32_t track_id = 0;
    bool locked_human = false;
    bool measured_this_frame = false;
    int point_count = 0;
    int age_frames = 0;
    int miss_frames = 0;

    int box_r0 = 0, box_c0 = 0, box_r1 = 0, box_c1 = 0;
    Vec3f center = {};
    float range_m = 0.0f;

    // Gravity-projected posture metrics (no ground offset needed)
    float h_p05 = 0.0f;
    float h_p50 = 0.0f;
    float h_p95 = 0.0f;
    float height_m = 0.0f;
    float horiz_span_m = 0.0f;
    float aspect = 0.0f;

    // Personal upright baseline & relative drop
    bool baseline_ready = false;
    float baseline_top_h = 0.0f;
    float baseline_height = 0.0f;
    float drop_top_m = 0.0f;

    // Filtered vertical kinematics (top-of-body P95 along gravity_up)
    float vel_top_mps = 0.0f;
    float acc_top_mps2 = 0.0f;
    float peak_down_vel_mps = 0.0f;
    float peak_down_acc_mps2 = 0.0f;
    float peak_brake_acc_mps2 = 0.0f;
    float horiz_speed_mps = 0.0f;
    float net_disp_m = 0.0f;

    float low_posture_sec = 0.0f;
    float still_sec = 0.0f;
    FallState fall_state = FallState::kUnknown;
    FallReason fall_reason = FallReason::kNone;
};

struct FrameResult {
    int frame_index = 0;
    int valid_cells = 0;
    int fg_seed_cells = 0;
    int candidate_count = 0;
    int track_count = 0;
    TrackSnapshot tracks[kMaxTracks];
};

class HumanTracker {
public:
    HumanTracker(const Workspace& ws, const Config& cfg);

    void reset();
    void set_gravity_up(Vec3f gravity_up);

    // Prepare frame buffer: clears cur_range_mm to 0 before caller fills valid cells.
    void begin_frame();

    // Populate one measured cell in native ring/col order (0 <= cell < kCells).
    void set_cell(uint16_t cell, float x, float y, float z);

    // Fast path when caller already computed range in millimeters (avoids sqrtf).
    void set_cell_range_mm(uint16_t cell, float x, float y, float z, uint16_t r_mm);

    // Run background-free segmentation, tracking, kinematics, and fall state machine.
    // dt_sec is elapsed time since previous frame. A long gap breaks track continuity.
    void step(float dt_sec, FrameResult& out);

    static constexpr size_t workspace_bytes() { return Workspace::total_bytes(); }
    static constexpr size_t tracker_object_bytes() { return sizeof(HumanTracker); }

private:
    struct Candidate {
        int point_count = 0;
        int motion_points = 0;
        int motion_lower = 0;
        int motion_upper = 0;
        int owned_points = 0;
        int r0 = 0, c0 = 0, r1 = 0, c1 = 0;
        Vec3f center = {};
        float cu = 0.0f, cv = 0.0f, ch = 0.0f;
        float range_m = 0.0f;
        float h_p05 = 0.0f, h_p50 = 0.0f, h_p95 = 0.0f;
        float height_m = 0.0f;
        float iqr_height_m = 0.0f;
        float vertical_fill = 0.0f;
        float max_vertical_gap_m = 0.0f;
        float min_third_ratio = 0.0f;
        float horiz_span_m = 0.0f;
        float aspect = 0.0f;
        bool from_retain = false;
        int retain_track_slot = -1;
    };

    struct KinSample {
        float dt = 0.1f;
        float down_vel = 0.0f;
        float down_acc = 0.0f;
        float brake_acc = 0.0f;
        float drop_top = 0.0f;
    };

    struct MotionWindow {
        Vec3f origin = {};
        float seconds = 0.0f;
        float path_m = 0.0f;
        int moving_steps = 0;
        int depth_frames = 0;
    };

    struct Track {
        bool active = false;
        uint32_t id = 0;
        bool locked_human = false;
        bool measured_this_frame = false;
        int age_frames = 0;
        int miss_frames = 0;
        int upright_frames = 0;
        float still_sec = 0.0f;
        float renewal_top_h = 0.0f;
        float missed_sec = 0.0f;
        float suspected_sec = 0.0f;
        MotionWindow motion;

        int box_r0 = 0, box_c0 = 0, box_r1 = 0, box_c1 = 0;
        int point_count = 0;
        Vec3f center = {};
        float cu = 0.0f, cv = 0.0f, ch = 0.0f;
        float start_cu = 0.0f, start_cv = 0.0f;
        float vel_u = 0.0f, vel_v = 0.0f;
        float range_m = 0.0f;

        float h_p05 = 0.0f, h_p50 = 0.0f, h_p95 = 0.0f;
        float height_m = 0.0f;
        float horiz_span_m = 0.0f;
        float aspect = 0.0f;

        bool baseline_ready = false;
        float baseline_top_h = 0.0f;
        float baseline_height = 0.0f;

        // Alpha-beta-gamma filter for h_p95
        bool filter_init = false;
        float f_top_h = 0.0f;
        float f_top_v = 0.0f;
        float f_top_a = 0.0f;

        // Sliding kinematic history ring buffer
        KinSample history[kKinematicWindow];
        int hist_head = 0;
        int hist_count = 0;

        float peak_down_vel = 0.0f;
        float peak_down_acc = 0.0f;
        float peak_brake_acc = 0.0f;
        float drop_top_m = 0.0f;

        float low_posture_sec = 0.0f;
        FallState fall_state = FallState::kUnknown;
        FallReason fall_reason = FallReason::kNone;
    };

    void rebuild_basis();
    bool grow_cluster(uint16_t seed_cell, int retain_slot, uint16_t ref_mm,
                      int candidate_index, Candidate& cand);
    bool upright_geometry(const Candidate& cand) const;
    float association_distance_squared(const Track& tr, const Candidate& cand, float dt) const;
    void update_track_from_candidate(Track& tr, const Candidate& cand, float dt);
    void update_kinematics_and_fall(Track& tr, float dt, float observed_dt);
    void update_background(const uint8_t* candidate_owners);

    Workspace ws_;
    Config cfg_;
    Vec3f g_up_ = {0.0f, 0.0f, 1.0f};
    Vec3f u_axis_ = {1.0f, 0.0f, 0.0f};
    Vec3f v_axis_ = {0.0f, 1.0f, 0.0f};

    int frame_index_ = 0;
    uint32_t next_track_id_ = 1;
    Track tracks_[kMaxTracks];
};

const char* fall_state_name(FallState state);
const char* fall_reason_name(FallReason reason);

}  // namespace human_s3
