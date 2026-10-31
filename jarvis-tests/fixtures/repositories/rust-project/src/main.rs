// Rust Example Project
// Used for multi-language testing

mod utils;
mod models;

use models::User;
use utils::process_data;

fn main() {
    println!("Hello from Rust!");

    let user = User::new("Alice", 30);
    process_data(&user);
}

fn calculate_score(value: i32) -> i32 {
    value * 2
}

fn validate_input(input: &str) -> bool {
    !input.is_empty()
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_calculate_score() {
        assert_eq!(calculate_score(5), 10);
    }
}
