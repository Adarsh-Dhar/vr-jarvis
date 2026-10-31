// Utility functions for Rust example

pub fn process_data(user: &models::User) {
    println!("Processing user: {}", user.name);
}

pub fn format_result(value: i32) -> String {
    format!("Result: {}", value)
}

pub fn validate_config(config: &str) -> bool {
    config.len() > 0
}
