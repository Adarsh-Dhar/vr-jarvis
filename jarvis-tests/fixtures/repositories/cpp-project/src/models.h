#ifndef MODELS_H
#define MODELS_H

#include <string>

class User {
private:
    std::string name;
    int age;

public:
    User(const std::string& name, int age);
    std::string getName() const;
    int getAge() const;
    std::string getDisplayName() const;
};

class Config {
private:
    std::string key;
    std::string value;

public:
    Config(const std::string& key, const std::string& value);
    std::string getKey() const;
    std::string getValue() const;
};

#endif
