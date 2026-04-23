cmake_minimum_required(VERSION 3.8)
project(robot_control)

find_package(ament_cmake REQUIRED)

install(DIRECTORY config launch
  DESTINATION share/${PROJECT_NAME}
)

install(PROGRAMS
  scripts/controller_cycle_metrics_publisher
  DESTINATION lib/${PROJECT_NAME}
)

ament_package()
