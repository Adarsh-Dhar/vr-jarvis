"""
Tests for the simple Python application.
"""

import pytest
from src.main import UserService, User


def test_create_user():
    """Test user creation."""
    service = UserService()
    user = service.create_user("testuser", "test@example.com")
    
    assert user.id == 1
    assert user.username == "testuser"
    assert user.email == "test@example.com"


def test_get_user():
    """Test user retrieval."""
    service = UserService()
    created = service.create_user("testuser", "test@example.com")
    
    retrieved = service.get_user(created.id)
    
    assert retrieved is not None
    assert retrieved.id == created.id
    assert retrieved.username == "testuser"


def test_authenticate():
    """Test authentication."""
    service = UserService()
    service.create_user("alice", "alice@example.com")
    
    user = service.authenticate("alice", "password")
    
    assert user is not None
    assert user.username == "alice"


def test_authenticate_failure():
    """Test authentication with non-existent user."""
    service = UserService()
    
    user = service.authenticate("nonexistent", "password")
    
    assert user is None
