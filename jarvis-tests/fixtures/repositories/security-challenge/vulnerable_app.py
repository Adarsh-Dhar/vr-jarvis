# Vulnerable application with security issues for testing
# This file contains intentional vulnerabilities for testing purposes only

import sqlite3

# SQL Injection Vulnerability
def get_user(username):
    """Vulnerable to SQL injection"""
    conn = sqlite3.connect('users.db')
    cursor = conn.cursor()
    # BAD: Direct string concatenation
    query = f"SELECT * FROM users WHERE username = '{username}'"
    cursor.execute(query)
    return cursor.fetchall()

# XSS Vulnerability
def render_user_input(user_input):
    """Vulnerable to XSS"""
    # BAD: Direct HTML rendering without sanitization
    html = f"<div>User said: {user_input}</div>"
    return html

# Hardcoded password
def authenticate(password):
    """Hardcoded password - BAD"""
    SECRET_PASSWORD = "admin123"
    return password == SECRET_PASSWORD

# Command injection potential
def execute_command(cmd):
    """Potential command injection"""
    import os
    # BAD: Direct command execution
    os.system(cmd)

# Weak encryption
def encrypt_data(data):
    """Weak encryption - BAD"""
    key = "weakkey123"
    # Simple XOR - not real encryption
    return ''.join(chr(ord(c) ^ ord(key[i % len(key)])) for i, c in enumerate(data))
