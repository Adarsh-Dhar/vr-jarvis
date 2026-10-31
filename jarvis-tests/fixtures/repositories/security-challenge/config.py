# Configuration file with hardcoded API key (BAD PRACTICE)
# This file contains a secret for testing purposes only

API_KEY = "sk-1234567890abcdefghijklmnopqrstuvwxyz"
DATABASE_URL = "postgresql://user:secretpassword@localhost/db"
AWS_SECRET_KEY = "aws_secret_key_ABCDEFGHIJKLMNOPQRSTUVWXYZ"

def get_api_config():
    """Returns API configuration"""
    return {
        "key": API_KEY,
        "endpoint": "https://api.example.com"
    }
