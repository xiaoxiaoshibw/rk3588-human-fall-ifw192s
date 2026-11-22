#pragma once

#include <algorithm>
#include <cstddef>
#include <cstdint>

#include "driver/gpio.h"
#include "driver/spi_master.h"
#include "esp_check.h"
#include "esp_timer.h"
#include "freertos/FreeRTOS.h"
#include "freertos/task.h"

namespace ifw192s {

class W5500 {
public:
    static constexpr size_t kBufferBytes = 16 * 1024;
    static constexpr int kBaseHz = 10'000'000;
    static constexpr uint8_t kIsolatedMac[] = {0x08, 0xe2, 0x6d, 0xc4, 0xfd, 0x47};

    void init() {
        gpio_config_t gpio{};
        gpio.pin_bit_mask = 1ull << GPIO_NUM_7;
        gpio.mode = GPIO_MODE_OUTPUT;
        ESP_ERROR_CHECK(gpio_config(&gpio));
        reset();
        spi_bus_config_t bus{};
        bus.mosi_io_num = GPIO_NUM_11;
        bus.miso_io_num = GPIO_NUM_13;
        bus.sclk_io_num = GPIO_NUM_12;
        bus.quadwp_io_num = bus.quadhd_io_num = -1;
        bus.data4_io_num = bus.data5_io_num = bus.data6_io_num = bus.data7_io_num = -1;
        bus.max_transfer_sz = kBufferBytes;
        ESP_ERROR_CHECK(spi_bus_initialize(SPI2_HOST, &bus, SPI_DMA_CH_AUTO));
        set_mode(0);
    }

    void set_mode(uint8_t mode) {
        if (spi_) {
            ESP_ERROR_CHECK(spi_bus_remove_device(spi_));
        }
        spi_device_interface_config_t device{};
        device.mode = mode;
        device.address_bits = 24;
        device.clock_speed_hz = kBaseHz;
        device.spics_io_num = GPIO_NUM_10;
        device.queue_size = 1;
        device.flags = SPI_DEVICE_HALFDUPLEX | SPI_DEVICE_NO_DUMMY;
        device.cs_ena_pretrans = 2;
        device.cs_ena_posttrans = 2;
        ESP_ERROR_CHECK(spi_bus_add_device(SPI2_HOST, &device, &spi_));
    }

    void drive(gpio_drive_cap_t strength) {
        ESP_ERROR_CHECK(gpio_set_drive_capability(GPIO_NUM_10, strength));
        ESP_ERROR_CHECK(gpio_set_drive_capability(GPIO_NUM_11, strength));
        ESP_ERROR_CHECK(gpio_set_drive_capability(GPIO_NUM_12, strength));
    }
    void read_dummy_bits(uint8_t count) { dummy_read_ = count; }
    void acquire() { ESP_ERROR_CHECK(spi_device_acquire_bus(spi_, portMAX_DELAY)); }
    void release() { spi_device_release_bus(spi_); }

    void reset() {
        ESP_ERROR_CHECK(gpio_set_level(GPIO_NUM_7, 0));
        vTaskDelay(pdMS_TO_TICKS(10));
        ESP_ERROR_CHECK(gpio_set_level(GPIO_NUM_7, 1));
        vTaskDelay(pdMS_TO_TICKS(100));
    }

    bool configure(const uint8_t* mac) {
        const uint8_t ip_and_mask[] = {255, 255, 255, 0, mac[0], mac[1], mac[2], mac[3], mac[4], mac[5],
                                       192, 168, 1, 35};
        write(kCommon, 0x0005, ip_and_mask, sizeof(ip_and_mask));
        for (unsigned socket = 0; socket < 8; ++socket) {
            write16(static_cast<uint8_t>(1 + 4 * socket), 0x001e, 0);
        }
        write16(kSocket0, 0x001e, 0x1002);
        return read16(kSocket0, 0x001e) == 0x1002;
    }

    bool open_udp() {
        if (!command(0x10)) { return false; }  // CLOSE
        write_byte(kSocket0, 0x0000, 0x02);
        write16(kSocket0, 0x0004, 8080);
        if (!command(0x01) || read_byte(kSocket0, 0x0003) != 0x22) { return false; }
        read_pointer_ = read16(kSocket0, 0x0028);
        return true;
    }

    uint8_t version(unsigned set_hz = 0) { return read_byte(kCommon, 0x0039, set_hz); }
    uint8_t phy() { return read_byte(kCommon, 0x002e); }
    void read_mac(uint8_t* mac) { read(kCommon, 0x0009, mac, 6); }

    int clock_khz() const {
        int khz;
        ESP_ERROR_CHECK(spi_device_get_actual_freq(spi_, &khz));
        return khz;
    }

    size_t pending() {
        uint16_t previous = read16(kSocket0, 0x0026);
        for (unsigned attempt = 0; attempt < 5; ++attempt) {
            const uint16_t current = read16(kSocket0, 0x0026);
            if (previous == current && current <= kBufferBytes) { return current; }
            previous = current;
        }
        return 0;
    }

    // For the isolated IFW192S stream, every queued UDP record is 8+1104 bytes.
    // Within a 16-KiB RX buffer the low-byte residues of the possible counts
    // are unique. Reject a torn register read rather than consuming bytes.
    size_t pending_ifw192s() {
        alignas(4) uint8_t registers[40];
        read(kSocket0, 0, registers, sizeof(registers));
        const uint16_t count = uint16_t{registers[0x26]} << 8 | registers[0x27];
        if (registers[1] != 0 || count > kBufferBytes || count % 1112 != 0) {
            return 0;
        }
        return count;
    }

    bool pop(uint8_t* out, size_t size, bool wait_for_command = true) {
        const uint16_t offset = read_pointer_ & (kBufferBytes - 1);
        const size_t head = std::min(size, kBufferBytes - offset);
        read(kRx0, offset, out, head);
        if (head != size) {
            read(kRx0, 0, out + head, size - head);
        }
        read_pointer_ = static_cast<uint16_t>(read_pointer_ + size);
        write16(kSocket0, 0x0028, read_pointer_);
        if (wait_for_command) {
            return command(0x40);  // RECV
        }
        write_byte(kSocket0, 0x0001, 0x40);
        return true;
    }

    void start_pop(uint8_t* out, size_t size) {
        // W5500 maps the 16-bit offset to the configured circular RX block.
        // The chip advances that offset for the whole VDM transaction.
        burst_ = {};
        burst_.base.flags = SPI_TRANS_VARIABLE_DUMMY;
        burst_.dummy_bits = dummy_read_;
        burst_.base.addr = address(kRx0, read_pointer_);
        burst_.base.rxlength = size * 8;
        burst_.base.rx_buffer = out;
        ESP_ERROR_CHECK(spi_device_polling_start(spi_, &burst_.base, portMAX_DELAY));
    }

    uint64_t finish_pop() {
        ESP_ERROR_CHECK(spi_device_polling_end(spi_, portMAX_DELAY));
        const uint64_t read_done_us = esp_timer_get_time();
        read_pointer_ = static_cast<uint16_t>(read_pointer_ + burst_.base.rxlength / 8);
        write16(kSocket0, 0x0028, read_pointer_);
        write_byte(kSocket0, 0x0001, 0x40);
        return read_done_us;
    }

    void write_test_bytes(const uint8_t* data, size_t size) { write(kTx0, 0, data, size); }
    void read_test_bytes(uint8_t* data, size_t size) { read(kTx0, 0, data, size); }

private:
    static constexpr uint8_t kCommon = 0;
    static constexpr uint8_t kSocket0 = 1;
    static constexpr uint8_t kTx0 = 2;
    static constexpr uint8_t kRx0 = 3;

    bool command(uint8_t value) {
        write_byte(kSocket0, 0x0001, value);
        const auto deadline = esp_timer_get_time() + 1000;
        do {
            if (read_byte(kSocket0, 0x0001) == 0) { return true; }
        } while (esp_timer_get_time() < deadline);
        return false;
    }

    static uint32_t address(uint8_t block, uint16_t reg, bool write_bit = false) {
        return (uint32_t{reg} << 8) | (uint32_t{block} << 3) | (write_bit ? 4u : 0u);
    }

    void transfer(spi_transaction_t& transaction) {
        ESP_ERROR_CHECK(spi_device_polling_transmit(spi_, &transaction));
    }

    void read(uint8_t block, uint16_t reg, uint8_t* out, size_t count) {
        spi_transaction_ext_t extended{};
        auto& transaction = extended.base;
        transaction.flags = SPI_TRANS_VARIABLE_DUMMY;
        extended.dummy_bits = dummy_read_;
        transaction.addr = address(block, reg);
        transaction.rxlength = count * 8;
        transaction.rx_buffer = out;
        transfer(transaction);
    }

    void write(uint8_t block, uint16_t reg, const uint8_t* data, size_t count) {
        spi_transaction_t transaction{};
        transaction.addr = address(block, reg, true);
        transaction.length = count * 8;
        transaction.tx_buffer = data;
        transfer(transaction);
    }

    uint16_t read_register(uint8_t block, uint16_t reg, unsigned bytes, unsigned hz = 0) {
        spi_transaction_ext_t extended{};
        auto& transaction = extended.base;
        transaction.flags = SPI_TRANS_USE_RXDATA | SPI_TRANS_VARIABLE_DUMMY;
        extended.dummy_bits = dummy_read_;
        transaction.addr = address(block, reg);
        transaction.rxlength = bytes * 8;
        transaction.override_freq_hz = hz;
        transfer(transaction);
        return bytes == 1 ? transaction.rx_data[0]
                          : uint16_t{transaction.rx_data[0]} << 8 | transaction.rx_data[1];
    }

    uint8_t read_byte(uint8_t block, uint16_t reg, unsigned hz = 0) {
        return read_register(block, reg, 1, hz);
    }

    uint16_t read16(uint8_t block, uint16_t reg) { return read_register(block, reg, 2); }

    void write_register(uint8_t block, uint16_t reg, uint16_t data, unsigned size) {
        spi_transaction_t transaction{};
        transaction.flags = SPI_TRANS_USE_TXDATA;
        transaction.addr = address(block, reg, true);
        transaction.length = size * 8;
        if (size == 2) {
            transaction.tx_data[0] = data >> 8;
            transaction.tx_data[1] = data;
        } else {
            transaction.tx_data[0] = data;
        }
        transfer(transaction);
    }

    void write_byte(uint8_t block, uint16_t reg, uint8_t data) { write_register(block, reg, data, 1); }
    void write16(uint8_t block, uint16_t reg, uint16_t data) { write_register(block, reg, data, 2); }

    spi_device_handle_t spi_ = nullptr;
    spi_transaction_ext_t burst_{};
    uint16_t read_pointer_ = 0;
    uint8_t dummy_read_ = 0;
};

}  // namespace ifw192s
