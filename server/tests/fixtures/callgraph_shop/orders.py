"""Orders module with validate function."""


def validate(order_id: str) -> bool:
    """Validate an order."""
    return len(order_id) > 0
