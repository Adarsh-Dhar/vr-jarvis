cmake_minimum_required(VERSION 3.10)
project(CppExample)

set(CMAKE_CXX_STANDARD 17)

add_executable(cpp_example
    src/main.cpp
    src/utils.cpp
    src/models.cpp
)
