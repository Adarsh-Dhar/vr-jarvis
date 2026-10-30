# Simple Python Test Repository
# Used for foundational correctness testing

def alpha():
    """Calls target function"""
    target()


def beta():
    """Calls target function"""
    target()


def gamma():
    """Calls alpha, which calls target"""
    alpha()


def delta():
    """Calls beta, which calls target"""
    beta()


def target():
    """Target function with multiple callers"""
    return True


def epsilon():
    """Standalone function with no callers"""
    return "standalone"


def recursive_a():
    """Recursive function A"""
    recursive_b()


def recursive_b():
    """Recursive function B"""
    recursive_a()


def overloaded_example():
    """Function with name that might be overloaded in other contexts"""
    return "original"


class ExampleClass:
    """Example class for testing"""

    def method_a(self):
        """Instance method"""
        self.target_method()

    def method_b(self):
        """Instance method"""
        self.target_method()

    def target_method(self):
        """Target method"""
        return "method_target"

    @staticmethod
    def static_method():
        """Static method"""
        return "static"

    @classmethod
    def class_method(cls):
        """Class method"""
        return "class"


def callback_example(callback):
    """Function that accepts a callback"""
    return callback()


def dependency_injection_example(service):
    """Function using dependency injection"""
    return service.process()


def imported_function():
    """Function imported from another module"""
    return "imported"


def cross_package_caller():
    """Function that calls across packages"""
    from subpackage import helper
    return helper.helper_function()
