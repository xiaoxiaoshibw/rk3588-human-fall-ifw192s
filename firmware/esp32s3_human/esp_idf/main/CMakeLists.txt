idf_component_register(
    SRCS "main.cpp" "../../human_tracker.cpp"
    INCLUDE_DIRS "." "../.."
    PRIV_REQUIRES esp_driver_gpio esp_driver_spi esp_driver_uart esp_timer esp_psram
)
