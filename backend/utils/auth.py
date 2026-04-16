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

# wraps preserves the original function's name and docstring when we wrap it with a decorator
from functools import wraps
# request gives us access to the incoming HTTP request (headers, body, etc.)
# jsonify converts a Python dict into a proper JSON HTTP response
# g is Flask's per-request storage object — data stored here lasts for one request only
# current_app gives us access to the running Flask application and its config
from flask import request, jsonify, g, current_app
# jwt is the PyJWT library used to create and verify JSON Web Tokens
import jwt


# Role hierarchy defines which roles each role level "inherits"
# An admin can do everything an official or student can do; an official can do everything a student can
ROLE_HIERARCHY = {
    'admin': ['admin', 'official', 'student'],   # Admin has all three effective roles
    'official': ['official', 'student'],          # Official also counts as a student
    'student': ['student']                        # Student only has the student role
}

# The complete list of valid role strings the system recognises
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
        # HTTP Authorization headers often look like "Bearer eyJ..." — strip the prefix if present
        if token.startswith('Bearer '):
            # Split on the space and take the second part (the actual token)
            token = token.split(' ')[1]

        # Ask PyJWT to decode and verify the token's signature using our app's secret key
        # algorithms=['HS256'] means we only accept tokens signed with HMAC-SHA256
        payload = jwt.decode(
            token,                                   # The JWT string to decode
            current_app.config['SECRET_KEY'],        # The secret used to verify the signature
            algorithms=['HS256']                     # Only accept tokens signed with this algorithm
        )
        # If decoding succeeded, return the payload dictionary (contains student_id, role, exp, etc.)
        return payload
    except jwt.ExpiredSignatureError:
        # The token's 'exp' timestamp has passed — the user must log in again
        return None  # Treat expired tokens the same as invalid ones
    except jwt.InvalidTokenError:
        # The token signature is wrong, the format is malformed, or some other JWT error occurred
        return None  # Return None to signal the token cannot be trusted


def get_current_user():
    """
    Get the current authenticated user from the request.

    Returns:
        User document from database or None.
    """
    # g.current_user is set by require_auth/require_role before the route function runs
    # getattr safely returns None if the attribute does not exist (e.g., on unauthenticated requests)
    return getattr(g, 'current_user', None)


def require_auth(f):
    """
    Decorator that requires authentication (any valid token).

    Sets g.current_user with the user document from database.
    """
    # @wraps(f) copies the name and docstring of the original function onto our wrapper
    @wraps(f)
    def decorated(*args, **kwargs):
        # Read the Authorization header from the incoming HTTP request
        token = request.headers.get('Authorization')

        # If no Authorization header was sent at all, reject the request immediately
        if not token:
            return jsonify({'error': 'Authentication required'}), 401  # 401 = Unauthorized

        # Try to decode the token; decode_token returns None if the token is invalid or expired
        payload = decode_token(token)
        if not payload:
            return jsonify({'error': 'Invalid or expired token'}), 401  # 401 = Unauthorized

        # Import here (inside the function) to avoid circular import issues at module load time
        from app import users_collection
        # Look up the user in the database using the student_id stored inside the token payload
        user = users_collection.find_one({'student_id': payload.get('student_id')})

        # If no matching user exists in the database, the token refers to a deleted or ghost account
        if not user:
            return jsonify({'error': 'User not found'}), 401  # 401 = Unauthorized

        # Store the full user document in Flask's g object so route functions can access it
        g.current_user = user
        # Also store the decoded token payload in case routes need token-level data (e.g., expiry)
        g.token_payload = payload

        # Call the original route function now that authentication has been confirmed
        return f(*args, **kwargs)

    # Return the wrapper function so Python knows to call decorated() instead of f() on each request
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
    # Allow callers to pass a single string like 'admin' instead of ['admin']
    if isinstance(roles, str):
        roles = [roles]  # Wrap the string in a list so the rest of the code works uniformly

    # The outer function (require_role) returns a decorator; the decorator wraps the route function
    def decorator(f):
        @wraps(f)  # Preserve the route function's original name and docstring
        def decorated(*args, **kwargs):
            # Read the Authorization header from the incoming HTTP request
            token = request.headers.get('Authorization')

            # Reject immediately if no token was provided
            if not token:
                return jsonify({'error': 'Authentication required'}), 401  # 401 = Unauthorized

            # Decode and validate the JWT — returns None if invalid or expired
            payload = decode_token(token)
            if not payload:
                return jsonify({'error': 'Invalid or expired token'}), 401  # 401 = Unauthorized

            # Import here to avoid circular imports at module startup
            from app import users_collection
            # Look up the user in MongoDB by their student_id from the token
            user = users_collection.find_one({'student_id': payload.get('student_id')})

            # If the user record is missing from the database, deny access
            if not user:
                return jsonify({'error': 'User not found'}), 401  # 401 = Unauthorized

            # Read the user's role from their database record
            # Default to 'student' if the role field is somehow missing (legacy user safety net)
            user_role = user.get('role', 'student')
            # Look up the full list of effective roles this user has based on the hierarchy
            # e.g., an admin also counts as an official and a student
            user_effective_roles = ROLE_HIERARCHY.get(user_role, ['student'])

            # Check whether the user has at least one of the roles required for this route
            # any() returns True as soon as it finds a match — no need to check every role
            if not any(role in user_effective_roles for role in roles):
                # The user is authenticated but does not have the required permissions — 403 Forbidden
                return jsonify({
                    'error': 'Insufficient permissions',
                    'required_roles': roles,      # Tell the caller what roles would have been accepted
                    'your_role': user_role        # Tell the caller what role the user actually has
                }), 403  # 403 = Forbidden (authenticated but not authorised)

            # Authentication and authorisation both passed — store the user in Flask's g object
            g.current_user = user        # Full user document from MongoDB
            g.token_payload = payload    # Decoded JWT payload

            # Call the original route function with all its original arguments
            return f(*args, **kwargs)

        # Return the inner wrapper so Python uses it instead of the original route function
        return decorated

    # Return the decorator so it can be applied with @require_role(...)
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
    # datetime is imported here (inside the function) to keep the top-level imports clean
    import datetime

    # Build the payload dictionary that will be signed and encoded into the JWT
    payload = {
        'student_id': student_id,   # Identifies which user this token belongs to
        'role': role,               # Note: Role in token is for convenience, DB is authoritative
        # exp is the standard JWT claim for expiry time — PyJWT checks this automatically on decode
        # We compute: current UTC time + the requested number of hours
        'exp': datetime.datetime.now(datetime.timezone.utc) + datetime.timedelta(hours=expires_hours)
    }

    # Sign the payload with our app's secret key using HMAC-SHA256 (HS256)
    # jwt.encode returns the token as a string ready to send to the client
    return jwt.encode(payload, current_app.config['SECRET_KEY'], algorithm='HS256')
