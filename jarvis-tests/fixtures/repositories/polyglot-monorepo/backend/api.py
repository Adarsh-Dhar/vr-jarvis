def process_data(data):
    """Backend Python service"""
    return {"result": data * 2}

def call_shared_library():
    """Calls shared Rust library via FFI"""
    # Placeholder for FFI call
    return "shared_result"
