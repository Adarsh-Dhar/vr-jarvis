# C++ Example Project

This is a simple C++ project used for multi-language testing of the JARVIS testing framework.

## Structure
- `src/main.cpp` - Main entry point with functions
- `src/utils.cpp/h` - Utility functions
- `src/models.cpp/h` - Data models (User, Config classes)
- `CMakeLists.txt` - Build configuration

## Purpose
To validate that:
- Language detection works for C++ files
- Symbol extraction finds functions, classes, and methods
- Dependency graph detects header file dependencies
- Call graph identifies function calls

## Usage
Used by tests for:
- Language adapter tools
- Symbol extraction
- Dependency analysis
- Cross-language code understanding
