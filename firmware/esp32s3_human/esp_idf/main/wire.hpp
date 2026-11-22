#pragma once

#include <array>
#include <cstddef>
#include <cstdint>
#include <cstring>

namespace ifw192s {

// Wire layout verified against the IFW192S SDK and the historical Ethernet capture.
constexpr size_t kPacketBytes = 1104;
constexpr size_t kRecordsPerPacket = 64;
constexpr size_t kRecordOffset = 24;
constexpr size_t kRecordBytes = 16;
constexpr size_t kSequenceOffset = 1100;
constexpr size_t kSequenceCopyOffset = 1088;
constexpr uint16_t kColumns = 256;
constexpr uint16_t kRings = 192;
constexpr uint32_t kFrameRecords = uint32_t{kRings} * kColumns;

inline uint32_t read_u24(const uint8_t* value) {
    return uint32_t{value[0]} | (uint32_t{value[1]} << 8) | (uint32_t{value[2]} << 16);
}

inline uint32_t read_u32(const uint8_t* value) {
    return read_u24(value) | (uint32_t{value[3]} << 24);
}

struct WireRecord {
    uint8_t column;
    uint8_t ring;
    uint16_t pulse_width;
    uint32_t range_ticks;
    uint32_t pulse_area;
};

inline WireRecord read_record(const uint8_t* value) {
    return {value[1], value[2], static_cast<uint16_t>(value[3] | (uint16_t{value[4]} << 8)),
            read_u24(value + 7), read_u24(value + 13)};
}

struct FrameBoundary {
    uint32_t first_sequence;
    uint32_t final_sequence;
    uint32_t records;
    uint64_t final_packet_read_us;
    bool complete;
};

struct WireStats {
    uint64_t packets = 0;
    uint64_t malformed = 0;
    uint64_t missing = 0;
    uint64_t duplicate_or_late = 0;
    uint32_t first_missing_sequence = 0;
    uint32_t invalid_cells = 0;
    uint32_t duplicate_cells = 0;
};

enum class PacketLayout { aligned, detect };

// A sink owns the grid and handles begin_frame(), record(point, wire_row) and end_frame(boundary).
// End markers belong to the closing frame. A single packet may contain records from two frames.
class WireAssembler {
public:
    explicit WireAssembler(PacketLayout layout = PacketLayout::aligned) : layout_(layout) {}

    const WireStats& stats() const { return stats_; }

    void reset_alignment() {
        have_sequence_ = false;
        have_frame_ = false;
        have_prefix_ = false;
    }

    template <typename Sink>
    void push(const uint8_t* bytes, size_t size, uint64_t packet_read_us, Sink& sink) {
        if (!bytes || size != kPacketBytes || bytes[0] != 0xee || bytes[1] != 0xff ||
            bytes[2] != 0x01 || read_u32(bytes + kSequenceCopyOffset) != read_u32(bytes + kSequenceOffset)) {
            ++stats_.malformed;
            frame_damaged_ = true;
            have_prefix_ = false;
            return;
        }
        const uint32_t sequence = read_u32(bytes + kSequenceOffset);
        if (have_sequence_) {
            const uint32_t advance = sequence - last_sequence_;
            if (advance == 0 || advance >= 0x80000000u) {
                ++stats_.duplicate_or_late;
                return;
            }
            if (advance != 1) {
                if (stats_.missing == 0) { stats_.first_missing_sequence = last_sequence_ + 1; }
                stats_.missing += advance - 1;
                frame_damaged_ = true;
                have_prefix_ = false;
            }
        }
        have_sequence_ = true;
        last_sequence_ = sequence;
        ++stats_.packets;

        const uint8_t* body = bytes + kRecordOffset;
        if (layout_ == PacketLayout::detect && !has_record_tags(body, record_offset_)) {
            const auto offset = find_record_offset(body);
            frame_damaged_ = true;
            have_prefix_ = false;
            if (offset == kRecordBytes) {
                ++stats_.malformed;
                return;
            }
            record_offset_ = offset;
        }
        if (record_offset_ == 0) {
            for (size_t slot = 0; slot < kRecordsPerPacket; ++slot) {
                record(body + slot * kRecordBytes, sequence, packet_read_us, sink);
            }
            return;
        }

        // The sensor can split a record between consecutive datagrams.
        // The pending prefix starts at the end of the previous packet body.
        const size_t prefix_bytes = kRecordBytes - record_offset_;
        if (have_prefix_) {
            uint8_t first[kRecordBytes];
            std::memcpy(first, prefix_.data(), prefix_bytes);
            std::memcpy(first + prefix_bytes, body, record_offset_);
            record(first, sequence, packet_read_us, sink);
        }
        for (size_t slot = 0; slot < kRecordsPerPacket - 1; ++slot) {
            record(body + record_offset_ + slot * kRecordBytes, sequence, packet_read_us, sink);
        }
        std::memcpy(prefix_.data(), body + kRecordsPerPacket * kRecordBytes - prefix_bytes, prefix_bytes);
        have_prefix_ = true;
    }

private:
    static bool has_record_tags(const uint8_t* body, size_t offset) {
        return body[offset] == 2 && body[offset + 15 * kRecordBytes] == 2 &&
            body[offset + 31 * kRecordBytes] == 2 && body[offset + 62 * kRecordBytes] == 2;
    }

    static size_t find_record_offset(const uint8_t* body) {
        size_t found = kRecordBytes;
        for (size_t offset = 0; offset < kRecordBytes; ++offset) {
            if (!has_record_tags(body, offset)) { continue; }
            bool matches = true;
            for (size_t slot = 0; slot < kRecordsPerPacket - 1; ++slot) {
                const auto* point = body + offset + slot * kRecordBytes;
                if (point[0] != 2 || point[2] >= kRings) {
                    matches = false;
                    break;
                }
            }
            if (matches) {
                if (found != kRecordBytes) { return kRecordBytes; }
                found = offset;
            }
        }
        return found;
    }

    template <typename Sink>
    void record(const uint8_t* bytes, uint32_t sequence, uint64_t packet_read_us, Sink& sink) {
        const auto point = read_record(bytes);
        const bool marker = point.column == 127 && point.ring == 191;
        if (have_frame_) {
            if (records_ == 0) {
                first_sequence_ = sequence;
            }
            if (!frame_damaged_) {
                accept_record(point, sink);
            }
            ++records_;
            if (marker) {
                sink.end_frame(FrameBoundary{
                    first_sequence_, sequence, records_, packet_read_us,
                    !frame_damaged_ && records_ == kFrameRecords,
                });
            }
        }
        if (marker) {
            sink.begin_frame();
            records_ = 0;
            seen_.fill(0);
            frame_damaged_ = false;
            have_frame_ = true;
        }
    }

    template <typename Sink>
    void accept_record(const WireRecord& point, Sink& sink) {
        if (point.ring >= kRings || records_ >= kFrameRecords) {
            ++stats_.invalid_cells;
            frame_damaged_ = true;
            return;
        }
        const uint16_t cell = (uint16_t{point.ring} << 8) | point.column;
        auto& word = seen_[cell / 32];
        const uint32_t bit = uint32_t{1} << (cell % 32);
        if (word & bit) {
            ++stats_.duplicate_cells;
            frame_damaged_ = true;
            return;
        }
        word |= bit;
        sink.record(point, records_);
    }

    std::array<uint32_t, kFrameRecords / 32> seen_{};
    std::array<uint8_t, kRecordBytes - 1> prefix_{};
    PacketLayout layout_;
    size_t record_offset_ = 0;
    WireStats stats_;
    uint32_t last_sequence_ = 0;
    uint32_t first_sequence_ = 0;
    uint32_t records_ = 0;
    bool have_sequence_ = false;
    bool have_frame_ = false;
    bool frame_damaged_ = false;
    bool have_prefix_ = false;
};

}  // namespace ifw192s
