cmake_minimum_required(VERSION 3.16)
project(esp32s3_human_core LANGUAGES CXX)

set(CMAKE_CXX_STANDARD 17)
set(CMAKE_CXX_STANDARD_REQUIRED ON)

add_library(esp32s3_human_core STATIC
    human_tracker.cpp
    human_tracker.hpp
)
target_include_directories(esp32s3_human_core PUBLIC ${CMAKE_CURRENT_SOURCE_DIR})
target_compile_options(esp32s3_human_core PRIVATE -O3 -Wall -Wextra)

option(HUMAN_HOST "Build PC host replay binary" ON)
if(HUMAN_HOST)
    add_executable(human_host host_replay.cpp)
    target_link_libraries(human_host PRIVATE esp32s3_human_core)
    target_compile_options(human_host PRIVATE -O3 -Wall -Wextra)
endif()
