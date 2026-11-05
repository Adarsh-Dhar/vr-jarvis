"""Main module testing various call patterns."""
from payments import Payment, CardPayment, UpiPayment, validate
from authentication import validate as auth_validate
from orders import validate as validate_order
import requests  # External library


def checkout(amount: float):
    """Checkout function."""
    # Direct call - should resolve to payments.validate
    validate("pay123")
    
    # Module call - should resolve to authentication.validate
    auth_validate("token123")
    
    # Aliased import - should resolve to orders.validate
    validate_order("order123")
    
    # Method call with typed receiver - polymorphic (Payment/CardPayment/UpiPayment)
    payment = CardPayment()
    payment.process(amount)
    
    # Direct call again - should resolve to same target (payments.validate)
    validate("pay456")


def twice(func):
    """Call a function twice."""
    func()
    func()


# Recursion test
def recursive(n: int):
    """Recursive function."""
    if n <= 0:
        return
    validate(f"rec_{n}")
    recursive(n - 1)


# External library call
def fetch_data(url: str):
    """Fetch data from external API."""
    return requests.get(url)
