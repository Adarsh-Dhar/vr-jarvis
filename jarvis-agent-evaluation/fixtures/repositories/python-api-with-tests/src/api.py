"""
REST API for user management with authentication
Demonstrates route handling, validation, and error handling
"""

from flask import Flask, request, jsonify
from functools import wraps
from typing import Dict, List, Optional
import hashlib
import secrets

app = Flask(__name__)

# In-memory storage
users_db: Dict[int, dict] = {}
sessions: Dict[str, dict] = {}
user_counter = 0


class User:
    """User data model."""
    def __init__(self, username: str, email: str, password: str):
        self.id = None
        self.username = username
        self.email = email
        self.password_hash = self._hash_password(password)
        self.roles = ['user']
    
    @staticmethod
    def _hash_password(password: str) -> str:
        return hashlib.sha256(password.encode()).hexdigest()
    
    def check_password(self, password: str) -> bool:
        return self.password_hash == self._hash_password(password)
    
    def to_dict(self) -> dict:
        return {
            'id': self.id,
            'username': self.username,
            'email': self.email,
            'roles': self.roles
        }


def require_auth(f):
    """Authentication decorator for protected routes."""
    @wraps(f)
    def decorated(*args, **kwargs):
        token = request.headers.get('Authorization')
        if not token or not token.startswith('Bearer '):
            return jsonify({'error': 'Unauthorized'}), 401
        
        session_token = token[7:]  # Remove 'Bearer ' prefix
        session = sessions.get(session_token)
        
        if not session:
            return jsonify({'error': 'Invalid token'}), 401
        
        return f(user_id=session['user_id'], *args, **kwargs)
    return decorated


@app.route('/users', methods=['POST'])
def create_user():
    """Create a new user."""
    global user_counter
    
    data = request.get_json()
    username = data.get('username')
    email = data.get('email')
    password = data.get('password')
    
    if not all([username, email, password]):
        return jsonify({'error': 'Missing required fields'}), 400
    
    # Check for duplicate username
    for user in users_db.values():
        if user['username'] == username:
            return jsonify({'error': 'Username already exists'}), 409
    
    user_counter += 1
    user = User(username, email, password)
    user.id = user_counter
    
    users_db[user.id] = user.to_dict()
    
    return jsonify(user.to_dict()), 201


@app.route('/users/<int:user_id>', methods=['GET'])
def get_user(user_id: int):
    """Get a user by ID."""
    user = users_db.get(user_id)
    if not user:
        return jsonify({'error': 'User not found'}), 404
    
    return jsonify(user)


@app.route('/users/<int:user_id>', methods=['DELETE'])
@require_auth
def delete_user(user_id: int):
    """Delete a user (requires authentication)."""
    if user_id not in users_db:
        return jsonify({'error': 'User not found'}), 404
    
    del users_db[user_id]
    
    # Invalidate all sessions for this user
    to_remove = [token for token, session in sessions.items() 
                 if session['user_id'] == user_id]
    for token in to_remove:
        del sessions[token]
    
    return jsonify({'message': 'User deleted'}), 200


@app.route('/auth/login', methods=['POST'])
def login():
    """Authenticate a user and return a session token."""
    data = request.get_json()
    username = data.get('username')
    password = data.get('password')
    
    if not all([username, password]):
        return jsonify({'error': 'Missing credentials'}), 400
    
    # Find user
    user_data = None
    for user in users_db.values():
        if user['username'] == username:
            user_data = user
            break
    
    if not user_data:
        return jsonify({'error': 'Invalid credentials'}), 401
    
    # Verify password (in real app, use proper password hashing)
    user = User(user_data['username'], user_data['email'], password)
    user.id = user_data['id']
    user.password_hash = user_data['password_hash']
    
    if not user.check_password(password):
        return jsonify({'error': 'Invalid credentials'}), 401
    
    # Create session
    token = secrets.token_hex(32)
    sessions[token] = {
        'user_id': user.id,
        'username': user.username
    }
    
    return jsonify({'token': token, 'user': user.to_dict()}), 200


@app.route('/auth/logout', methods=['POST'])
@require_auth
def logout(user_id: int):
    """Logout and invalidate session."""
    token = request.headers.get('Authorization')[7:]
    sessions.pop(token, None)
    return jsonify({'message': 'Logged out'}), 200


@app.route('/health', methods=['GET'])
def health():
    """Health check endpoint."""
    return jsonify({
        'status': 'healthy',
        'users_count': len(users_db),
        'sessions_count': len(sessions)
    }), 200


if __name__ == '__main__':
    app.run(debug=True, port=5000)
