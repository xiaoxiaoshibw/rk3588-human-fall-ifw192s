cmake_minimum_required(VERSION 3.0.2)
project(human_follow_calibration)

find_package(catkin REQUIRED COMPONENTS rospy sensor_msgs std_msgs)
catkin_package()

catkin_install_python(PROGRAMS scripts/calibrate_human_follow.py scripts/monitor_human_follow.py
  DESTINATION ${CATKIN_PACKAGE_BIN_DESTINATION})
