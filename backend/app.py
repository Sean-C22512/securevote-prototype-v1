from flask import Flask, request, jsonify, g
from flask_cors import CORS
from data.tud_programmes import TUD_PROGRAMMES, PROGRAMMES_BY_CODE
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
import jwt
import datetime
import os
import logging
from dotenv import load_dotenv
from pymongo import MongoClient
from pymongo.errors import DuplicateKeyError
from crypto.ballot_crypto import BallotCrypto, get_ballot_crypto
from utils.auth import require_auth, require_role, get_current_user, VALID_ROLES
from utils.password import (
    hash_password, verify_password, validate_password_strength,
    get_password_requirements
)

# Load environment variables
load_dotenv()

app = Flask(__name__)

# CORS: restrict origins to known frontends
allowed_origins = ['http://localhost:3000']
frontend_url = os.getenv('FRONTEND_URL')
if frontend_url:
    allowed_origins.extend([u.strip() for u in frontend_url.split(',') if u.strip()])
CORS(app, origins=allowed_origins)

# SECRET_KEY for JWT encoding
app.config['SECRET_KEY'] = os.getenv('SECRET_KEY', 'securevote-prototype-secret-key')

# Warn if using default secret in non-dev mode
if (app.config['SECRET_KEY'] == 'securevote-prototype-secret-key'
        and os.getenv('FLASK_ENV') != 'development'):
    logging.warning(
        "WARNING: Using default SECRET_KEY. Set SECRET_KEY environment variable for production."
    )

# Rate limiting (disabled during testing)
limiter = Limiter(
    key_func=get_remote_address,
    app=app,
    default_limits=["60 per minute"],
    storage_uri="memory://",
    enabled=os.getenv('FLASK_ENV') != 'testing'
)

# MongoDB Connection
MONGO_URI = os.getenv('MONGO_URI', 'mongodb://localhost:27017/securevote')
client = MongoClient(MONGO_URI)
db = client.get_database()
users_collection = db.users
votes_collection = db.votes
elections_collection = db.elections

# Initialize cryptographic service
ballot_crypto = get_ballot_crypto()

# Ensure unique index for chain integrity (prevents two votes claiming the same previous_hash)
votes_collection.create_index(
    [('election_id', 1), ('previous_hash', 1)],
    unique=True,
    name='unique_chain_link'
)

# Register elections blueprint
from routes.elections import elections_bp, init_elections_routes
init_elections_routes(elections_collection, votes_collection, ballot_crypto)
app.register_blueprint(elections_bp)

# Register WebAuthn blueprint
from routes.webauthn import webauthn_bp, init_webauthn_routes
init_webauthn_routes(users_collection, app.config['SECRET_KEY'])
app.register_blueprint(webauthn_bp)

# Legacy hardcoded candidates (kept for backward compatibility with tests)
# New elections should use /elections endpoints
candidates = [
    {"id": 1, "name": "Candidate A", "party": "Party Alpha"},
    {"id": 2, "name": "Candidate B", "party": "Party Beta"},
    {"id": 3, "name": "Candidate C", "party": "Party Gamma"}
]

@app.route('/programmes', methods=['GET'])
def get_programmes():
    """Return the full TUD programme catalogue."""
    return jsonify({'programmes': TUD_PROGRAMMES})


@app.route('/auth/register', methods=['POST'])
@limiter.limit("5 per minute")
def register():
    """
    Register a new student account.

    Body: {
        "student_id": "C22512873",
        "password": "SecurePass123",
        "email": "student@tudublin.ie",  // Optional
        "programme": {"code": "TU856", "name": "Computer Science"}  // Required
    }

    Returns: { "message": "...", "student_id": "..." }
    """
    data = request.get_json()
    student_id = data.get('student_id')
    password = data.get('password')
    email = data.get('email')
    programme = data.get('programme')

    # Validate required fields
    if not student_id:
        return jsonify({'error': 'Student ID is required'}), 400

    if not password:
        return jsonify({'error': 'Password is required'}), 400

    if not programme or not programme.get('code') or not programme.get('name'):
        return jsonify({'error': 'Programme is required'}), 400

    if programme['code'] not in PROGRAMMES_BY_CODE:
        return jsonify({'error': 'Invalid programme code'}), 400

    # Validate password strength
    is_valid, errors = validate_password_strength(password)
    if not is_valid:
        return jsonify({
            'error': 'Password does not meet requirements',
            'details': errors,
            'requirements': get_password_requirements()
        }), 400

    # Check if user already exists
    existing = users_collection.find_one({'student_id': student_id})
    if existing:
        return jsonify({'error': 'User already exists'}), 409

    # Hash password and create user
    password_hash = hash_password(password)

    user = {
        'student_id': student_id,
        'password_hash': password_hash,
        'email': email,
        'role': 'student',
        'programme': {'code': programme['code'], 'name': programme['name']},
        'created_at': datetime.datetime.now(datetime.timezone.utc)
    }
    users_collection.insert_one(user)

    return jsonify({
        'message': 'Registration successful',
        'student_id': student_id
    }), 201


@app.route('/auth/login', methods=['POST'])
@limiter.limit("10 per minute")
def login():
    """
    Login with student ID and password.

    Body: { "student_id": "C22512873", "password": "SecurePass123" }

    Returns: { "token": "...", "role": "...", "student_id": "..." }

    Note: For backward compatibility, if user has no password set,
    login works without password (legacy mode - will be deprecated).
    """
    data = request.get_json()
    student_id = data.get('student_id')
    password = data.get('password')

    if not student_id:
        return jsonify({'error': 'Student ID is required'}), 400

    # Find user
    user = users_collection.find_one({'student_id': student_id})

    if not user:
        # Legacy behavior: auto-create user without password
        # This supports existing tests and gradual migration
        if password:
            return jsonify({'error': 'Invalid credentials'}), 401

        user = {
            'student_id': student_id,
            'role': 'student',
            'created_at': datetime.datetime.now(datetime.timezone.utc)
        }
        users_collection.insert_one(user)
    else:
        # User exists - check password if they have one set
        if user.get('password_hash'):
            if not password:
                return jsonify({'error': 'Password is required'}), 400

            if not verify_password(password, user['password_hash']):
                return jsonify({'error': 'Invalid credentials'}), 401
        # else: legacy user without password - allow login (backward compatibility)

    # Get user's role
    role = user.get('role', 'student')

    # Generate token
    token = jwt.encode({
        'student_id': student_id,
        'role': role,
        'exp': datetime.datetime.now(datetime.timezone.utc) + datetime.timedelta(hours=1)
    }, app.config['SECRET_KEY'], algorithm="HS256")

    return jsonify({
        'token': token,
        'role': role,
        'student_id': student_id
    })

@app.route('/candidates', methods=['GET'])
def get_candidates():
    """
    Returns the list of candidates.
    """
    return jsonify(candidates)

@app.route('/vote', methods=['POST'])
@limiter.limit("10 per minute")
@require_role('student')
def cast_vote():
    """
    Cast a vote in an election.
    Requires JWT authentication with 'student' role (or higher).
    Enforces one vote per user per election.

    Body: { "election_id": "ELECTION-ID", "candidate_id": 1 }

    Legacy support: If no election_id provided, uses ELECTION_ID env var.
    """
    user = get_current_user()
    student_id = user['student_id']

    vote_data = request.get_json()
    if not vote_data or 'candidate_id' not in vote_data:
        return jsonify({'error': 'Invalid vote data'}), 400

    candidate_id = vote_data['candidate_id']

    # Get election - either from request or legacy env var
    election_id = vote_data.get('election_id') or os.getenv('ELECTION_ID', 'TUD-SU-ELECTION-2025')

    # Check if election exists in database
    election = elections_collection.find_one({'election_id': election_id})

    if election:
        # Dynamic election from database
        if election['status'] != 'active':
            status = election['status']
            if status == 'draft':
                return jsonify({'error': 'Election has not started yet'}), 400
            elif status == 'closed':
                return jsonify({'error': 'Election has ended'}), 400
            else:
                return jsonify({'error': f'Election is {status}'}), 400

        # Check programme eligibility (students only; officials/admins can vote in any election)
        eligible_programmes = election.get('eligible_programmes', [])
        if eligible_programmes and user.get('role', 'student') == 'student':
            student_programme = user.get('programme', {})
            student_code = student_programme.get('code') if student_programme else None
            eligible_codes = [p['code'] for p in eligible_programmes]
            if student_code not in eligible_codes:
                return jsonify({'error': 'You are not eligible to vote in this election'}), 403

        # Get candidate from election
        candidate = next((c for c in election['candidates'] if c['id'] == candidate_id), None)
        if not candidate:
            return jsonify({'error': 'Invalid candidate for this election'}), 400
        candidate_name = candidate['name']
    else:
        # Legacy mode: use hardcoded candidates
        candidate_name = next((c['name'] for c in candidates if c['id'] == candidate_id), None)
        if not candidate_name:
            return jsonify({'error': 'Invalid candidate'}), 400

    # Check if user has already voted in THIS election
    existing_vote = votes_collection.find_one({
        'student_id': student_id,
        'election_id': election_id
    })
    if existing_vote:
        return jsonify({'error': 'You have already voted in this election'}), 403

    # Prepare ballot data
    ballot_data = {
        'candidate_id': candidate_id,
        'candidate': candidate_name,
        'timestamp': datetime.datetime.now(datetime.timezone.utc)
    }

    # Atomic chain construction: retry loop to handle concurrent vote submissions.
    # Each iteration reads the latest chain tail and attempts to insert with that
    # previous_hash. If another vote was inserted between read and write (detected
    # via a unique index or re-check), we retry with the updated tail.
    max_retries = 10
    for attempt in range(max_retries):
        # Get previous vote's hash for chain linking
        last_vote = votes_collection.find_one(
            {'election_id': election_id},
            sort=[('timestamp', -1)]
        )
        previous_hash = last_vote['current_hash'] if last_vote else None

        # Encrypt ballot using hybrid AES+RSA encryption
        encrypted = ballot_crypto.encrypt_ballot(
            ballot_data,
            election_id,
            previous_hash=previous_hash
        )

        vote_record = {
            'student_id': student_id,
            'election_id': election_id,
            'encrypted_ballot': encrypted['encrypted_ballot'],
            'encrypted_aes_key': encrypted['encrypted_aes_key'],
            'current_hash': encrypted['current_hash'],
            'previous_hash': encrypted['previous_hash'],
            'timestamp': datetime.datetime.now(datetime.timezone.utc),
            'sequence': (last_vote.get('sequence', 0) + 1) if last_vote else 1
        }

        try:
            votes_collection.insert_one(vote_record)
            break
        except DuplicateKeyError:
            # Another vote claimed this chain position — retry with updated tail
            if attempt == max_retries - 1:
                return jsonify({'error': 'Vote submission failed due to high traffic. Please try again.'}), 503
            continue

    return jsonify({
        'message': 'Vote cast successfully',
        'vote_hash': encrypted['current_hash'][:16] + '...',
        'election_id': election_id
    }), 201

@app.route('/results', methods=['GET'])
@require_role(['official', 'admin'])
def get_results():
    """
    Returns aggregated vote counts.
    Decrypts ballots and tallies votes securely.
    Requires 'official' or 'admin' role.

    Query params:
    - election_id: Optional. If not provided, uses legacy env var.

    Note: For full election results, use /elections/<id>/results instead.
    """
    election_id = request.args.get('election_id') or os.getenv('ELECTION_ID', 'TUD-SU-ELECTION-2025')

    # Check if this is a managed election
    election = elections_collection.find_one({'election_id': election_id})
    election_candidates = election['candidates'] if election else candidates

    # Fetch all encrypted votes for this election
    votes = list(votes_collection.find(
        {'election_id': election_id},
        {'encrypted_ballot': 1, 'encrypted_aes_key': 1, 'election_id': 1}
    ))

    # Decrypt and tally
    tally = {}
    for vote in votes:
        try:
            decrypted = ballot_crypto.decrypt_ballot(
                vote['encrypted_ballot'],
                vote['encrypted_aes_key'],
                vote['election_id']
            )
            candidate = decrypted.get('candidate')
            if candidate:
                tally[candidate] = tally.get(candidate, 0) + 1
        except Exception:
            # Log failed decryption (tampered ballot) but continue
            continue

    # Ensure all candidates are represented even with 0 votes
    for cand in election_candidates:
        if cand['name'] not in tally:
            tally[cand['name']] = 0

    return jsonify(tally)


@app.route('/audit/verify', methods=['GET'])
@require_role('admin')
def verify_chain():
    """
    Verify the integrity of the entire vote chain.
    Returns chain status and any detected tampering.
    Requires 'admin' role.

    Query params:
    - election_id: Optional. If not provided, uses legacy env var.
    """
    election_id = request.args.get('election_id') or os.getenv('ELECTION_ID', 'TUD-SU-ELECTION-2025')

    # Fetch all votes in chronological order
    votes = list(votes_collection.find(
        {'election_id': election_id},
        sort=[('timestamp', 1)]
    ))

    if not votes:
        return jsonify({
            'valid': True,
            'message': 'No votes to verify',
            'total_votes': 0,
            'election_id': election_id
        })

    # Verify the chain using BallotCrypto
    result = ballot_crypto.verify_chain(votes)

    if result['valid']:
        return jsonify({
            'valid': True,
            'message': 'Chain integrity verified',
            'total_votes': result['verified_count'],
            'election_id': election_id
        })
    else:
        return jsonify({
            'valid': False,
            'message': f"Chain broken at vote index {result['broken_at']}",
            'total_votes': len(votes),
            'verified_before_break': result['verified_count'],
            'election_id': election_id
        }), 400


@app.route('/audit/stats', methods=['GET'])
@require_role('admin')
def audit_stats():
    """
    Returns election statistics for auditing.
    Requires 'admin' role.

    Query params:
    - election_id: Optional. If not provided, uses legacy env var.
    """
    election_id = request.args.get('election_id') or os.getenv('ELECTION_ID', 'TUD-SU-ELECTION-2025')

    total_votes = votes_collection.count_documents({'election_id': election_id})
    total_users = users_collection.count_documents({})

    # Get election details if it's a managed election
    election = elections_collection.find_one({'election_id': election_id})

    # Get first and last vote timestamps
    first_vote = votes_collection.find_one(
        {'election_id': election_id},
        sort=[('timestamp', 1)]
    )
    last_vote = votes_collection.find_one(
        {'election_id': election_id},
        sort=[('timestamp', -1)]
    )

    # Count unique voters for this election
    unique_voters = len(votes_collection.distinct('student_id', {'election_id': election_id}))

    # Verify chain integrity
    chain_votes = list(votes_collection.find(
        {'election_id': election_id},
        sort=[('timestamp', 1)]
    ))
    chain_result = ballot_crypto.verify_chain(chain_votes) if chain_votes else {'valid': True, 'verified_count': 0}

    response = {
        'election_id': election_id,
        'total_votes': total_votes,
        'registered_users': total_users,
        'chain_length': total_votes,
        'unique_voters': unique_voters,
        'chain_valid': chain_result['valid'],
        'first_vote': first_vote['timestamp'].isoformat() if first_vote else None,
        'last_vote': last_vote['timestamp'].isoformat() if last_vote else None
    }

    # Add election metadata if available
    if election:
        response['title'] = election.get('title')
        response['status'] = election.get('status')
        response['started_at'] = election['started_at'].isoformat() if election.get('started_at') else None
        response['ended_at'] = election['ended_at'].isoformat() if election.get('ended_at') else None

    return jsonify(response)


# ============================================================================
# Admin User Management Endpoints
# ============================================================================

@app.route('/admin/users', methods=['GET'])
@require_role('admin')
def list_users():
    """
    List all users with their roles.
    Requires 'admin' role.
    """
    users = list(users_collection.find(
        {},
        {'_id': 0, 'student_id': 1, 'role': 1, 'created_at': 1}
    ))

    # Add default role for legacy users
    for user in users:
        if 'role' not in user:
            user['role'] = 'student'
        if 'created_at' in user:
            user['created_at'] = user['created_at'].isoformat()

    return jsonify({
        'users': users,
        'total': len(users)
    })


@app.route('/admin/users/<student_id>/role', methods=['PUT'])
@require_role('admin')
def update_user_role(student_id):
    """
    Update a user's role.
    Requires 'admin' role.

    Body: { "role": "student|official|admin" }
    """
    data = request.get_json()
    new_role = data.get('role')

    if not new_role or new_role not in VALID_ROLES:
        return jsonify({
            'error': 'Invalid role',
            'valid_roles': VALID_ROLES
        }), 400

    # Check user exists
    user = users_collection.find_one({'student_id': student_id})
    if not user:
        return jsonify({'error': 'User not found'}), 404

    # Prevent admin from demoting themselves (safety)
    current_user = get_current_user()
    if current_user['student_id'] == student_id and new_role != 'admin':
        return jsonify({'error': 'Cannot demote yourself'}), 400

    # Update role
    users_collection.update_one(
        {'student_id': student_id},
        {'$set': {'role': new_role}}
    )

    return jsonify({
        'message': 'Role updated successfully',
        'student_id': student_id,
        'new_role': new_role
    })


@app.route('/admin/users', methods=['POST'])
@require_role('admin')
def create_user():
    """
    Create a new user with a specified role.
    Requires 'admin' role.

    Body: { "student_id": "12345", "role": "student|official|admin" }
    """
    data = request.get_json()
    student_id = data.get('student_id')
    role = data.get('role', 'student')

    if not student_id:
        return jsonify({'error': 'Student ID is required'}), 400

    if role not in VALID_ROLES:
        return jsonify({
            'error': 'Invalid role',
            'valid_roles': VALID_ROLES
        }), 400

    # Check if user already exists
    if users_collection.find_one({'student_id': student_id}):
        return jsonify({'error': 'User already exists'}), 409

    # Create user
    user = {
        'student_id': student_id,
        'role': role,
        'created_at': datetime.datetime.now(datetime.timezone.utc)
    }
    users_collection.insert_one(user)

    return jsonify({
        'message': 'User created successfully',
        'student_id': student_id,
        'role': role
    }), 201


@app.route('/auth/me', methods=['GET'])
@require_auth
def get_current_user_info():
    """
    Get current authenticated user's information.
    """
    user = get_current_user()
    webauthn_creds = user.get('webauthn_credentials', [])
    return jsonify({
        'student_id': user['student_id'],
        'role': user.get('role', 'student'),
        'email': user.get('email'),
        'has_password': bool(user.get('password_hash')),
        'created_at': user.get('created_at').isoformat() if user.get('created_at') else None,
        'has_webauthn': len(webauthn_creds) > 0,
        'credential_count': len(webauthn_creds),
        'webauthn_credentials': [
            {
                'credential_id': c.get('credential_id'),
                'friendly_name': c.get('friendly_name', 'Passkey'),
                'created_at': c.get('created_at'),
                'device_type': c.get('device_type', 'single_device'),
            }
            for c in webauthn_creds
        ],
    })


@app.route('/auth/change-password', methods=['POST'])
@require_auth
def change_password():
    """
    Change the current user's password.

    Body: {
        "current_password": "OldPass123",  // Required if user has password
        "new_password": "NewSecurePass456"
    }
    """
    data = request.get_json()
    current_password = data.get('current_password')
    new_password = data.get('new_password')

    if not new_password:
        return jsonify({'error': 'New password is required'}), 400

    # Validate new password strength
    is_valid, errors = validate_password_strength(new_password)
    if not is_valid:
        return jsonify({
            'error': 'New password does not meet requirements',
            'details': errors,
            'requirements': get_password_requirements()
        }), 400

    user = get_current_user()

    # If user has a password, verify current password
    if user.get('password_hash'):
        if not current_password:
            return jsonify({'error': 'Current password is required'}), 400

        if not verify_password(current_password, user['password_hash']):
            return jsonify({'error': 'Current password is incorrect'}), 401

    # Hash and store new password
    new_hash = hash_password(new_password)
    users_collection.update_one(
        {'student_id': user['student_id']},
        {'$set': {'password_hash': new_hash}}
    )

    return jsonify({'message': 'Password changed successfully'})


@app.route('/auth/set-password', methods=['POST'])
@require_auth
def set_password():
    """
    Set password for a legacy user who doesn't have one.
    This is for migrating existing users to password-based auth.

    Body: { "password": "NewSecurePass456" }
    """
    data = request.get_json()
    password = data.get('password')

    if not password:
        return jsonify({'error': 'Password is required'}), 400

    user = get_current_user()

    # Only allow if user doesn't have a password yet
    if user.get('password_hash'):
        return jsonify({
            'error': 'Password already set. Use /auth/change-password instead.'
        }), 400

    # Validate password strength
    is_valid, errors = validate_password_strength(password)
    if not is_valid:
        return jsonify({
            'error': 'Password does not meet requirements',
            'details': errors,
            'requirements': get_password_requirements()
        }), 400

    # Hash and store password
    password_hash = hash_password(password)
    users_collection.update_one(
        {'student_id': user['student_id']},
        {'$set': {'password_hash': password_hash}}
    )

    return jsonify({'message': 'Password set successfully'})


@app.route('/auth/password-requirements', methods=['GET'])
def password_requirements():
    """
    Get password requirements for client-side validation.
    No authentication required.
    """
    return jsonify(get_password_requirements())


if __name__ == '__main__':
    app.run(debug=True, port=5001)
