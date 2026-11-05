"""Payments module with validate function and classes."""
from authentication import validate as auth_validate


class Payment:
    """Base payment class."""
    
    def process(self, amount: float) -> bool:
        """Process payment."""
        # Call auth_validate (inherited method test)
        return auth_validate("test_token")
    
    def validate(self, payment_id: str) -> bool:
        """Validate a payment (base class method)."""
        return len(payment_id) > 0


class CardPayment(Payment):
    """Card payment processor."""
    
    def process(self, amount: float) -> bool:
        """Process card payment."""
        # Call parent method (inheritance test)
        return super().process(amount) if amount > 0 else False
    
    def validate(self, payment_id: str) -> bool:
        """Override validate."""
        return len(payment_id) >= 16


class UpiPayment(Payment):
    """UPI payment processor."""
    
    def process(self, amount: float) -> bool:
        """Process UPI payment."""
        return True


def validate(payment_id: str) -> bool:
    """Validate a payment."""
    return len(payment_id) > 0
