// C++ Example Project
// Used for multi-language testing

#include <iostream>
#include <string>
#include "models.h"
#include "utils.h"

int main() {
    std::cout << "Hello from C++!" << std::endl;

    User user("Alice", 30);
    processUser(user);

    return 0;
}

int calculateScore(int value) {
    return value * 2;
}

bool validateInput(const std::string& input) {
    return !input.empty();
}
