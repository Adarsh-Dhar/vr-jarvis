"""ID allocator for unique IDs within a function scope."""
from typing import Optional


class IdAllocator:
    """Allocates unique operation, use, and definition IDs for a function."""

    def __init__(self, function_id: str):
        self.function_id = function_id
        self._op = 0
        self._use = 0
        self._def = 0

    def operation(self) -> str:
        """Generate a unique operation ID."""
        self._op += 1
        return f'{self.function_id}_op_{self._op}'

    def use(self, variable: str) -> str:
        """Generate a unique use ID for a variable."""
        self._use += 1
        return f'{self.function_id}_use_{variable}_{self._use}'

    def definition(self, variable: str) -> str:
        """Generate a unique definition ID for a variable."""
        self._def += 1
        return f'{self.function_id}_def_{variable}_{self._def}'
