"""
SecureVote Authentication & Authorization
=========================================
Role-based access control decorators and utilities.

Roles:
- student: Can vote in elections
- official: Can manage elections, view results
- admin: Full access including audit logs

Usage:
    @require_auth
    def protected_route():
        # Requires any authenticated user
        pass

    @require_role('admin')
    def admin_only_route():
        # Requires admin role
        pass

    @require_role(['admin', 'official'])
    def admin_or_official_route():
        # Requires admin OR official role
        pass
"""

from functools import wraps
from flask import request, jsonify, g, current_app
import jwt


# Role hierarchy (higher roles inherit lower role permissions)
ROLE_HIERARCHY = {
    'admin': ['admin', 'official', 'student'],
    'official': ['official', 'student'],
    'student': ['student']
}

VALID_ROLES = ['student', 'official', 'admin']


def decode_token(token):
    """
    Decode and validate a JWT token.

    Args:
        token: JWT token string (with or without 'Bearer ' prefix)

    Returns:
        Decoded token payload or None if invalid.
    """
    try:
        if token.startswith('Bearer '):
            token = token.split(' ')[1]

        payload = jwt.decode(
            token,
            current_app.config['SECRET_KEY'],
            algorithms=['HS256']
        )
        return payload
    except jwt.ExpiredSignatureError:
        return None
    except jwt.InvalidTokenError:
        return None


def get_current_user():
    """
    Get the current authenticated user from the request.

    Returns:
        User document from database or None.
    """
    return getattr(g, 'current_user', None)


def require_auth(f):
    """
    Decorator that requires authentication (any valid token).

    Sets g.current_user with the user document from database.
    """
    @wraps(f)
    def decorated(*args, **kwargs):
        token = request.headers.get('Authorization')

        if not token:
            return jsonify({'error': 'Authentication required'}), 401

        payload = decode_token(token)
        if not payload:
            return jsonify({'error': 'Invalid or expired token'}), 401

        # Get user from database
        from app import users_collection
        user = users_collection.find_one({'student_id': payload.get('student_id')})

        if not user:
            return jsonify({'error': 'User not found'}), 401

        # Store user in Flask's g object for access in route
        g.current_user = user
        g.token_payload = payload

        return f(*args, **kwargs)

    return decorated


def require_role(roles):
    """
    Decorator that requires specific role(s).

    Args:
        roles: Single role string or list of allowed roles.
               User must have at least one of the specified roles.

    Example:
        @require_role('admin')
        @require_role(['admin', 'official'])
    """
    if isinstance(roles, str):
        roles = [roles]

    def decorator(f):
        @wraps(f)
        def decorated(*args, **kwargs):
            token = request.headers.get('Authorization')

            if not token:
                return jsonify({'error': 'Authentication required'}), 401

            payload = decode_token(token)
            if not payload:
                return jsonify({'error': 'Invalid or expired token'}), 401

            # Get user from database
            from app import users_collection
            user = users_collection.find_one({'student_id': payload.get('student_id')})

            if not user:
                return jsonify({'error': 'User not found'}), 401

            # Check role
            user_role = user.get('role', 'student')  # Default to student
            user_effective_roles = ROLE_HIERARCHY.get(user_role, ['student'])

            # Check if user has any of the required roles
            if not any(role in user_effective_roles for role in roles):
                return jsonify({
                    'error': 'Insufficient permissions',
                    'required_roles': roles,
                    'your_role': user_role
                }), 403

            # Store user in Flask's g object
            g.current_user = user
            g.token_payload = payload

            return f(*args, **kwargs)

        return decorated

    return decorator


def create_token(student_id, role='student', expires_hours=1):
    """
    Create a JWT token for a user.

    Args:
        student_id: User's student ID
        role: User's role (for token payload, not authoritative)
        expires_hours: Token expiration in hours

    Returns:
        JWT token string.
    """
    import datetime

    payload = {
        'student_id': student_id,
        'role': role,  # Note: Role in token is for convenience, DB is authoritative
        'exp': datetime.datetime.now(datetime.timezone.utc) + datetime.timedelta(hours=expires_hours)
    }

    return jwt.encode(payload, current_app.config['SECRET_KEY'], algorithm='HS256')
