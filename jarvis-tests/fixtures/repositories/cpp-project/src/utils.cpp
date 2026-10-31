// Utility functions for C++ example

#include "utils.h"
#include <iostream>

void processUser(const User& user) {
    std::cout << "Processing user: " << user.getName() << std::endl;
}

std::string formatResult(int value) {
    return "Result: " + std::to_string(value);
}

bool validateConfig(const std::string& config) {
    return config.length() > 0;
}
