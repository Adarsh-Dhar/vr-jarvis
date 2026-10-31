#ifndef UTILS_H
#define UTILS_H

#include "models.h"
#include <string>

void processUser(const User& user);
std::string formatResult(int value);
bool validateConfig(const std::string& config);

#endif
