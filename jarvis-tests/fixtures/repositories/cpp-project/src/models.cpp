// Data models for C++ example

#include "models.h"
#include <string>

User::User(const std::string& name, int age) : name(name), age(age) {}

std::string User::getName() const {
    return name;
}

int User::getAge() const {
    return age;
}

std::string User::getDisplayName() const {
    return name + " (age " + std::to_string(age) + ")";
}

Config::Config(const std::string& key, const std::string& value) 
    : key(key), value(value) {}

std::string Config::getKey() const {
    return key;
}

std::string Config::getValue() const {
    return value;
}
