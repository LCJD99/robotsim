cmake_minimum_required(VERSION 3.8)
project(sim_description)

find_package(ament_cmake REQUIRED)

install(DIRECTORY worlds
  DESTINATION share/${PROJECT_NAME}
)

ament_package()
