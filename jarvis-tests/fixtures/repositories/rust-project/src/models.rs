// Data models for Rust example

pub struct User {
    pub name: String,
    pub age: u32,
}

impl User {
    pub fn new(name: &str, age: u32) -> Self {
        User {
            name: name.to_string(),
            age,
        }
    }

    pub fn get_display_name(&self) -> String {
        format!("{} (age {})", self.name, self.age)
    }
}

pub struct Config {
    pub key: String,
    pub value: String,
}

impl Config {
    pub fn new(key: &str, value: &str) -> Self {
        Config {
            key: key.to_string(),
            value: value.to_string(),
        }
    }
}
