#[no_mangle]
pub extern "C" fn shared_function(input: i32) -> i32 {
    input * 3
}

pub fn internal_logic(value: i32) -> i32 {
    value + 1
}
