#include "human_tracker.hpp"

#include <algorithm>
#include <cmath>
#include <cstring>

namespace human_s3 {

namespace {

constexpr uint8_t kFlagFgSeed = 1u << 0;
constexpr uint8_t kFlagVisited = 1u << 1;
constexpr uint8_t kFlagMotion = 1u << 2;
constexpr uint8_t kFlagCandidate = 1u << 3;
// High nibble: previous owning track slot + 1, or current candidate index
// once that measured cell has been assigned by BFS.
constexpr int kOwnerShift = 4;
constexpr uint8_t kOwnerMask = 0xf0;
constexpr int kShortMissFrames = 2;

constexpr float kPi = 3.14159265358979323846f;

inline float dot3(Vec3f a, Vec3f b) {
    return a.x * b.x + a.y * b.y + a.z * b.z;
}

inline float dot3_pt(Point3f a, Vec3f b) {
    return a.x * b.x + a.y * b.y + a.z * b.z;
}

inline Vec3f cross3(Vec3f a, Vec3f b) {
    return {
        a.y * b.z - a.z * b.y,
        a.z * b.x - a.x * b.z,
        a.x * b.y - a.y * b.x,
    };
}

inline Vec3f normalize3(Vec3f v) {
    const float n = std::sqrt(dot3(v, v));
    if (n < 1e-6f) {
        return {0.0f, 0.0f, 1.0f};
    }
    const float inv = 1.0f / n;
    return {v.x * inv, v.y * inv, v.z * inv};
}

inline int abs_diff_u16(uint16_t a, uint16_t b) {
    return a >= b ? static_cast<int>(a - b) : static_cast<int>(b - a);
}

}  // namespace

Vec3f Config::gravity_up_from_pitch_roll(float pitch_deg, float roll_deg) {
    const float p = pitch_deg * (kPi / 180.0f);
    const float r = roll_deg * (kPi / 180.0f);
    // Sensor tilted downward by pitch_deg around +Y, roll_deg around +X.
    // World up in sensor frame: (-sin(p), -cos(p)*sin(r), cos(p)*cos(r)).
    const float cp = std::cos(p);
    return normalize3({-std::sin(p), -cp * std::sin(r), cp * std::cos(r)});
}

const char* fall_state_name(FallState state) {
    switch (state) {
        case FallState::kUpright: return "UPRIGHT";
        case FallState::kFalling: return "FALLING";
        case FallState::kFallSuspected: return "FALL_SUSPECTED";
        case FallState::kUnknown:
        default: return "UNKNOWN";
    }
}

const char* fall_reason_name(FallReason reason) {
    switch (reason) {
        case FallReason::kFastKinematic: return "FAST_KINEMATIC";
        case FallReason::kSlowDescent: return "SLOW_DESCENT";
        case FallReason::kNone:
        default: return "NONE";
    }
}

HumanTracker::HumanTracker(const Workspace& ws, const Config& cfg)
    : ws_(ws), cfg_(cfg) {
    set_gravity_up(cfg_.gravity_up);
    reset();
}

void HumanTracker::set_gravity_up(Vec3f gravity_up) {
    g_up_ = normalize3(gravity_up);
    rebuild_basis();
}

void HumanTracker::rebuild_basis() {
    // Choose a reference vector not parallel to g_up_
    const Vec3f ref = (std::fabs(g_up_.x) < 0.8f) ? Vec3f{1.0f, 0.0f, 0.0f}
                                                  : Vec3f{0.0f, 1.0f, 0.0f};
    v_axis_ = normalize3(cross3(g_up_, ref));
    u_axis_ = normalize3(cross3(v_axis_, g_up_));
}

void HumanTracker::reset() {
    frame_index_ = 0;
    next_track_id_ = 1;
    for (int t = 0; t < kMaxTracks; ++t) {
        tracks_[t] = Track{};
    }
    if (ws_.cur_range_mm) std::memset(ws_.cur_range_mm, 0, sizeof(uint16_t) * kCells);
    if (ws_.bg_far_mm) std::memset(ws_.bg_far_mm, 0, sizeof(uint16_t) * kCells);
    if (ws_.prev_range_mm) std::memset(ws_.prev_range_mm, 0, sizeof(uint16_t) * kCells);
    if (ws_.cell_flags) std::memset(ws_.cell_flags, 0, sizeof(uint8_t) * kCells);
}

void HumanTracker::begin_frame() {
    std::memset(ws_.cur_range_mm, 0, sizeof(uint16_t) * kCells);
}

void HumanTracker::set_cell(uint16_t cell, float x, float y, float z) {
    if (cell >= kCells) return;
    const float r2 = x * x + y * y + z * z;
    if (!(r2 > 0.01f)) return;
    const float r_mm_f = std::sqrt(r2) * 1000.0f;
    if (r_mm_f < static_cast<float>(cfg_.min_range_mm) ||
        r_mm_f > static_cast<float>(cfg_.max_range_mm)) {
        return;
    }
    const uint16_t r_mm = static_cast<uint16_t>(r_mm_f + 0.5f);
    set_cell_range_mm(cell, x, y, z, r_mm);
}

void HumanTracker::set_cell_range_mm(uint16_t cell, float x, float y, float z, uint16_t r_mm) {
    if (cell >= kCells) return;
    if (r_mm < cfg_.min_range_mm || r_mm > cfg_.max_range_mm) return;
    // Nearest-return tie-break if multiple returns hit same cell
    if (ws_.cur_range_mm[cell] == 0 || r_mm < ws_.cur_range_mm[cell]) {
        ws_.cur_range_mm[cell] = r_mm;
        ws_.points[cell] = {x, y, z};
    }
}

bool HumanTracker::grow_cluster(uint16_t seed_cell, int retain_slot,
                                uint16_t ref_mm, int candidate_index, Candidate& cand) {
    static constexpr int dr[8] = {-1, -1, -1, 0, 0, 1, 1, 1};
    static constexpr int dc[8] = {-1, 0, 1, -1, 1, -1, 0, 1};

    const Point3f seed_pt = ws_.points[seed_cell];
    const float seed_u = dot3_pt(seed_pt, u_axis_);
    const float seed_v = dot3_pt(seed_pt, v_axis_);
    const float max_horiz_r2 = 1.15f * 1.15f;  // Bound growth radius from seed

    int box_r0 = 0, box_c0 = 0, box_r1 = kHeight - 1, box_c1 = kWidth - 1;
    const bool retain_mode = retain_slot >= 0;
    if (retain_mode) {
        const Track& tr = tracks_[retain_slot];
        const int row_pad = tr.locked_human &&
            (tr.drop_top_m >= 0.30f || std::fabs(tr.f_top_v) >= 0.35f) ? 24 : 16;
        box_r0 = std::max(0, tr.box_r0 - row_pad);
        box_c0 = std::max(0, tr.box_c0 - 16);
        box_r1 = std::min(kHeight - 1, tr.box_r1 + row_pad);
        box_c1 = std::min(kWidth - 1, tr.box_c1 + 16);
    }

    int head = 0;
    int tail = 0;
    ws_.bfs_queue[tail++] = seed_cell;
    ws_.cell_flags[seed_cell] |= kFlagVisited;

    float sum_x = 0.0f, sum_y = 0.0f, sum_z = 0.0f;
    float sum_u = 0.0f, sum_v = 0.0f, sum_h = 0.0f;
    float sum_r = 0.0f;
    float h_min = 1e9f, h_max = -1e9f;
    float u_min = 1e9f, u_max = -1e9f;
    float v_min = 1e9f, v_max = -1e9f;
    int r0 = kHeight, c0 = kWidth, r1 = -1, c1 = -1;
    int motion_points = 0;
    int owned_points = 0;

    while (head < tail) {
        const uint16_t cur = ws_.bfs_queue[head++];
        const int cr = cur >> 8;
        const int cc = cur & 255;
        const uint16_t cur_mm = ws_.cur_range_mm[cur];
        const Point3f pt = ws_.points[cur];
        const uint8_t cell_flags = ws_.cell_flags[cur];
        if (cell_flags & kFlagMotion) ++motion_points;
        if (retain_mode && (cell_flags >> kOwnerShift) == retain_slot + 1) ++owned_points;

        const float pu = dot3_pt(pt, u_axis_);
        const float pv = dot3_pt(pt, v_axis_);
        const float ph = dot3_pt(pt, g_up_);

        sum_x += pt.x;
        sum_y += pt.y;
        sum_z += pt.z;
        sum_u += pu;
        sum_v += pv;
        sum_h += ph;
        sum_r += static_cast<float>(cur_mm) * 0.001f;

        if (ph < h_min) h_min = ph;
        if (ph > h_max) h_max = ph;
        if (pu < u_min) u_min = pu;
        if (pu > u_max) u_max = pu;
        if (pv < v_min) v_min = pv;
        if (pv > v_max) v_max = pv;
        if (cr < r0) r0 = cr;
        if (cr > r1) r1 = cr;
        if (cc < c0) c0 = cc;
        if (cc > c1) c1 = cc;

        for (int k = 0; k < 8; ++k) {
            const int nr = cr + dr[k];
            const int nc = cc + dc[k];
            if (nr < box_r0 || nr > box_r1 || nc < box_c0 || nc > box_c1) continue;
            const uint16_t nb = static_cast<uint16_t>((nr << 8) | nc);
            if (ws_.cell_flags[nb] & kFlagVisited) continue;
            const uint16_t nb_mm = ws_.cur_range_mm[nb];
            if (nb_mm == 0) continue;

            // Depth continuity gate
            if (abs_diff_u16(nb_mm, cur_mm) > cfg_.bfs_step_mm) continue;

            // Prevent bleeding into static background wall/floor:
            // Grow across foreground pixels, pixels clearly closer than bg_far_mm,
            // or (only in retain mode for locked humans) previously covered body pixels
            // within tight depth proximity of ref_mm.
            const uint16_t bg_mm = ws_.bg_far_mm[nb];
            const bool is_fg = (ws_.cell_flags[nb] & kFlagFgSeed) != 0;
            const bool was_owned = (ws_.cell_flags[nb] >> kOwnerShift) == retain_slot + 1;
            if (!is_fg) {
                const bool tight_retain_body =
                    retain_mode && was_owned && (abs_diff_u16(nb_mm, ref_mm) <= 300);
                if (!tight_retain_body && bg_mm > 0 && nb_mm + 140 >= bg_mm) {
                    continue;
                }
            }

            if (retain_mode && abs_diff_u16(nb_mm, ref_mm) > cfg_.retain_margin_mm + 350) {
                continue;
            }

            // Physical horizontal radius cap around seed to avoid creeping across floor
            const Point3f npt = ws_.points[nb];
            const float du = dot3_pt(npt, u_axis_) - seed_u;
            const float dv = dot3_pt(npt, v_axis_) - seed_v;
            if (du * du + dv * dv > max_horiz_r2) continue;

            ws_.cell_flags[nb] |= kFlagVisited;
            if (tail < kCells) {
                ws_.bfs_queue[tail++] = nb;
            }
        }
    }

    if (tail < cfg_.min_cluster_points) {
        return false;
    }

    const float u_span = u_max - u_min;
    const float v_span = v_max - v_min;
    const float raw_h_span = h_max - h_min;
    if (u_span > cfg_.max_cluster_span_m || v_span > cfg_.max_cluster_span_m ||
        raw_h_span > cfg_.max_cluster_span_m) {
        return false;
    }

    // O(N) fixed-bin histogram for robust P05 / P50 / P95 height along gravity_up
    uint16_t hist[kHistBins];
    std::memset(hist, 0, sizeof(hist));
    constexpr float kBinSize = 0.02f;  // 2 cm
    constexpr float kInvBin = 1.0f / kBinSize;

    for (int i = 0; i < tail; ++i) {
        const uint16_t cell = ws_.bfs_queue[i];
        const float ph = dot3_pt(ws_.points[cell], g_up_);
        int b = static_cast<int>((ph - h_min) * kInvBin);
        if (b < 0) b = 0;
        if (b >= kHistBins) b = kHistBins - 1;
        hist[b]++;
    }

    const int target_05 = std::max(1, (tail * 5) / 100);
    const int target_50 = std::max(1, tail / 2);
    const int target_95 = std::max(1, (tail * 95) / 100);
    int acc = 0;
    float hp05 = h_min, hp50 = h_min, hp95 = h_max;
    bool got05 = false, got50 = false, got95 = false;
    for (int b = 0; b < kHistBins; ++b) {
        acc += hist[b];
        const float h_val = h_min + (static_cast<float>(b) + 0.5f) * kBinSize;
        if (!got05 && acc >= target_05) { hp05 = h_val; got05 = true; }
        if (!got50 && acc >= target_50) { hp50 = h_val; got50 = true; }
        if (!got95 && acc >= target_95) { hp95 = h_val; got95 = true; break; }
    }

    const float inv_n = 1.0f / static_cast<float>(tail);
    cand.point_count = tail;
    cand.motion_points = motion_points;
    cand.owned_points = owned_points;
    cand.r0 = r0;
    cand.c0 = c0;
    cand.r1 = r1;
    cand.c1 = c1;
    cand.center = {sum_x * inv_n, sum_y * inv_n, sum_z * inv_n};
    cand.cu = sum_u * inv_n;
    cand.cv = sum_v * inv_n;
    cand.ch = sum_h * inv_n;
    cand.range_m = sum_r * inv_n;
    cand.h_p05 = hp05;
    cand.h_p50 = hp50;
    cand.h_p95 = hp95;
    cand.height_m = std::max(0.0f, hp95 - hp05);
    cand.horiz_span_m = std::max(u_span, v_span);
    cand.aspect = cand.height_m / std::max(cand.horiz_span_m, 0.15f);
    cand.from_retain = retain_mode;
    cand.retain_track_slot = retain_slot;

    for (int i = 0; i < tail; ++i) {
        uint8_t& flags = ws_.cell_flags[ws_.bfs_queue[i]];
        flags = (flags & ~kOwnerMask) | kFlagCandidate | (candidate_index << kOwnerShift);
    }
    return true;
}

bool HumanTracker::upright_geometry(const Candidate& cand) const {
    const bool high_edge = (cand.r0 <= 1 || cand.r1 >= kHeight - 2) && cand.h_p05 > 0.0f;
    return !high_edge && cand.height_m >= cfg_.human_min_upright_h_m &&
           cand.height_m <= cfg_.human_max_upright_h_m &&
           cand.horiz_span_m <= cfg_.human_max_horiz_m && cand.aspect >= 1.05f;
}

float HumanTracker::association_distance_squared(const Track& tr, const Candidate& cand,
                                                 float dt) const {
    const float horizon = dt + tr.missed_sec;
    const float du = cand.cu - (tr.cu + tr.vel_u * horizon);
    const float dv = cand.cv - (tr.cv + tr.vel_v * horizon);
    const float dh = cand.ch - tr.ch;
    const float horizontal_sq = du * du + dv * dv;
    const float horizontal_limit = std::min(cfg_.assoc_horiz_m, 0.22f + cfg_.human_max_speed_mps * horizon);
    if (horizontal_sq > horizontal_limit * horizontal_limit) return INFINITY;

    bool postural_match = false;
    if (tr.locked_human) {
        const bool columns_overlap = cand.c0 <= tr.box_c1 && tr.box_c0 <= cand.c1;
        const bool rising = cand.h_p95 >= tr.h_p95 + 0.12f;
        const bool low_track = tr.drop_top_m >= 0.35f || tr.fall_state == FallState::kFalling ||
                               tr.fall_state == FallState::kFallSuspected;
        postural_match = low_track && columns_overlap && horizontal_sq <= 0.45f * 0.45f &&
                         std::fabs(cand.range_m - tr.range_m) <= 0.65f;
        const bool covers_body = cand.height_m >= 0.60f && cand.horiz_span_m >= cfg_.human_min_horiz_m;
        const bool covers_low_body = tr.baseline_ready && cand.height_m >= cfg_.collapsed_min_height_m &&
                                     cand.horiz_span_m >= 0.50f &&
                                     cand.h_p95 <= tr.baseline_top_h - 0.45f &&
                                     cand.h_p05 <= tr.h_p05 + (postural_match && rising ? 0.50f : 0.30f);
        const bool covers_rising_body = postural_match && rising && cand.height_m >= 0.42f &&
                                        cand.horiz_span_m >= 0.28f && cand.h_p95 <= tr.baseline_top_h + 0.20f;
        if (!covers_body && !covers_low_body && !covers_rising_body) return INFINITY;
        // A sudden loss of the bottom half without downward motion is usually a split.
        if (cand.h_p05 > tr.h_p05 + 0.42f && cand.height_m < 0.72f * tr.height_m &&
            cand.h_p95 > tr.h_p95 - 0.22f && !covers_rising_body) return INFINITY;
    } else if (!upright_geometry(cand)) {
        return INFINITY;
    }

    const float distance_sq = horizontal_sq + (postural_match ? 0.25f : 1.0f) * dh * dh;
    const float limit_3d = std::min(cfg_.assoc_3d_m, 0.32f + 4.0f * horizon);
    return distance_sq <= limit_3d * limit_3d ? distance_sq : INFINITY;
}

void HumanTracker::update_track_from_candidate(Track& tr, const Candidate& cand,
                                               float dt) {
    const bool continuous = tr.age_frames > 0 && tr.miss_frames == 0;
    const float elapsed = dt + tr.missed_sec;
    const bool upright = upright_geometry(cand);
    const Vec3f delta = {cand.cu - tr.cu, cand.cv - tr.cv, cand.ch - tr.ch};
    const float step_m = continuous ? std::sqrt(dot3(delta, delta)) : 0.0f;
    const Vec3f position = {cand.cu, cand.cv, cand.ch};
    MotionWindow& motion = tr.motion;
    bool moving = false;
    if (!upright || !continuous || motion.seconds + dt > cfg_.motion_window_sec ||
        step_m > cfg_.human_max_speed_mps * dt || std::fabs(cand.height_m - tr.height_m) > 0.26f) {
        motion = MotionWindow{position};
        tr.upright_frames = 0;
    } else if (tr.upright_frames > 0) {
        motion.seconds += dt;
        motion.path_m += step_m;
        if (step_m >= 0.012f) ++motion.moving_steps;
        const float range_step = std::fabs(cand.range_m - tr.range_m);
        const bool radial_motion = range_step >= std::max(0.025f, 0.70f * step_m) &&
                                   std::fabs(cand.height_m - tr.height_m) <= 0.10f &&
                                   std::abs(cand.point_count - tr.point_count) <= tr.point_count / 6;
        if (radial_motion || cand.motion_points >= std::max(4, cand.point_count / 100)) {
            ++motion.depth_frames;
        }
        const Vec3f net = {position.x - motion.origin.x, position.y - motion.origin.y,
                           position.z - motion.origin.z};
        const float displacement = std::sqrt(dot3(net, net));
        const float min_displacement = tr.locked_human ? 0.075f : cfg_.motion_lock_disp_m;
        moving = motion.moving_steps >= 2 && motion.depth_frames >= 2 &&
                 displacement >= min_displacement && displacement >= 0.60f * motion.path_m;
    }
    if (upright) {
        if (tr.upright_frames < cfg_.lock_min_frames) ++tr.upright_frames;
        if (moving && tr.upright_frames >= cfg_.lock_min_frames &&
            cand.horiz_span_m >= cfg_.human_min_horiz_m) {
            motion = MotionWindow{position};
            if (!tr.locked_human) {
                tr.locked_human = true;
                tr.fall_state = FallState::kUpright;
            }
            tr.still_sec = 0.0f;
            tr.renewal_top_h = cand.h_p95;
        }
    }

    if (tr.age_frames == 0) {
        tr.start_cu = cand.cu;
        tr.start_cv = cand.cv;
        tr.vel_u = 0.0f;
        tr.vel_v = 0.0f;
    } else if (continuous) {
        const float raw_vu = (cand.cu - tr.cu) / dt;
        const float raw_vv = (cand.cv - tr.cv) / dt;
        tr.vel_u = 0.65f * tr.vel_u + 0.35f * raw_vu;
        tr.vel_v = 0.65f * tr.vel_v + 0.35f * raw_vv;
    }

    tr.measured_this_frame = true;
    tr.miss_frames = 0;
    tr.missed_sec = 0.0f;
    tr.age_frames += 1;
    tr.point_count = cand.point_count;
    tr.box_r0 = cand.r0;
    tr.box_c0 = cand.c0;
    tr.box_r1 = cand.r1;
    tr.box_c1 = cand.c1;
    tr.center = cand.center;
    tr.cu = cand.cu;
    tr.cv = cand.cv;
    tr.ch = cand.ch;
    tr.range_m = cand.range_m;
    tr.h_p05 = cand.h_p05;
    tr.h_p50 = cand.h_p50;
    tr.h_p95 = cand.h_p95;
    tr.height_m = cand.height_m;
    tr.horiz_span_m = cand.horiz_span_m;
    tr.aspect = cand.aspect;

    // Learn the baseline from qualified upright observations of this track.
    if (upright && tr.fall_state != FallState::kFalling &&
        tr.fall_state != FallState::kFallSuspected) {
        if (!tr.baseline_ready) {
            tr.baseline_top_h = cand.h_p95;
            tr.baseline_height = cand.height_m;
            tr.baseline_ready = true;
        } else {
            // Slow EMA upward/steady tracking; do not pull baseline down during descent
            const float alpha = (cand.h_p95 >= tr.baseline_top_h - 0.10f) ? 0.12f : 0.02f;
            tr.baseline_top_h = (1.0f - alpha) * tr.baseline_top_h + alpha * cand.h_p95;
            tr.baseline_height = (1.0f - alpha) * tr.baseline_height + alpha * cand.height_m;
        }
    }

    update_kinematics_and_fall(tr, elapsed, continuous ? dt : 0.0f);
    // Sustained, measured vertical motion can renew an established lock during a bend or rise.
    if (tr.locked_human && continuous && std::fabs(tr.f_top_h - tr.renewal_top_h) >= 0.20f &&
        std::fabs(tr.h_p95 - tr.f_top_h) <= 0.10f && cand.horiz_span_m >= 0.28f) {
        tr.still_sec = 0.0f;
        tr.renewal_top_h = tr.f_top_h;
    }
}

void HumanTracker::update_kinematics_and_fall(Track& tr, float dt, float observed_dt) {
    // Alpha-beta-gamma filter on h_p95 for noise-tolerant 10 Hz velocity & acceleration
    if (!tr.filter_init) {
        tr.f_top_h = tr.h_p95;
        tr.f_top_v = 0.0f;
        tr.f_top_a = 0.0f;
        tr.filter_init = true;
    } else {
        const float h_pred = tr.f_top_h + tr.f_top_v * dt + 0.5f * tr.f_top_a * dt * dt;
        const float v_pred = tr.f_top_v + tr.f_top_a * dt;
        const float resid = tr.h_p95 - h_pred;

        constexpr float kAlpha = 0.52f;
        constexpr float kBeta = 0.22f;
        constexpr float kGamma = 0.045f;

        tr.f_top_h = h_pred + kAlpha * resid;
        tr.f_top_v = v_pred + (kBeta / dt) * resid;
        tr.f_top_a = tr.f_top_a + (2.0f * kGamma / (dt * dt)) * resid;

        // Clamp non-physical outliers from single-frame occlusion
        tr.f_top_v = std::max(-6.0f, std::min(6.0f, tr.f_top_v));
        tr.f_top_a = std::max(-25.0f, std::min(25.0f, tr.f_top_a));
    }

    tr.drop_top_m = tr.baseline_ready ? std::max(0.0f, tr.baseline_top_h - tr.h_p95) : 0.0f;

    // Push into sliding kinematic window
    KinSample sample{};
    sample.dt = dt;
    sample.down_vel = std::max(0.0f, -tr.f_top_v);
    sample.down_acc = std::max(0.0f, -tr.f_top_a);
    sample.brake_acc = std::max(0.0f, tr.f_top_a);
    sample.drop_top = tr.drop_top_m;

    tr.history[tr.hist_head] = sample;
    tr.hist_head = (tr.hist_head + 1) % kKinematicWindow;
    if (tr.hist_count < kKinematicWindow) tr.hist_count += 1;

    float peak_dv = 0.0f;
    float peak_da = 0.0f;
    float peak_ba = 0.0f;
    float peak_drop = 0.0f;
    for (int i = 0; i < tr.hist_count; ++i) {
        const KinSample& s = tr.history[i];
        if (s.down_vel > peak_dv) peak_dv = s.down_vel;
        if (s.down_acc > peak_da) peak_da = s.down_acc;
        if (s.brake_acc > peak_ba) peak_ba = s.brake_acc;
        if (s.drop_top > peak_drop) peak_drop = s.drop_top;
    }
    tr.peak_down_vel = peak_dv;
    tr.peak_down_acc = peak_da;
    tr.peak_brake_acc = peak_ba;

    if (!tr.locked_human || !tr.baseline_ready) {
        tr.low_posture_sec = 0.0f;
        return;
    }

    const bool is_collapsed =
        ((tr.height_m <= cfg_.collapsed_height_m && tr.aspect <= cfg_.collapsed_aspect_max) ||
         (tr.height_m <= cfg_.very_low_height_m));

    const bool fast_kin =
        (peak_dv >= cfg_.fast_down_vel_mps &&
         (peak_da >= cfg_.fast_acc_mps2 || peak_ba >= cfg_.fast_acc_mps2) &&
         tr.drop_top_m >= cfg_.fast_drop_m);

    const bool slow_kin =
        (peak_dv >= cfg_.slow_down_vel_mps && tr.drop_top_m >= cfg_.slow_drop_m);

    // Upright recovery clears fall state (filters bending / picking up items)
    if (tr.height_m >= cfg_.recover_height_m && tr.drop_top_m <= cfg_.recover_drop_m) {
        tr.fall_state = FallState::kUpright;
        tr.fall_reason = FallReason::kNone;
        tr.low_posture_sec = 0.0f;
        return;
    }

    // Intermediate rising poses do not clear an existing suspicion.
    if (tr.fall_state == FallState::kFallSuspected) {
        if (is_collapsed) tr.low_posture_sec += observed_dt;
        return;
    }

    if (is_collapsed && (fast_kin || slow_kin || tr.low_posture_sec > 0.0f)) {
        tr.low_posture_sec += observed_dt;
        if (tr.fall_reason == FallReason::kNone) {
            tr.fall_reason = fast_kin ? FallReason::kFastKinematic : FallReason::kSlowDescent;
        }
        if (tr.low_posture_sec >= cfg_.fall_hold_sec) {
            tr.fall_state = FallState::kFallSuspected;
        } else {
            tr.fall_state = FallState::kFalling;
        }
    } else {
        tr.low_posture_sec = 0.0f;
        tr.fall_reason = FallReason::kNone;
        tr.fall_state = (fast_kin || slow_kin ||
                         (tr.drop_top_m >= 0.45f && tr.f_top_v <= -0.35f))
                            ? FallState::kFalling : FallState::kUpright;
    }
}

void HumanTracker::update_background(const uint8_t* candidate_owners) {
    const Track* locked[kMaxTracks];
    int locked_count = 0;
    for (const Track& tr : tracks_) {
        if (tr.active && tr.locked_human && tr.miss_frames <= kShortMissFrames && tr.missed_sec <= 0.35f) {
            locked[locked_count++] = &tr;
        }
    }
    for (int c = 0; c < kCells; ++c) {
        const uint16_t cur = ws_.cur_range_mm[c];
        const uint8_t flags = ws_.cell_flags[c];
        const uint8_t index = flags >> kOwnerShift;
        uint8_t owner = flags & kFlagCandidate ? candidate_owners[index] : 0;
        if (!(flags & kFlagCandidate) && index != 0) {
            const Track& prior = tracks_[index - 1];
            if (prior.active && prior.locked_human && prior.miss_frames > 0 &&
                prior.miss_frames <= kShortMissFrames && prior.missed_sec <= 0.35f &&
                (cur == 0 || std::fabs(cur - 1000.0f * prior.range_m) <= 300.0f)) {
                owner = index;
            }
        }
        ws_.cell_flags[c] = owner << kOwnerShift;
        const uint16_t prev = ws_.prev_range_mm[c];
        ws_.prev_range_mm[c] = cur;
        if (cur == 0) continue;

        if (owner == 0) {
            const uint16_t bg = ws_.bg_far_mm[c];
            // Keep nearby edges of the locked return from becoming background.
            if (locked_count && (bg == 0 || cur < bg) && prev > 0 && abs_diff_u16(cur, prev) <= 150) {
                const int row = c >> 8;
                const int col = c & 255;
                bool protect = false;
                for (int i = 0; i < locked_count; ++i) {
                    const Track& tr = *locked[i];
                    if (row >= tr.box_r0 - 1 && row <= tr.box_r1 + 1 &&
                        col >= tr.box_c0 - 1 && col <= tr.box_c1 + 1 &&
                        std::fabs(cur - 1000.0f * tr.range_m) <= 300.0f) {
                        protect = true;
                        break;
                    }
                }
                if (protect) continue;
            }
            if (bg == 0) {
                // Only initialize previously missing bg cell once it is stable across frames
                if (prev > 0 && abs_diff_u16(cur, prev) <= 100) {
                    ws_.bg_far_mm[c] = cur;
                }
            } else if (cur > bg + 150) {
                // Person walked away exposing farther static wall/floor -> adopt quickly
                ws_.bg_far_mm[c] = cur;
            } else if (abs_diff_u16(cur, bg) <= 150) {
                // Slow smoothing on stable static surface
                const int blended = (static_cast<int>(bg) * 15 + static_cast<int>(cur)) >> 4;
                ws_.bg_far_mm[c] = static_cast<uint16_t>(blended);
            } else if (prev > 0 && abs_diff_u16(cur, prev) <= 35 && cur < bg) {
                // A stable closer return can become background after the owner is gone.
                ws_.bg_far_mm[c] = static_cast<uint16_t>(bg - std::max(1, (bg - cur) >> 5));
            }
        }
    }
}

void HumanTracker::step(float dt_sec, FrameResult& out) {
    const bool gap = !std::isfinite(dt_sec) || dt_sec <= 0.0f || dt_sec > 0.35f;
    const float dt = gap ? 0.104f : std::max(0.04f, dt_sec);
    out = FrameResult{};
    out.frame_index = frame_index_;

    // Break continuity before consuming any old spatial or kinematic support.
    bool retain_owner[kMaxTracks + 1] = {};
    for (int t = 0; t < kMaxTracks; ++t) {
        Track& tr = tracks_[t];
        if (!tr.active) continue;
        tr.still_sec += dt;
        if (tr.fall_state == FallState::kFallSuspected) tr.suspected_sec += dt;
        else tr.suspected_sec = 0.0f;
        const float hold = tr.locked_human ? cfg_.still_hold_sec : cfg_.motion_window_sec;
        const bool expired = tr.fall_state == FallState::kFallSuspected
                                 ? tr.suspected_sec >= cfg_.suspected_hold_sec : tr.still_sec >= hold;
        if (gap || expired) tr.active = false;
        retain_owner[t + 1] = tr.active;
    }
    if (gap) std::memset(ws_.prev_range_mm, 0, sizeof(uint16_t) * kCells);

    int valid_cells = 0;
    int fg_seeds = 0;
    for (int c = 0; c < kCells; ++c) {
        const uint8_t owner = ws_.cell_flags[c] >> kOwnerShift;
        uint8_t flags = retain_owner[owner] ? ws_.cell_flags[c] : 0;
        const uint16_t cur = ws_.cur_range_mm[c];
        if (cur > 0) {
            valid_cells++;
            if (frame_index_ > 0) {
                const uint16_t bg = ws_.bg_far_mm[c];
                const uint16_t prev = ws_.prev_range_mm[c];
                const bool closer_than_bg = (bg > 0 && cur + cfg_.fg_margin_mm < bg);
                const bool closer_than_prev = (prev > 0 && cur + cfg_.fg_margin_mm < prev);
                if (prev > 0 && abs_diff_u16(cur, prev) >= cfg_.motion_depth_mm) flags |= kFlagMotion;
                if (closer_than_bg || closer_than_prev) {
                    flags |= kFlagFgSeed;
                    fg_seeds++;
                }
            }
        }
        ws_.cell_flags[c] = flags;
    }

    out.valid_cells = valid_cells;
    out.fg_seed_cells = fg_seeds;

    // Frame 0: bootstrap far-bg & prev directly without requiring empty room
    if (frame_index_ == 0) {
        for (int c = 0; c < kCells; ++c) {
            ws_.bg_far_mm[c] = ws_.cur_range_mm[c];
            ws_.prev_range_mm[c] = ws_.cur_range_mm[c];
        }
        frame_index_++;
        return;
    }

    Candidate candidates[kMaxCandidates];
    int cand_count = 0;

    // Stage 1: Segment inside a track's own recent measured coverage.
    for (int t = 0; t < kMaxTracks; ++t) {
        Track& tr = tracks_[t];
        if (!tr.active) continue;
        tr.measured_this_frame = false;

        const uint16_t pred_mm = static_cast<uint16_t>(
            std::max(100.0f, std::min(60000.0f, tr.range_m * 1000.0f)));
        const int row_pad = tr.locked_human &&
            (tr.drop_top_m >= 0.30f || std::fabs(tr.f_top_v) >= 0.35f) ? 24 : 12;
        const int r0 = std::max(0, tr.box_r0 - row_pad);
        const int c0 = std::max(0, tr.box_c0 - 12);
        const int r1 = std::min(kHeight - 1, tr.box_r1 + row_pad);
        const int c1 = std::min(kWidth - 1, tr.box_c1 + 12);

        // Pick best seed inside predicted region (prefer fg_seed or prev_locked near pred_mm)
        int best_seed = -1;
        int best_score = 1000000;
        for (int r = r0; r <= r1; ++r) {
            for (int c = c0; c <= c1; ++c) {
                const uint16_t cell = static_cast<uint16_t>((r << 8) | c);
                if (ws_.cell_flags[cell] & kFlagVisited) continue;
                const uint16_t mm = ws_.cur_range_mm[cell];
                if (mm == 0) continue;
                const int dmm = abs_diff_u16(mm, pred_mm);
                if (dmm > cfg_.retain_margin_mm) continue;
                const bool is_fg = (ws_.cell_flags[cell] & kFlagFgSeed) != 0;
                const bool was_owned = (ws_.cell_flags[cell] >> kOwnerShift) == t + 1;
                if (!is_fg && !was_owned) continue;
                const int score = dmm - (is_fg ? 250 : 0);
                if (score < best_score) {
                    best_score = score;
                    best_seed = cell;
                }
            }
        }

        if (best_seed >= 0 && cand_count < kMaxCandidates) {
            Candidate cand{};
            if (grow_cluster(static_cast<uint16_t>(best_seed), t, pred_mm, cand_count, cand)) {
                candidates[cand_count++] = cand;
            }
        }
    }

    // Stage 2: Discover new moving / foreground objects across full grid (stride-2 coarse seed scan)
    for (int r = 0; r < kHeight; r += 2) {
        for (int c = 0; c < kWidth; c += 2) {
            if (cand_count >= kMaxCandidates) break;
            const uint16_t cell = static_cast<uint16_t>((r << 8) | c);
            const uint8_t f = ws_.cell_flags[cell];
            if ((f & kFlagFgSeed) == 0 || (f & kFlagVisited) != 0) continue;
            Candidate cand{};
            if (grow_cluster(cell, -1, ws_.cur_range_mm[cell], cand_count, cand)) {
                candidates[cand_count++] = cand;
            }
        }
    }

    out.candidate_count = cand_count;

    // Stage 3: Greedy gated association (retain-origin candidates first, then nearest)
    uint8_t cand_slots[kMaxCandidates] = {};

    // 3a. Direct retain matches
    for (int i = 0; i < cand_count; ++i) {
        if (!candidates[i].from_retain) continue;
        const int slot = candidates[i].retain_track_slot;
        if (slot < 0 || slot >= kMaxTracks || !tracks_[slot].active) continue;
        Track& tr = tracks_[slot];
        if (std::isfinite(association_distance_squared(tr, candidates[i], dt))) {
            update_track_from_candidate(tr, candidates[i], dt);
            cand_slots[i] = static_cast<uint8_t>(slot + 1);
        }
    }

    // 3b. Associate remaining tracks to unmatched candidates
    // Give established tracks priority over tentative tracks competing for a candidate.
    for (bool locked : {true, false}) {
        for (int t = 0; t < kMaxTracks; ++t) {
            Track& tr = tracks_[t];
            if (!tr.active || tr.measured_this_frame || tr.locked_human != locked) continue;
            int best_c = -1;
            float best_d = INFINITY;
            for (int i = 0; i < cand_count; ++i) {
                if (cand_slots[i]) continue;
                const float distance = association_distance_squared(tr, candidates[i], dt);
                if (distance < best_d) {
                    best_d = distance;
                    best_c = i;
                }
            }
            if (best_c >= 0) {
                update_track_from_candidate(tr, candidates[best_c], dt);
                cand_slots[best_c] = static_cast<uint8_t>(t + 1);
            }
        }
    }

    // 3c. Age out unmeasured tracks (never fabricate measured points)
    for (int t = 0; t < kMaxTracks; ++t) {
        Track& tr = tracks_[t];
        if (!tr.active || tr.measured_this_frame) continue;
        tr.miss_frames += 1;
        tr.missed_sec += dt;
        if (tr.locked_human && tr.miss_frames <= kShortMissFrames && tr.missed_sec <= 0.35f) continue;
        tr.vel_u = 0.0f;
        tr.vel_v = 0.0f;
        tr.filter_init = false;
        tr.hist_count = 0;
        tr.hist_head = 0;
        tr.peak_down_vel = 0.0f;
        tr.peak_down_acc = 0.0f;
        tr.peak_brake_acc = 0.0f;
        tr.low_posture_sec = 0.0f;
        tr.fall_reason = FallReason::kNone;
        tr.fall_state = tr.locked_human ? FallState::kUpright : FallState::kUnknown;
        if (tr.miss_frames > cfg_.max_miss_frames) {
            tr.active = false;
        }
    }

    // 3d. Spawn new tracks from unmatched candidates
    for (int i = 0; i < cand_count; ++i) {
        if (cand_slots[i] || !upright_geometry(candidates[i])) continue;
        int free_slot = -1;
        for (int t = 0; t < kMaxTracks; ++t) {
            if (!tracks_[t].active) {
                free_slot = t;
                break;
            }
        }
        if (free_slot < 0) break;
        Track& tr = tracks_[free_slot];
        tr = Track{};
        tr.active = true;
        tr.id = next_track_id_++;
        tr.fall_state = FallState::kUnknown;
        tr.fall_reason = FallReason::kNone;
        update_track_from_candidate(tr, candidates[i], dt);
        cand_slots[i] = static_cast<uint8_t>(free_slot + 1);
    }

    // Stage 4: Only matched locked tracks and short moving hypotheses own coverage.
    for (int i = 0; i < cand_count; ++i) {
        const int slot = cand_slots[i] - 1;
        if (slot < 0 || tracks_[slot].locked_human) continue;
        const Candidate& cand = candidates[i];
        if (cand.motion_points < 4 && (cand.retain_track_slot != slot || cand.owned_points < 4)) {
            cand_slots[i] = 0;
        }
    }
    update_background(cand_slots);

    // Stage 5: Export active tracks snapshot
    int out_n = 0;
    for (int t = 0; t < kMaxTracks; ++t) {
        const Track& tr = tracks_[t];
        if (!tr.active) continue;
        TrackSnapshot& s = out.tracks[out_n++];
        s.track_id = tr.id;
        s.locked_human = tr.locked_human;
        s.measured_this_frame = tr.measured_this_frame;
        s.point_count = tr.measured_this_frame ? tr.point_count : 0;
        s.age_frames = tr.age_frames;
        s.miss_frames = tr.miss_frames;
        s.box_r0 = tr.box_r0;
        s.box_c0 = tr.box_c0;
        s.box_r1 = tr.box_r1;
        s.box_c1 = tr.box_c1;
        s.center = tr.center;
        s.range_m = tr.range_m;
        s.h_p05 = tr.h_p05;
        s.h_p50 = tr.h_p50;
        s.h_p95 = tr.h_p95;
        s.height_m = tr.height_m;
        s.horiz_span_m = tr.horiz_span_m;
        s.aspect = tr.aspect;
        s.baseline_ready = tr.baseline_ready;
        s.baseline_top_h = tr.baseline_top_h;
        s.baseline_height = tr.baseline_height;
        s.drop_top_m = tr.drop_top_m;
        s.vel_top_mps = tr.f_top_v;
        s.acc_top_mps2 = tr.f_top_a;
        s.peak_down_vel_mps = tr.peak_down_vel;
        s.peak_down_acc_mps2 = tr.peak_down_acc;
        s.peak_brake_acc_mps2 = tr.peak_brake_acc;
        s.horiz_speed_mps = std::sqrt(tr.vel_u * tr.vel_u + tr.vel_v * tr.vel_v);
        const float du = tr.cu - tr.start_cu;
        const float dv = tr.cv - tr.start_cv;
        s.net_disp_m = std::sqrt(du * du + dv * dv);
        s.low_posture_sec = tr.low_posture_sec;
        s.still_sec = tr.still_sec;
        s.fall_state = tr.fall_state;
        s.fall_reason = tr.fall_reason;
    }
    out.track_count = out_n;
    frame_index_++;
}

}  // namespace human_s3
