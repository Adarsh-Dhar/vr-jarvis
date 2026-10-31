#!/usr/bin/env python3
"""
Simple Flask API for integration testing
A basic REST API with CRUD operations
"""

from flask import Flask, jsonify, request
from datetime import datetime

app = Flask(__name__)

# In-memory data store
users = [
    {"id": 1, "name": "Alice", "email": "alice@example.com"},
    {"id": 2, "name": "Bob", "email": "bob@example.com"},
    {"id": 3, "name": "Charlie", "email": "charlie@example.com"}
]

posts = [
    {"id": 1, "user_id": 1, "title": "First Post", "content": "This is my first post"},
    {"id": 2, "user_id": 1, "title": "Second Post", "content": "Another post"},
    {"id": 3, "user_id": 2, "title": "Hello World", "content": "Bob says hello"}
]

@app.route('/')
def index():
    return jsonify({"message": "Simple Flask API for testing", "version": "1.0"})

@app.route('/health')
def health():
    return jsonify({"status": "healthy", "timestamp": datetime.now().isoformat()})

@app.route('/api/users', methods=['GET'])
def get_users():
    return jsonify({"users": users, "count": len(users)})

@app.route('/api/users/<int:user_id>', methods=['GET'])
def get_user(user_id):
    user = next((u for u in users if u['id'] == user_id), None)
    if user:
        return jsonify(user)
    return jsonify({"error": "User not found"}), 404

@app.route('/api/users', methods=['POST'])
def create_user():
    data = request.get_json()
    if not data or 'name' not in data or 'email' not in data:
        return jsonify({"error": "Missing required fields"}), 400

    new_user = {
        "id": len(users) + 1,
        "name": data['name'],
        "email": data['email']
    }
    users.append(new_user)
    return jsonify(new_user), 201

@app.route('/api/users/<int:user_id>', methods=['PUT'])
def update_user(user_id):
    user = next((u for u in users if u['id'] == user_id), None)
    if not user:
        return jsonify({"error": "User not found"}), 404

    data = request.get_json()
    if 'name' in data:
        user['name'] = data['name']
    if 'email' in data:
        user['email'] = data['email']

    return jsonify(user)

@app.route('/api/users/<int:user_id>', methods=['DELETE'])
def delete_user(user_id):
    global users
    users = [u for u in users if u['id'] != user_id]
    return jsonify({"message": "User deleted"}), 200

@app.route('/api/posts', methods=['GET'])
def get_posts():
    return jsonify({"posts": posts, "count": len(posts)})

@app.route('/api/posts/<int:post_id>', methods=['GET'])
def get_post(post_id):
    post = next((p for p in posts if p['id'] == post_id), None)
    if post:
        return jsonify(post)
    return jsonify({"error": "Post not found"}), 404

@app.route('/api/posts', methods=['POST'])
def create_post():
    data = request.get_json()
    if not data or 'user_id' not in data or 'title' not in data:
        return jsonify({"error": "Missing required fields"}), 400

    new_post = {
        "id": len(posts) + 1,
        "user_id": data['user_id'],
        "title": data['title'],
        "content": data.get('content', '')
    }
    posts.append(new_post)
    return jsonify(new_post), 201

@app.route('/api/users/<int:user_id>/posts', methods=['GET'])
def get_user_posts(user_id):
    user_posts = [p for p in posts if p['user_id'] == user_id]
    return jsonify({"posts": user_posts, "count": len(user_posts)})

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5001, debug=True)
