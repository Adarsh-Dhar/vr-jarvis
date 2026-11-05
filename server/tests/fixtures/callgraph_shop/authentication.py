"""Authentication module with validate function."""


def validate(token: str) -> bool:
    """Validate a token."""
    return token == "secret"
