"""
Simple Python application for testing.
A basic web API with user authentication.
"""

from typing import Optional
from dataclasses import dataclass


@dataclass
class User:
    """User data model."""
    id: int
    username: str
    email: str


class UserService:
    """User service for managing users."""
    
    def __init__(self):
        self.users = {}
        self.next_id = 1
    
    def create_user(self, username: str, email: str) -> User:
        """Create a new user."""
        user = User(id=self.next_id, username=username, email=email)
        self.users[self.next_id] = user
        self.next_id += 1
        return user
    
    def get_user(self, user_id: int) -> Optional[User]:
        """Get a user by ID."""
        return self.users.get(user_id)
    
    def authenticate(self, username: str, password: str) -> Optional[User]:
        """Authenticate a user."""
        # Simplified authentication - in real app would hash passwords
        for user in self.users.values():
            if user.username == username:
                return user
        return None


def main():
    """Main entry point."""
    service = UserService()
    
    # Create test users
    service.create_user("alice", "alice@example.com")
    service.create_user("bob", "bob@example.com")
    
    # Authenticate
    user = service.authenticate("alice", "password")
    if user:
        print(f"Authenticated: {user.username}")
    else:
        print("Authentication failed")


if __name__ == "__main__":
    main()
