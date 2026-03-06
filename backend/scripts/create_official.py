#!/usr/bin/env python3
"""
Create Student Union Official User Script
==========================================
Creates a new Student Union official user with auto-generated credentials.

Usage: python scripts/create_official.py

Each run creates a new unique user and prints credentials to stdout.
"""

import sys
import os
import secrets
import string

# Add parent directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from pymongo import MongoClient
from utils.password import hash_password
from datetime import datetime, timezone

# Configuration
MONGO_URI = os.environ.get('MONGO_URI', 'mongodb://localhost:27017/')
DB_NAME = os.environ.get('DB_NAME', 'securevote')


def generate_user_id(prefix='SUOFF'):
    """Generate a unique user ID."""
    random_part = ''.join(secrets.choice(string.digits) for _ in range(4))
    return f"{prefix}{random_part}"


def generate_password():
    """
    Generate a password that meets requirements:
    - At least 8 characters
    - At least one uppercase
    - At least one lowercase
    - At least one digit
    """
    # Ensure we have at least one of each required type
    uppercase = secrets.choice(string.ascii_uppercase)
    lowercase = secrets.choice(string.ascii_lowercase)
    digit = secrets.choice(string.digits)

    # Fill the rest with a mix (5 more chars to reach 8 total)
    alphabet = string.ascii_letters + string.digits
    remaining = ''.join(secrets.choice(alphabet) for _ in range(5))

    # Combine and shuffle
    password_chars = list(uppercase + lowercase + digit + remaining)
    secrets.SystemRandom().shuffle(password_chars)

    return ''.join(password_chars)


def create_official():
    """Create a new Student Union official user with generated credentials."""
    client = MongoClient(MONGO_URI)
    db = client[DB_NAME]

    # Generate unique ID (ensure it doesn't exist)
    while True:
        user_id = generate_user_id()
        if not db.users.find_one({'student_id': user_id}):
            break

    password = generate_password()

    official_data = {
        'student_id': user_id,
        'role': 'official',
        'password_hash': hash_password(password),
        'created_at': datetime.now(timezone.utc)
    }

    db.users.insert_one(official_data)
    client.close()

    # Print credentials to stdout
    print(f"")
    print(f"=== SU Official User Created ===")
    print(f"")
    print(f"Student ID: {user_id}")
    print(f"Password:   {password}")
    print(f"Role:       official")
    print(f"")
    print(f"Login at:   http://localhost:3000")
    print(f"Dashboard:  http://localhost:3000/official")
    print(f"")


if __name__ == '__main__':
    create_official()
