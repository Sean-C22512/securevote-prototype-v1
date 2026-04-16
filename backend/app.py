# ── Flask and standard library imports ───────────────────────────────────────
# Flask: the web framework that handles HTTP routing and request/response objects.
# request: the current incoming HTTP request (body, headers, query params).
# jsonify: converts a Python dict into a proper JSON HTTP response.
# g:       Flask's per-request global store — we use it to attach the current user
#          after JWT verification so any function within the same request can call
#          get_current_user() without hitting MongoDB again.
from flask import Flask, request, jsonify, g

# flask_cors: Cross-Origin Resource Sharing middleware.
# Without this, the browser blocks the React frontend (on port 3000) from
# calling this API (on port 5001) because they have different origins.
from flask_cors import CORS

# TUD programme data — a list of all valid TU Dublin courses.
# Used to validate programme codes during registration.
from data.tud_programmes import TUD_PROGRAMMES, PROGRAMMES_BY_CODE

# flask_limiter: rate limiting middleware that restricts how many requests a
# single IP address can make in a given time window.
# get_remote_address: the key function that identifies callers by their IP.
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address

# jwt (PyJWT): JSON Web Token library for creating and decoding signed tokens.
# Tokens are issued on login and sent in the Authorization header on every request.
import jwt

# datetime: used to stamp vote records and to set JWT expiry times.
import datetime

# os: read environment variables (MONGO_URI, SECRET_KEY, etc.) set at deploy time.
import os

# logging: write warnings to the server log (e.g. insecure default secret key).
import logging

# dotenv: loads a local .env file so developers can set environment variables
# without exporting them in their shell session.
from dotenv import load_dotenv

# pymongo: the official MongoDB driver for Python.
# MongoClient:    opens the connection pool.
# DuplicateKeyError: raised when a $unique index constraint is violated —
#                    we use this to enforce atomic chain link insertion.
from pymongo import MongoClient
from pymongo.errors import DuplicateKeyError

# Internal crypto service — wraps AES+RSA ballot encryption/decryption.
from crypto.ballot_crypto import BallotCrypto, get_ballot_crypto

# Auth utilities:
# require_auth:  decorator that rejects requests without a valid JWT.
# require_role:  decorator that rejects requests whose JWT role doesn't match.
# get_current_user: returns the MongoDB user doc for the logged-in caller.
# VALID_ROLES:   the allowed role strings: ['student', 'official', 'admin'].
from utils.auth import require_auth, require_role, get_current_user, VALID_ROLES

# Password utilities:
# hash_password:               bcrypt-hash a plaintext password for storage.
# verify_password:             check a plaintext password against a stored hash.
# validate_password_strength:  enforce complexity rules (length, uppercase, etc.).
# get_password_requirements:   return a human-readable list of rules for the UI.
from utils.password import (
    hash_password, verify_password, validate_password_strength,
    get_password_requirements
)

# ── Load environment variables from .env (if present) ─────────────────────────
# In production on AWS the variables come from the EC2 instance environment;
# locally they come from the .env file in the backend directory.
load_dotenv()

# ── Create the Flask application ──────────────────────────────────────────────
app = Flask(__name__)

# ── Configure CORS (Cross-Origin Resource Sharing) ────────────────────────────
# Browsers enforce the same-origin policy — a page loaded from one URL can't
# make AJAX requests to a different URL unless the server explicitly allows it.
# We whitelist localhost:3000 (dev) plus any URLs in the FRONTEND_URL env var
# (e.g. "https://securevote.ie,https://www.securevote.ie" in production).
# CORS: restrict origins to known frontends
allowed_origins = ['http://localhost:3000']
frontend_url = os.getenv('FRONTEND_URL')
if frontend_url:
    # FRONTEND_URL may contain multiple comma-separated origins — split and strip.
    allowed_origins.extend([u.strip() for u in frontend_url.split(',') if u.strip()])
CORS(app,
     origins=allowed_origins,
     allow_headers=['Content-Type', 'Authorization'],  # Authorization carries the JWT
     methods=['GET', 'POST', 'PUT', 'DELETE', 'OPTIONS'],
     max_age=600)  # browsers cache the CORS preflight for 10 minutes

# ── JWT secret key ────────────────────────────────────────────────────────────
# All JWTs are signed (HS256) with this secret.  Anyone who knows this key can
# forge tokens, so it MUST be a long random value in production.
# SECRET_KEY for JWT encoding
app.config['SECRET_KEY'] = os.getenv('SECRET_KEY', 'securevote-prototype-secret-key')

# ── Warn loudly if the default (insecure) key is used outside development ──────
# This catches the most common deployment mistake: forgetting to set the secret.
# Warn if using default secret in non-dev mode
if (app.config['SECRET_KEY'] == 'securevote-prototype-secret-key'
        and os.getenv('FLASK_ENV') != 'development'):
    logging.warning(
        "WARNING: Using default SECRET_KEY. Set SECRET_KEY environment variable for production."
    )

# ── Rate limiting ──────────────────────────────────────────────────────────────
# Protects against brute-force attacks by limiting how often a single IP can
# call any endpoint.  The default is 60 requests per minute.
# Individual sensitive endpoints (login, register) apply stricter per-route limits.
# Disabled entirely during test runs so automated tests aren't throttled.
# Rate limiting (disabled during testing)
limiter = Limiter(
    key_func=get_remote_address,   # rate-limit by caller IP address
    app=app,
    default_limits=["60 per minute"],
    storage_uri="memory://",       # store counters in RAM (fine for a single instance)
    enabled=os.getenv('FLASK_ENV') != 'testing'  # skip rate limits in test mode
)

# ── MongoDB connection ─────────────────────────────────────────────────────────
# MONGO_URI defaults to localhost for local development; in production it points
# to the Atlas cluster or the Docker-networked MongoDB container.
# MongoDB Connection
MONGO_URI = os.getenv('MONGO_URI', 'mongodb://localhost:27017/securevote')
client = MongoClient(MONGO_URI)
db = client.get_database()          # uses the database name embedded in the URI
users_collection = db.users         # stores user accounts and credentials
votes_collection = db.votes         # stores every encrypted ballot
elections_collection = db.elections # stores election metadata

# ── Initialise the cryptographic service ──────────────────────────────────────
# This loads (or generates) the RSA key pair from disk — done once at startup
# so the first request doesn't pay the cost of key generation.
# Initialize cryptographic service
ballot_crypto = get_ballot_crypto()

# ── Create the vote chain integrity index ─────────────────────────────────────
# This unique compound index ensures that no two votes for the same election
# can claim the same previous_hash.  Because the previous_hash of the next vote
# is derived from the current vote's hash, this effectively makes the chain
# append-only and prevents two concurrent submissions from stomping on each other
# (the second one will raise DuplicateKeyError and must retry with the updated tail).
# Ensure unique index for chain integrity (prevents two votes claiming the same previous_hash)
votes_collection.create_index(
    [('election_id', 1), ('previous_hash', 1)],
    unique=True,
    name='unique_chain_link'
)

# ── Register the Elections blueprint ──────────────────────────────────────────
# Blueprints are registered AFTER the DB handles exist so we can inject them
# via init_elections_routes().  All election endpoints will be prefixed /elections.
# Register elections blueprint
from routes.elections import elections_bp, init_elections_routes
init_elections_routes(elections_collection, votes_collection, ballot_crypto)
app.register_blueprint(elections_bp)

# ── Register the WebAuthn (biometric) blueprint ───────────────────────────────
# All biometric endpoints will be prefixed /auth/webauthn.
# Register WebAuthn blueprint
from routes.webauthn import webauthn_bp, init_webauthn_routes
init_webauthn_routes(users_collection, app.config['SECRET_KEY'])
app.register_blueprint(webauthn_bp)

# ── Legacy hardcoded candidates ───────────────────────────────────────────────
# Before the full elections blueprint was built, the system had three fixed
# candidates.  Kept here so old API tests and the legacy /vote endpoint still work.
# New elections should use /elections endpoints
candidates = [
    {"id": 1, "name": "Candidate A", "party": "Party Alpha"},
    {"id": 2, "name": "Candidate B", "party": "Party Beta"},
    {"id": 3, "name": "Candidate C", "party": "Party Gamma"}
]

# ── GET /programmes ────────────────────────────────────────────────────────────
@app.route('/programmes', methods=['GET'])
def get_programmes():
    """Return the full TUD programme catalogue."""
    # No authentication required — the programme list is public data used on
    # the registration form before the user has an account.
    return jsonify({'programmes': TUD_PROGRAMMES})


# ── POST /auth/register ────────────────────────────────────────────────────────
@app.route('/auth/register', methods=['POST'])
@limiter.limit("5 per minute")  # strict limit: max 5 registration attempts per minute per IP
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

    # ── Basic field presence validation ───────────────────────────────────────
    if not student_id:
        return jsonify({'error': 'Student ID is required'}), 400

    if not password:
        return jsonify({'error': 'Password is required'}), 400

    # ── Programme is required and must be a known TUD code ─────────────────────
    # We don't allow freeform programme entry — it must match the official list.
    if not programme or not programme.get('code') or not programme.get('name'):
        return jsonify({'error': 'Programme is required'}), 400

    if programme['code'] not in PROGRAMMES_BY_CODE:
        return jsonify({'error': 'Invalid programme code'}), 400

    # ── Password strength check ───────────────────────────────────────────────
    # Returns a list of failure reasons so the frontend can display them all
    # at once (e.g. "needs uppercase", "too short") rather than one at a time.
    # Validate password strength
    is_valid, errors = validate_password_strength(password)
    if not is_valid:
        return jsonify({
            'error': 'Password does not meet requirements',
            'details': errors,
            'requirements': get_password_requirements()
        }), 400

    # ── Check whether this student ID already exists ───────────────────────────
    # Check if user already exists
    existing = users_collection.find_one({'student_id': student_id})
    if existing:
        # ── Special case: admin-provisioned account ───────────────────────────
        # An admin might pre-create a user (e.g. an official) without a password.
        # If the account exists but has no password_hash, allow the student to
        # "complete" their registration by setting a password.
        if existing.get('password_hash'):
            return jsonify({'error': 'User already exists'}), 409

        # Hash the chosen password and update the pre-existing account.
        password_hash = hash_password(password)
        users_collection.update_one(
            {'student_id': student_id},
            {'$set': {
                'password_hash': password_hash,
                'email': email or existing.get('email'),  # keep existing email if none supplied
                'programme': {'code': programme['code'], 'name': programme['name']},
            }}
        )
        return jsonify({
            'message': 'Registration successful',
            'student_id': student_id
        }), 201

    # ── Brand-new user — hash password and insert ─────────────────────────────
    # bcrypt hashes the password with an automatically generated salt.
    # We never store the plaintext password.
    # Hash password and create new user
    password_hash = hash_password(password)

    user = {
        'student_id': student_id,
        'password_hash': password_hash,
        'email': email,
        'role': 'student',          # all self-registered users start as students
        'programme': {'code': programme['code'], 'name': programme['name']},
        'created_at': datetime.datetime.now(datetime.timezone.utc)
    }
    users_collection.insert_one(user)

    return jsonify({
        'message': 'Registration successful',
        'student_id': student_id
    }), 201


# ── POST /auth/login ───────────────────────────────────────────────────────────
@app.route('/auth/login', methods=['POST'])
@limiter.limit("10 per minute")  # brute-force protection: max 10 login attempts per minute
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

    # ── Look up the user by student ID ────────────────────────────────────────
    # Find user
    user = users_collection.find_one({'student_id': student_id})

    if not user:
        # ── Legacy behaviour: auto-create passwordless user ────────────────────
        # The very first version of SecureVote had no registration — any student
        # could log in just by providing their ID.  We preserve this for tests
        # and gradual migration.  If a password was supplied, we refuse (it
        # implies the caller expected an account to exist).
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
        # ── User exists: verify password if they have one ─────────────────────
        # User exists - check password if they have one set
        if user.get('password_hash'):
            if not password:
                return jsonify({'error': 'Password is required'}), 400

            # verify_password uses bcrypt to compare the plaintext with the hash.
            if not verify_password(password, user['password_hash']):
                return jsonify({'error': 'Invalid credentials'}), 401
        # else: legacy user without password - allow login (backward compatibility)

    # ── Read the user's role (default to 'student' if missing) ────────────────
    # Get user's role
    role = user.get('role', 'student')

    # ── Issue a signed JWT ─────────────────────────────────────────────────────
    # The token contains: who the user is (student_id), their role, and an
    # expiry time 1 hour from now.  The HS256 signature means it can't be
    # forged without the SECRET_KEY.
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

# ── GET /candidates ────────────────────────────────────────────────────────────
@app.route('/candidates', methods=['GET'])
def get_candidates():
    """
    Returns the list of candidates.
    """
    # Legacy endpoint returning the hardcoded candidate list above.
    # New code should query /elections/<id> for the candidate list.
    return jsonify(candidates)

# ── POST /vote ─────────────────────────────────────────────────────────────────
@app.route('/vote', methods=['POST'])
@limiter.limit("10 per minute")  # limit vote submissions to prevent flooding
@require_role('student')         # only students (or higher roles) can cast a vote
def cast_vote():
    """
    Cast a vote in an election.
    Requires JWT authentication with 'student' role (or higher).
    Enforces one vote per user per election.

    Body: { "election_id": "ELECTION-ID", "candidate_id": 1 }

    Legacy support: If no election_id provided, uses ELECTION_ID env var.
    """
    # ── Identify the voter ────────────────────────────────────────────────────
    user = get_current_user()
    student_id = user['student_id']

    vote_data = request.get_json()
    if not vote_data or 'candidate_id' not in vote_data:
        return jsonify({'error': 'Invalid vote data'}), 400

    candidate_id = vote_data['candidate_id']

    # ── Resolve which election this vote is for ───────────────────────────────
    # Get election - either from request or legacy env var
    election_id = vote_data.get('election_id') or os.getenv('ELECTION_ID', 'TUD-SU-ELECTION-2025')

    # ── Look up the election in MongoDB ───────────────────────────────────────
    # Check if election exists in database
    election = elections_collection.find_one({'election_id': election_id})

    if election:
        # ── Managed election path ─────────────────────────────────────────────
        # Dynamic election from database
        if election['status'] != 'active':
            # Voting is only allowed when the election is in 'active' state.
            status = election['status']
            if status == 'draft':
                return jsonify({'error': 'Election has not started yet'}), 400
            elif status == 'closed':
                return jsonify({'error': 'Election has ended'}), 400
            else:
                return jsonify({'error': f'Election is {status}'}), 400

        # ── Programme eligibility check ───────────────────────────────────────
        # If the election is restricted to specific programmes, verify the
        # student's enrolled programme is in the eligible list.
        # Check programme eligibility (students only; officials/admins can vote in any election)
        eligible_programmes = election.get('eligible_programmes', [])
        if eligible_programmes and user.get('role', 'student') == 'student':
            student_programme = user.get('programme', {})
            student_code = student_programme.get('code') if student_programme else None
            eligible_codes = [p['code'] for p in eligible_programmes]
            if student_code not in eligible_codes:
                return jsonify({'error': 'You are not eligible to vote in this election'}), 403

        # ── Validate the chosen candidate belongs to this election ─────────────
        # Get candidate from election
        candidate = next((c for c in election['candidates'] if c['id'] == candidate_id), None)
        if not candidate:
            return jsonify({'error': 'Invalid candidate for this election'}), 400
        candidate_name = candidate['name']
    else:
        # ── Legacy mode — fall back to the hardcoded candidates list ──────────
        # Legacy mode: use hardcoded candidates
        candidate_name = next((c['name'] for c in candidates if c['id'] == candidate_id), None)
        if not candidate_name:
            return jsonify({'error': 'Invalid candidate'}), 400

    # ── One-vote-per-person enforcement ───────────────────────────────────────
    # We check BEFORE encrypting to fail fast — but the chain index is the
    # ultimate guard against duplicate votes at the DB level.
    # Check if user has already voted in THIS election
    existing_vote = votes_collection.find_one({
        'student_id': student_id,
        'election_id': election_id
    })
    if existing_vote:
        return jsonify({'error': 'You have already voted in this election'}), 403

    # ── Build the plaintext ballot payload ────────────────────────────────────
    ballot_data = {
        'candidate_id': candidate_id,
        'candidate': candidate_name,
        'timestamp': datetime.datetime.now(datetime.timezone.utc)
    }

    # ── Atomic chain construction with retry loop ─────────────────────────────
    # The vote chain requires each new vote to reference the hash of the
    # previous vote.  Under concurrent load, two votes might both read the
    # same "last vote" and try to insert with the same previous_hash.
    # MongoDB's unique index on (election_id, previous_hash) rejects the second
    # insert with DuplicateKeyError, and we simply retry with the freshly read tail.
    # Atomic chain construction: retry loop to handle concurrent vote submissions.
    # Each iteration reads the latest chain tail and attempts to insert with that
    # previous_hash. If another vote was inserted between read and write (detected
    # via a unique index or re-check), we retry with the updated tail.
    max_retries = 10
    for attempt in range(max_retries):
        # ── Read the current chain tail ───────────────────────────────────────
        # Get previous vote's hash for chain linking
        last_vote = votes_collection.find_one(
            {'election_id': election_id},
            sort=[('timestamp', -1)]  # most recent vote first
        )
        previous_hash = last_vote['current_hash'] if last_vote else None

        # ── Encrypt the ballot using hybrid AES+RSA ───────────────────────────
        # Each ballot gets its own random AES-256 key; that key is then RSA-
        # encrypted so only the admin can decrypt it.  The election_id is
        # included as AAD so ballots can't be swapped between elections.
        # Encrypt ballot using hybrid AES+RSA encryption
        encrypted = ballot_crypto.encrypt_ballot(
            ballot_data,
            election_id,
            previous_hash=previous_hash
        )

        # ── Assemble the vote document for MongoDB ────────────────────────────
        vote_record = {
            'student_id': student_id,           # who voted (can be audited but ballot is secret)
            'election_id': election_id,
            'encrypted_ballot': encrypted['encrypted_ballot'],   # AES-GCM ciphertext (base64)
            'encrypted_aes_key': encrypted['encrypted_aes_key'], # RSA-encrypted AES key (base64)
            'current_hash': encrypted['current_hash'],           # this vote's chain hash
            'previous_hash': encrypted['previous_hash'],         # links back to the previous vote
            'timestamp': datetime.datetime.now(datetime.timezone.utc),
            'sequence': (last_vote.get('sequence', 0) + 1) if last_vote else 1  # 1-based vote number
        }

        try:
            # ── Attempt to insert — this may fail if a concurrent vote beat us ─
            votes_collection.insert_one(vote_record)
            break  # success — exit the retry loop
        except DuplicateKeyError:
            # ── Another vote claimed this chain position — try again ───────────
            # Another vote claimed this chain position — retry with updated tail
            if attempt == max_retries - 1:
                # We've exhausted all retries (very unlikely under normal load).
                return jsonify({'error': 'Vote submission failed due to high traffic. Please try again.'}), 503
            continue  # go back to the top of the loop and re-read the tail

    return jsonify({
        'message': 'Vote cast successfully',
        # Return only the first 16 characters of the hash so the user can
        # verify their ballot appears in the audit log without exposing the full hash.
        'vote_hash': encrypted['current_hash'][:16] + '...',
        'election_id': election_id
    }), 201

# ── GET /results ───────────────────────────────────────────────────────────────
@app.route('/results', methods=['GET'])
@require_role(['official', 'admin'])  # students cannot see raw results
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

    # ── Check if this is a managed election ───────────────────────────────────
    # Check if this is a managed election
    election = elections_collection.find_one({'election_id': election_id})
    election_candidates = election['candidates'] if election else candidates

    # ── Fetch all encrypted vote documents for this election ──────────────────
    # We only request the fields needed for decryption to limit data exposure.
    # Fetch all encrypted votes for this election
    votes = list(votes_collection.find(
        {'election_id': election_id},
        {'encrypted_ballot': 1, 'encrypted_aes_key': 1, 'election_id': 1}
    ))

    # ── Decrypt every ballot and tally the results ─────────────────────────────
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
            # A tampered or corrupted ballot is skipped — the chain verification
            # endpoint (/audit/verify) will flag the exact broken link separately.
            continue

    # ── Ensure all candidates appear even with zero votes ─────────────────────
    # Ensure all candidates are represented even with 0 votes
    for cand in election_candidates:
        if cand['name'] not in tally:
            tally[cand['name']] = 0

    return jsonify(tally)


# ── GET /audit/verify ─────────────────────────────────────────────────────────
@app.route('/audit/verify', methods=['GET'])
@require_role('admin')  # chain verification is admin-only
def verify_chain():
    """
    Verify the integrity of the entire vote chain.
    Returns chain status and any detected tampering.
    Requires 'admin' role.

    Query params:
    - election_id: Optional. If not provided, uses legacy env var.
    """
    election_id = request.args.get('election_id') or os.getenv('ELECTION_ID', 'TUD-SU-ELECTION-2025')

    # ── Retrieve all votes in chronological order ──────────────────────────────
    # We sort by timestamp ascending so we walk the chain in the correct direction.
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

    # ── Run the full chain verification via BallotCrypto ─────────────────────
    # This recomputes every SHA-256 hash from scratch and checks continuity.
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
        # Report which vote index first broke — this tells an auditor exactly
        # where to investigate potential tampering.
        return jsonify({
            'valid': False,
            'message': f"Chain broken at vote index {result['broken_at']}",
            'total_votes': len(votes),
            'verified_before_break': result['verified_count'],
            'election_id': election_id
        }), 400


# ── GET /audit/stats ──────────────────────────────────────────────────────────
@app.route('/audit/stats', methods=['GET'])
@require_role('admin')  # statistics dashboard is admin-only
def audit_stats():
    """
    Returns election statistics for auditing.
    Requires 'admin' role.

    Query params:
    - election_id: Optional. If not provided, uses legacy env var.
    """
    election_id = request.args.get('election_id') or None
    global_mode = election_id is None  # no election specified — return system-wide totals

    if not election_id:
        election_id = os.getenv('ELECTION_ID', 'TUD-SU-ELECTION-2025')

    # ── Count votes — either for one election or system-wide ──────────────────
    # In global mode we count ALL votes across every election.
    total_votes = votes_collection.count_documents({}) if global_mode else votes_collection.count_documents({'election_id': election_id})
    total_users = users_collection.count_documents({})  # total registered users

    # ── Fetch election metadata for the response ───────────────────────────────
    # Get election details if it's a managed election
    election = elections_collection.find_one({'election_id': election_id})

    # ── Get first and last vote timestamps for the timeline widget ─────────────
    # Get first and last vote timestamps
    first_vote = votes_collection.find_one(
        {'election_id': election_id},
        sort=[('timestamp', 1)]   # ascending → earliest vote
    )
    last_vote = votes_collection.find_one(
        {'election_id': election_id},
        sort=[('timestamp', -1)]  # descending → most recent vote
    )

    # ── Count unique voters (prevents double-counting) ─────────────────────────
    # Count unique voters for this election
    unique_voters = len(votes_collection.distinct('student_id', {'election_id': election_id}))

    # ── Select which election to verify chain integrity for ───────────────────
    # In global mode there's no single election to check, so we pick the most
    # recently created one as a representative sample.
    # Verify chain integrity — in global mode use the most recent election
    if global_mode:
        most_recent = elections_collection.find_one({}, sort=[('created_at', -1)])
        chain_election_id = most_recent['election_id'] if most_recent else election_id
    else:
        chain_election_id = election_id

    chain_votes = list(votes_collection.find(
        {'election_id': chain_election_id},
        sort=[('timestamp', 1)]
    ))
    chain_result = ballot_crypto.verify_chain(chain_votes) if chain_votes else {'valid': True, 'verified_count': 0}

    # ── Build the stats response ───────────────────────────────────────────────
    response = {
        'election_id': election_id,
        'total_votes': total_votes,
        'registered_users': total_users,
        'chain_length': total_votes,          # synonymous with total_votes for the current election
        'unique_voters': unique_voters,
        'chain_valid': chain_result['valid'], # True = no tampering detected
        'first_vote': first_vote['timestamp'].isoformat() if first_vote else None,
        'last_vote': last_vote['timestamp'].isoformat() if last_vote else None
    }

    # ── Attach election metadata when available ────────────────────────────────
    # Add election metadata if available
    if election:
        response['title'] = election.get('title')
        response['status'] = election.get('status')
        response['started_at'] = election['started_at'].isoformat() if election.get('started_at') else None
        response['ended_at'] = election['ended_at'].isoformat() if election.get('ended_at') else None

    return jsonify(response)


# ── GET /audit/blocks ─────────────────────────────────────────────────────────
@app.route('/audit/blocks', methods=['GET'])
@require_role('admin')  # detailed block data is admin-only
def audit_blocks():
    """
    Returns per-block verification data for the audit trail view.
    Each block includes its hashes and individual verification status.
    Requires 'admin' role.

    Query params:
    - election_id: Optional. Defaults to env var.
    - status: Optional. 'verified' or 'tampered' to filter.
    """
    election_id = request.args.get('election_id') or os.getenv('ELECTION_ID', 'TUD-SU-ELECTION-2025')
    status_filter = request.args.get('status', '')  # optional filter: 'verified' or 'tampered'

    # ── Fetch all votes in chronological order ────────────────────────────────
    votes = list(votes_collection.find(
        {'election_id': election_id},
        sort=[('timestamp', 1)]
    ))

    if not votes:
        return jsonify({
            'blocks': [],
            'verified_count': 0,
            'tampered_count': 0,
            'chain_valid': True,
            'total': 0,
            'election_id': election_id,
            'last_verified': datetime.datetime.utcnow().isoformat()
        })

    # ── Run per-block verification ────────────────────────────────────────────
    # Run per-block verification via BallotCrypto
    chain_result = ballot_crypto.verify_chain(votes)
    details = chain_result.get('details', [])
    broken_at = chain_result.get('broken_at', -1)  # -1 means no break detected

    # ── Build a structured block list for the frontend ─────────────────────────
    blocks = []
    for i, vote in enumerate(votes):
        detail = details[i] if i < len(details) else {'valid': False}
        # Votes after a break in the chain are also considered invalid —
        # even if their own hash is internally consistent, their chain
        # linkage is untrusted.
        is_verified = detail.get('valid', False) and (broken_at == -1 or i < broken_at or chain_result['valid'])
        block = {
            'index': i + 1,                               # 1-based block number for display
            'vote_id': f'VOTE-{str(i + 1).zfill(3)}',   # e.g. VOTE-001, VOTE-002
            'timestamp': vote['timestamp'].isoformat(),
            'current_hash': vote.get('current_hash', ''),
            'previous_hash': vote.get('previous_hash', 'GENESIS'),
            'verified': is_verified,
            'hash_valid': detail.get('hash_valid', False),   # True if the hash recomputes correctly
            'chain_valid': detail.get('chain_valid', False), # True if previous_hash link is correct
        }
        blocks.append(block)

    # ── Compute summary counts ─────────────────────────────────────────────────
    verified_count = sum(1 for b in blocks if b['verified'])
    tampered_count = len(blocks) - verified_count

    # ── Apply optional status filter ───────────────────────────────────────────
    # The admin UI can request only tampered blocks to quickly identify issues.
    # Apply status filter
    if status_filter == 'verified':
        blocks = [b for b in blocks if b['verified']]
    elif status_filter == 'tampered':
        blocks = [b for b in blocks if not b['verified']]

    return jsonify({
        'blocks': blocks,
        'verified_count': verified_count,
        'tampered_count': tampered_count,
        'chain_valid': chain_result['valid'],
        'total': len(votes),
        'election_id': election_id,
        'last_verified': datetime.datetime.utcnow().isoformat()
    })


# ============================================================================
# Admin User Management Endpoints
# ============================================================================

# ── GET /admin/users ──────────────────────────────────────────────────────────
@app.route('/admin/users', methods=['GET'])
@require_role('admin')
def list_users():
    """
    List all users with their roles.
    Requires 'admin' role.
    """
    # ── Fetch all user documents, excluding the MongoDB _id ────────────────────
    # We explicitly request only the safe-to-expose fields.
    # password_hash is fetched temporarily so we can convert it to a boolean.
    users = list(users_collection.find(
        {},
        {'_id': 0, 'student_id': 1, 'role': 1, 'created_at': 1, 'password_hash': 1, 'email': 1}
    ))

    # ── Normalise legacy user documents ───────────────────────────────────────
    # Add default role for legacy users
    for user in users:
        if 'role' not in user:
            user['role'] = 'student'  # legacy docs may not have a role field
        if 'created_at' in user:
            user['created_at'] = user['created_at'].isoformat()  # convert datetime to string
        # Replace the raw password_hash with a simple boolean — we never send
        # password hashes to the frontend, even to admins.
        user['has_password'] = bool(user.pop('password_hash', None))

    return jsonify({
        'users': users,
        'total': len(users)
    })


# ── PUT /admin/users/<student_id>/role ────────────────────────────────────────
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

    # ── Validate the requested role ───────────────────────────────────────────
    if not new_role or new_role not in VALID_ROLES:
        return jsonify({
            'error': 'Invalid role',
            'valid_roles': VALID_ROLES
        }), 400

    # ── Ensure the target user exists ─────────────────────────────────────────
    # Check user exists
    user = users_collection.find_one({'student_id': student_id})
    if not user:
        return jsonify({'error': 'User not found'}), 404

    # ── Prevent an admin from accidentally locking themselves out ─────────────
    # If the logged-in admin tries to demote their own account, we block it.
    # Another admin would be needed to fix it, so we save admins from themselves.
    # Prevent admin from demoting themselves (safety)
    current_user = get_current_user()
    if current_user['student_id'] == student_id and new_role != 'admin':
        return jsonify({'error': 'Cannot demote yourself'}), 400

    # ── Update the role in MongoDB ─────────────────────────────────────────────
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


# ── POST /admin/users ─────────────────────────────────────────────────────────
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
    role = data.get('role', 'student')  # default to student if not specified

    if not student_id:
        return jsonify({'error': 'Student ID is required'}), 400

    if role not in VALID_ROLES:
        return jsonify({
            'error': 'Invalid role',
            'valid_roles': VALID_ROLES
        }), 400

    # ── Prevent duplicate accounts ────────────────────────────────────────────
    # Check if user already exists
    if users_collection.find_one({'student_id': student_id}):
        return jsonify({'error': 'User already exists'}), 409

    # ── Create a minimal user document with no password ────────────────────────
    # Admin-created accounts have no password_hash — the user must complete
    # registration via /auth/register to set their own password.
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


# ── GET /auth/me ──────────────────────────────────────────────────────────────
@app.route('/auth/me', methods=['GET'])
@require_auth  # requires a valid JWT but any role is fine
def get_current_user_info():
    """
    Get current authenticated user's information.
    """
    user = get_current_user()
    # ── Collect WebAuthn credential metadata ───────────────────────────────────
    # We return a summary of each registered passkey (e.g. "Touch ID on MacBook")
    # so the user can see and manage their biometric login options.
    webauthn_creds = user.get('webauthn_credentials', [])
    return jsonify({
        'student_id': user['student_id'],
        'role': user.get('role', 'student'),
        'email': user.get('email'),
        'has_password': bool(user.get('password_hash')),   # True if they've set a password
        'created_at': user.get('created_at').isoformat() if user.get('created_at') else None,
        'has_webauthn': len(webauthn_creds) > 0,           # True if any passkeys registered
        'credential_count': len(webauthn_creds),
        'webauthn_credentials': [
            {
                'credential_id': c.get('credential_id'),
                'friendly_name': c.get('friendly_name', 'Passkey'),
                'created_at': c.get('created_at'),
                'device_type': c.get('device_type', 'single_device'),  # e.g. multi_device (synced)
            }
            for c in webauthn_creds
        ],
    })


# ── POST /auth/change-password ────────────────────────────────────────────────
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

    # ── Validate the new password meets the complexity requirements ────────────
    # Validate new password strength
    is_valid, errors = validate_password_strength(new_password)
    if not is_valid:
        return jsonify({
            'error': 'New password does not meet requirements',
            'details': errors,
            'requirements': get_password_requirements()
        }), 400

    user = get_current_user()

    # ── Require the current password before allowing a change ─────────────────
    # This prevents a session-hijacker from locking out the real user by changing
    # the password — they'd need to know the existing password too.
    # If user has a password, verify current password
    if user.get('password_hash'):
        if not current_password:
            return jsonify({'error': 'Current password is required'}), 400

        if not verify_password(current_password, user['password_hash']):
            return jsonify({'error': 'Current password is incorrect'}), 401

    # ── Hash and persist the new password ─────────────────────────────────────
    # Hash and store new password
    new_hash = hash_password(new_password)
    users_collection.update_one(
        {'student_id': user['student_id']},
        {'$set': {'password_hash': new_hash}}
    )

    return jsonify({'message': 'Password changed successfully'})


# ── POST /auth/set-password ───────────────────────────────────────────────────
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

    # ── Refuse if the user already has a password ─────────────────────────────
    # This endpoint is specifically for the migration path: legacy users who
    # logged in without a password and now want to set one.  If they already
    # have one they must use /auth/change-password (which verifies the old one).
    # Only allow if user doesn't have a password yet
    if user.get('password_hash'):
        return jsonify({
            'error': 'Password already set. Use /auth/change-password instead.'
        }), 400

    # ── Validate password strength ────────────────────────────────────────────
    # Validate password strength
    is_valid, errors = validate_password_strength(password)
    if not is_valid:
        return jsonify({
            'error': 'Password does not meet requirements',
            'details': errors,
            'requirements': get_password_requirements()
        }), 400

    # ── Hash and store the new password ───────────────────────────────────────
    # Hash and store password
    password_hash = hash_password(password)
    users_collection.update_one(
        {'student_id': user['student_id']},
        {'$set': {'password_hash': password_hash}}
    )

    return jsonify({'message': 'Password set successfully'})


# ── GET /auth/password-requirements ──────────────────────────────────────────
@app.route('/auth/password-requirements', methods=['GET'])
def password_requirements():
    """
    Get password requirements for client-side validation.
    No authentication required.
    """
    # Public endpoint so the registration/change-password forms can show
    # the rules to the user before they even try to submit.
    return jsonify(get_password_requirements())


# ── Development server entry point ────────────────────────────────────────────
# This block only runs when executing `python app.py` directly.
# In production the gunicorn WSGI server in the Dockerfile is used instead,
# which is multi-process, production-hardened, and does NOT use Flask's dev server.
if __name__ == '__main__':
    app.run(debug=True, port=5001)
