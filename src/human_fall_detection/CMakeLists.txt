cmake_minimum_required(VERSION 3.0.2)
project(human_fall_detection)

find_package(catkin REQUIRED COMPONENTS rospy sensor_msgs std_msgs inno_lidar_msg)
catkin_package()

catkin_python_setup()

catkin_install_python(PROGRAMS scripts/sensor_health.py scripts/record_session.py
  scripts/calibrate_sensors.py scripts/fall_replay.py scripts/human_fall_node.py
  DESTINATION ${CATKIN_PACKAGE_BIN_DESTINATION})

install(DIRECTORY config
  DESTINATION ${CATKIN_PACKAGE_SHARE_DESTINATION})

install(DIRECTORY launch
  DESTINATION ${CATKIN_PACKAGE_SHARE_DESTINATION})
