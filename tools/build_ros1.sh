#!/bin/bash
set -e

echo "=== Switch to ROS1 environment ==="

# 切换 package.xml
cp -f ./src/inno_lidar_msg/package_ros1.xml ./src/inno_lidar_msg/package.xml
cp -f ./src/inno_lidar_ros/package_ros1.xml ./src/inno_lidar_ros/package.xml


# 修改 CMakeLists 的 COMPILE_METHOD 为 CATKIN
sed -i 's/set(COMPILE_METHOD .*)/set(COMPILE_METHOD CATKIN)/' ./src/inno_lidar_msg/CMakeLists.txt
sed -i 's/set(COMPILE_METHOD .*)/set(COMPILE_METHOD CATKIN)/' ./src/inno_lidar_ros/CMakeLists.txt


# 编译
catkin_make

if [ -f "./devel/setup.bash" ]; then
    echo "source ./devel/setup.bash"
    source ./devel/setup.bash
fi

