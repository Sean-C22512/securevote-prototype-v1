"""
SecureVote Password Utilities
=============================
Secure password hashing and validation using bcrypt.

Security Features:
- bcrypt with automatic salting
- Configurable work factor (cost)
- Timing-safe password comparison
- Password strength validation

Usage:
    from utils.password import hash_password, verify_password, validate_password_strength

    # Hash a password for storage
    hashed = hash_password("user_password")

    # Verify a password
    if verify_password("user_password", hashed):
        print("Password correct!")

    # Validate password strength
    is_valid, errors = validate_password_strength("weak")
"""

import bcrypt
import re
from typing import Tuple, List


# Work factor for bcrypt (higher = more secure but slower)
# 12 is a good balance for 2024+ (takes ~250ms to hash)
BCRYPT_WORK_FACTOR = 12

# Password requirements
MIN_PASSWORD_LENGTH = 8
MAX_PASSWORD_LENGTH = 128
REQUIRE_UPPERCASE = True
REQUIRE_LOWERCASE = True
REQUIRE_DIGIT = True
REQUIRE_SPECIAL = False  # Optional for prototype


def hash_password(password: str) -> str:
    """
    Hash a password using bcrypt.

    Args:
        password: Plain text password to hash

    Returns:
        Hashed password as string (safe for database storage)

    Raises:
        ValueError: If password is empty or too long
    """
    if not password:
        raise ValueError("Password cannot be empty")

    if len(password) > MAX_PASSWORD_LENGTH:
        raise ValueError(f"Password cannot exceed {MAX_PASSWORD_LENGTH} characters")

    # Encode password to bytes
    password_bytes = password.encode('utf-8')

    # Generate salt and hash
    salt = bcrypt.gensalt(rounds=BCRYPT_WORK_FACTOR)
    hashed = bcrypt.hashpw(password_bytes, salt)

    # Return as string for database storage
    return hashed.decode('utf-8')


def verify_password(password: str, hashed: str) -> bool:
    """
    Verify a password against a bcrypt hash.

    This function is timing-safe to prevent timing attacks.

    Args:
        password: Plain text password to verify
        hashed: Bcrypt hash to compare against

    Returns:
        True if password matches, False otherwise
    """
    if not password or not hashed:
        return False

    try:
        password_bytes = password.encode('utf-8')
        hashed_bytes = hashed.encode('utf-8')
        return bcrypt.checkpw(password_bytes, hashed_bytes)
    except (ValueError, TypeError):
        return False


def validate_password_strength(password: str) -> Tuple[bool, List[str]]:
    """
    Validate password meets strength requirements.

    Args:
        password: Password to validate

    Returns:
        Tuple of (is_valid, list_of_errors)
        If valid, errors list will be empty.
    """
    errors = []

    if not password:
        return (False, ["Password is required"])

    # Length checks
    if len(password) < MIN_PASSWORD_LENGTH:
        errors.append(f"Password must be at least {MIN_PASSWORD_LENGTH} characters")

    if len(password) > MAX_PASSWORD_LENGTH:
        errors.append(f"Password cannot exceed {MAX_PASSWORD_LENGTH} characters")

    # Character type checks
    if REQUIRE_UPPERCASE and not re.search(r'[A-Z]', password):
        errors.append("Password must contain at least one uppercase letter")

    if REQUIRE_LOWERCASE and not re.search(r'[a-z]', password):
        errors.append("Password must contain at least one lowercase letter")

    if REQUIRE_DIGIT and not re.search(r'\d', password):
        errors.append("Password must contain at least one digit")

    if REQUIRE_SPECIAL and not re.search(r'[!@#$%^&*(),.?":{}|<>]', password):
        errors.append("Password must contain at least one special character")

    # Common password check (basic list - could be expanded)
    common_passwords = [
        'password', 'password123', '12345678', 'qwerty123',
        'letmein', 'welcome', 'admin123', 'iloveyou'
    ]
    if password.lower() in common_passwords:
        errors.append("Password is too common")

    return (len(errors) == 0, errors)


def get_password_requirements() -> dict:
    """
    Get current password requirements for client-side validation.

    Returns:
        Dictionary describing password requirements
    """
    return {
        'min_length': MIN_PASSWORD_LENGTH,
        'max_length': MAX_PASSWORD_LENGTH,
        'require_uppercase': REQUIRE_UPPERCASE,
        'require_lowercase': REQUIRE_LOWERCASE,
        'require_digit': REQUIRE_DIGIT,
        'require_special': REQUIRE_SPECIAL
    }
