"""
Tests for the user management API
"""

import pytest
import json
from src.api import app, users_db, sessions


@pytest.fixture
def client():
    """Create a test client."""
    app.config['TESTING'] = True
    with app.test_client() as client:
        yield client


@pytest.fixture(autouse=True)
def cleanup():
    """Clean up databases after each test."""
    yield
    users_db.clear()
    sessions.clear()


def test_create_user(client):
    """Test user creation."""
    response = client.post('/users', 
                          json={'username': 'testuser', 'email': 'test@example.com', 'password': 'password123'})
    
    assert response.status_code == 201
    data = json.loads(response.data)
    assert data['username'] == 'testuser'
    assert data['email'] == 'test@example.com'
    assert 'id' in data


def test_create_user_missing_fields(client):
    """Test user creation with missing fields."""
    response = client.post('/users', json={'username': 'testuser'})
    
    assert response.status_code == 400
    data = json.loads(response.data)
    assert 'error' in data


def test_create_duplicate_user(client):
    """Test creating duplicate username."""
    client.post('/users', json={'username': 'testuser', 'email': 'test@example.com', 'password': 'password123'})
    response = client.post('/users', json={'username': 'testuser', 'email': 'test2@example.com', 'password': 'password123'})
    
    assert response.status_code == 409


def test_get_user(client):
    """Test getting a user."""
    create_response = client.post('/users', 
                                   json={'username': 'testuser', 'email': 'test@example.com', 'password': 'password123'})
    user_id = json.loads(create_response.data)['id']
    
    response = client.get(f'/users/{user_id}')
    
    assert response.status_code == 200
    data = json.loads(response.data)
    assert data['username'] == 'testuser'


def test_get_nonexistent_user(client):
    """Test getting a non-existent user."""
    response = client.get('/users/999')
    
    assert response.status_code == 404


def test_login(client):
    """Test user login."""
    client.post('/users', json={'username': 'testuser', 'email': 'test@example.com', 'password': 'password123'})
    
    response = client.post('/auth/login', json={'username': 'testuser', 'password': 'password123'})
    
    assert response.status_code == 200
    data = json.loads(response.data)
    assert 'token' in data
    assert 'user' in data


def test_login_invalid_credentials(client):
    """Test login with invalid credentials."""
    response = client.post('/auth/login', json={'username': 'nonexistent', 'password': 'wrong'})
    
    assert response.status_code == 401


def test_delete_user(client):
    """Test deleting a user."""
    create_response = client.post('/users', 
                                   json={'username': 'testuser', 'email': 'test@example.com', 'password': 'password123'})
    user_id = json.loads(create_response.data)['id']
    
    # Login to get token
    login_response = client.post('/auth/login', json={'username': 'testuser', 'password': 'password123'})
    token = json.loads(login_response.data)['token']
    
    response = client.delete(f'/users/{user_id}', headers={'Authorization': f'Bearer {token}'})
    
    assert response.status_code == 200
    
    # Verify user is deleted
    get_response = client.get(f'/users/{user_id}')
    assert get_response.status_code == 404


def test_health_check(client):
    """Test health check endpoint."""
    response = client.get('/health')
    
    assert response.status_code == 200
    data = json.loads(response.data)
    assert data['status'] == 'healthy'
