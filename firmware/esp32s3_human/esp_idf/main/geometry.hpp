#pragma once

#include <cmath>

#include "wire.hpp"

namespace ifw192s {

struct Direction {
    float x, y, z;
};

struct RangeCalibration {
    float intensity;
    float distance;
    float squared_intensity;
    float offset;
};

// SDK Cartesian angles use the opposite sign from the azimuth calibration table.
// The scanner table is mirror-symmetric, so this maps a wire cell into the existing
// tracking grid while leaving ring and wire-row provenance unchanged.
inline uint16_t tracker_cell(const WireRecord& point) {
    return (uint16_t{point.ring} << 8) | (255u - point.column);
}

inline Direction ray_from_calibration(float azimuth_deg, float elevation_deg) {
    constexpr double kRadiansPerCentidegree = 0.00017453292519943296;
    const double azimuth = static_cast<int>(azimuth_deg * -100.0f) * kRadiansPerCentidegree;
    const double elevation = static_cast<int>(elevation_deg * 100.0f) * kRadiansPerCentidegree;
    const double cos_elevation = std::cos(elevation);
    return {static_cast<float>(cos_elevation * std::cos(azimuth)),
            static_cast<float>(cos_elevation * std::sin(azimuth)),
            static_cast<float>(std::sin(elevation))};
}

// Decode the measured point before applying the vendor's optional near-field filtering.
// A zero result is missing input to GridTracker.
inline float measured_range(const WireRecord& point, const RangeCalibration& calibration) {
    if (point.pulse_width == 0) {
        return 0.0f;
    }
    const float ticks = static_cast<float>(point.range_ticks) * (1.0f / 64.0f);
    const float raw = static_cast<float>((static_cast<double>(ticks) * 1.645 - 2.09) * 0.149896229);
    if (raw <= 0.0f) {
        return 0.0f;
    }
    const float intensity = static_cast<float>(point.pulse_area) / point.pulse_width;
    const double correction = static_cast<double>(intensity * intensity * calibration.squared_intensity)
        + static_cast<double>(intensity * calibration.intensity)
        + static_cast<double>(raw * calibration.distance) + calibration.offset;
    const float distance = static_cast<float>(raw - correction);
    return distance > 0.1f ? distance : 0.0f;
}

// Keep the live ingress on the S3's single-precision FPU. Around the validity
// cutoff use the SDK-matched calculation to resolve rounding differences.
inline float live_measured_range(const WireRecord& point, const RangeCalibration& calibration) {
    if (point.pulse_width == 0) { return 0.0f; }
    constexpr float meters_per_tick = 1.645 * 0.149896229 / 64.0;
    constexpr float range_offset = -2.09 * 0.149896229;
    const float raw = static_cast<float>(point.range_ticks) * meters_per_tick + range_offset;
    if (raw <= 0.0f) { return 0.0f; }
    constexpr size_t table_size = 1024;
    static constexpr auto reciprocal_width = [] {
        std::array<float, table_size> values{};
        for (size_t width = 1; width < values.size(); ++width) {
            values[width] = 1.0f / width;
        }
        return values;
    }();
    const float area = static_cast<float>(point.pulse_area);
    const float intensity = point.pulse_width < table_size
        ? area * reciprocal_width[point.pulse_width] : area / point.pulse_width;
    const float distance = raw - (intensity * intensity * calibration.squared_intensity +
        intensity * calibration.intensity + raw * calibration.distance + calibration.offset);
    if (distance > 0.1001f) { return distance; }
    if (distance < 0.0999f) { return 0.0f; }
    return measured_range(point, calibration);
}

}  // namespace ifw192s
