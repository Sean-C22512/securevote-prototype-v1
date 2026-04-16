"""
SecureVote WebAuthn Routes
==========================
WebAuthn (passkey/biometric) authentication endpoints.

Endpoints:
- POST /auth/webauthn/register/begin    Begin passkey registration (requires JWT)
- POST /auth/webauthn/register/complete Complete passkey registration (requires JWT)
- POST /auth/webauthn/login/begin       Begin passkey authentication (public)
- POST /auth/webauthn/login/complete    Complete passkey authentication (public)

Signature verification:
During the signature verification step, the browser's authenticator (e.g., TouchID or FaceID)
uses its private key — stored in the device's Secure Enclave and never transmitted — to produce
an ECDSA (P-256) digital signature over the concatenation of the SHA-256 hash of clientDataJSON
and the raw authenticatorData bytes, which together encode the origin, the server's challenge,
and a replay-attack counter. The backend then calls verify_authentication_response() from
py-webauthn, which decodes the stored COSE-formatted public key and checks that the signature
is mathematically valid; because only the device holding the corresponding private key can produce
a valid signature, this step cryptographically proves the user's physical presence and identity.
Finally, the backend compares the response's sign_count against the last persisted value —
if the counter has not incremented, the server detects a cloned or replayed credential and
rejects the request, providing protection against credential copying attacks.
"""

# ── Standard library imports ───────────────────────────────────────────────────
# os:       read environment variables (RP_ID, RP_NAME, ORIGIN) set at deploy time.
# base64:   encode/decode raw credential bytes to/from base64 for MongoDB storage.
# datetime: used to set a 5-minute TTL on the WebAuthn challenge.
# json:     convert webauthn options objects to JSON for the HTTP response.
# logging:  record failed verification attempts without crashing the request.
import os
import base64
import datetime
import json
import logging

# ── Flask imports ──────────────────────────────────────────────────────────────
# Blueprint: groups these endpoints separately from app.py.
# request:   incoming HTTP request body.
# jsonify:   builds JSON responses.
from flask import Blueprint, request, jsonify

# jwt (PyJWT): used to issue a standard JWT after a successful biometric login —
# exactly the same token format as password login so RBAC is unchanged.
import jwt

# ── py-webauthn library ────────────────────────────────────────────────────────
# generate_registration_options:    builds the challenge + RP metadata the browser
#                                   needs to start the credential creation ceremony.
# verify_registration_response:     validates the signed attestation object the
#                                   browser returns after the user authenticates.
# generate_authentication_options:  builds the challenge + credential hints for login.
# verify_authentication_response:   validates the assertion signature for login.
# options_to_json:                  serialises the options struct to a JSON string.
from webauthn import (
    generate_registration_options,
    verify_registration_response,
    generate_authentication_options,
    verify_authentication_response,
    options_to_json,
)

# ── WebAuthn helper structs ────────────────────────────────────────────────────
# UserVerificationRequirement.REQUIRED: forces the authenticator to verify the
#                                        user (biometric or PIN) — not just presence.
# PublicKeyCredentialDescriptor:  used to tell the browser which existing
#                                 credentials it already knows about (for login).
# RegistrationCredential /
# AuthenticationCredential:       typed containers for the browser's response.
# AuthenticatorAttestationResponse: the blob returned after registration.
# AuthenticatorAssertionResponse:   the blob returned after login assertion.
from webauthn.helpers.structs import (
    UserVerificationRequirement,
    PublicKeyCredentialDescriptor,
    RegistrationCredential,
    AuthenticationCredential,
    AuthenticatorAttestationResponse,
    AuthenticatorAssertionResponse,
)

# ── AuthenticatorTransport — optional, version-dependent ─────────────────────
# Some older versions of py-webauthn don't export this struct.
# We guard the import and set a flag so the builder function can skip it safely.
try:
    from webauthn.helpers.structs import AuthenticatorTransport
    _TRANSPORT_AVAILABLE = True
except ImportError:
    _TRANSPORT_AVAILABLE = False

# ── Custom exception classes — version-dependent ───────────────────────────────
# py-webauthn changed which exceptions it exposes between versions.
# We try to import the specific ones so we can give a cleaner error message;
# if the import fails we fall back to empty stubs that will never match but
# let the generic Exception handler deal with verification failures instead.
try:
    from webauthn.helpers.exceptions import (
        InvalidCBORData,
        InvalidAuthenticatorDataStructure,
    )
except ImportError:
    # Fallback: these won't match anything but the generic handler will still catch
    class InvalidCBORData(Exception): pass
    class InvalidAuthenticatorDataStructure(Exception): pass

# ── Internal auth utilities ────────────────────────────────────────────────────
# require_auth: decorator that validates the JWT in the Authorization header.
# get_current_user: returns the MongoDB user document for the logged-in caller.
from utils.auth import require_auth, get_current_user

log = logging.getLogger(__name__)

# ── Blueprint definition ───────────────────────────────────────────────────────
# All routes here are prefixed with /auth/webauthn.
# e.g. /register/begin becomes POST /auth/webauthn/register/begin.
webauthn_bp = Blueprint('webauthn', __name__, url_prefix='/auth/webauthn')

# ── Module-level dependencies (injected by app.py at startup) ─────────────────
# Injected by init_webauthn_routes
users_collection = None  # MongoDB users collection
_secret_key = None        # JWT signing secret — same key used in app.py


def init_webauthn_routes(users_col, secret_key):
    """Initialize route dependencies (called from app.py)."""
    # ── Receive the DB handle and secret from app.py ───────────────────────────
    # Using injection instead of importing directly avoids circular imports.
    global users_collection, _secret_key
    users_collection = users_col
    _secret_key = secret_key


# ---------------------------------------------------------------------------
# base64url helpers (not always exported from webauthn top-level in all versions)
# ---------------------------------------------------------------------------

def base64url_to_bytes(value: str) -> bytes:
    """Decode a base64url string (with or without padding) to bytes."""
    # ── base64url vs standard base64 ──────────────────────────────────────────
    # WebAuthn uses the URL-safe variant of base64 (no +/= characters).
    # Python's base64.urlsafe_b64decode requires the string to be padded to a
    # multiple of 4 characters with '=', so we add padding if it's missing.
    if not value:
        return b''
    padding = 4 - len(value) % 4
    if padding != 4:
        value += '=' * padding
    return base64.urlsafe_b64decode(value)


def bytes_to_base64url(value: bytes) -> str:
    """Encode bytes to an unpadded base64url string."""
    # ── Strip padding for a clean URL-safe string ──────────────────────────────
    # We strip the trailing '=' characters because WebAuthn clients (and our DB)
    # expect unpadded base64url.
    return base64.urlsafe_b64encode(value).rstrip(b'=').decode('ascii')


# ---------------------------------------------------------------------------
# Credential builders — construct structs from the JSON dict that
# SimpleWebAuthn returns, avoiding pydantic v1/v2 parse_raw differences.
# ---------------------------------------------------------------------------

def _build_registration_credential(data):
    """Build RegistrationCredential from a SimpleWebAuthn JSON response dict."""
    # ── Extract the raw fields from the browser's JSON response ───────────────
    # The browser (via @simplewebauthn/browser) sends rawId and response fields.
    resp = data.get('response', {})
    raw_id = base64url_to_bytes(data.get('rawId') or data.get('id', ''))
    client_data_json = base64url_to_bytes(resp.get('clientDataJSON', ''))
    attestation_object = base64url_to_bytes(resp.get('attestationObject', ''))

    # ── Build the attestation response object ─────────────────────────────────
    # We try to include the 'transports' field (e.g. ['internal'] for Touch ID,
    # ['usb'] for a hardware key) because some versions of py-webauthn use it
    # to select the right verification path.  If the version doesn't support it,
    # we fall back gracefully by removing it from the kwargs.
    # Build response object — try with transports first, fall back without
    attestation_kwargs = dict(
        client_data_json=client_data_json,
        attestation_object=attestation_object,
    )
    if _TRANSPORT_AVAILABLE and resp.get('transports'):
        transports = []
        for t in resp['transports']:
            try:
                transports.append(AuthenticatorTransport(t))  # e.g. AuthenticatorTransport.INTERNAL
            except Exception:
                pass  # skip any unrecognised transport string
        if transports:
            attestation_kwargs['transports'] = transports

    try:
        attestation_response = AuthenticatorAttestationResponse(**attestation_kwargs)
    except TypeError:
        # Some versions don't accept 'transports' kwarg
        attestation_kwargs.pop('transports', None)
        attestation_response = AuthenticatorAttestationResponse(**attestation_kwargs)

    # ── Wrap everything in the top-level RegistrationCredential struct ─────────
    return RegistrationCredential(
        id=data.get('id', ''),
        raw_id=raw_id,
        response=attestation_response,
        type=data.get('type', 'public-key'),
    )


def _build_authentication_credential(data):
    """Build AuthenticationCredential from a SimpleWebAuthn JSON assertion dict."""
    # ── Extract assertion fields from the browser response ────────────────────
    # An assertion (login) response includes: clientDataJSON, authenticatorData,
    # signature, and optionally userHandle (the stored user identifier).
    resp = data.get('response', {})
    raw_id = base64url_to_bytes(data.get('rawId') or data.get('id', ''))
    client_data_json = base64url_to_bytes(resp.get('clientDataJSON', ''))
    authenticator_data = base64url_to_bytes(resp.get('authenticatorData', ''))
    signature = base64url_to_bytes(resp.get('signature', ''))
    user_handle_str = resp.get('userHandle')
    user_handle = base64url_to_bytes(user_handle_str) if user_handle_str else None  # optional

    # ── Build the assertion response struct ───────────────────────────────────
    assertion_response = AuthenticatorAssertionResponse(
        client_data_json=client_data_json,
        authenticator_data=authenticator_data,
        signature=signature,        # ECDSA P-256 signature produced by the Secure Enclave
        user_handle=user_handle,
    )

    # ── Wrap in the AuthenticationCredential top-level struct ─────────────────
    return AuthenticationCredential(
        id=data.get('id', ''),
        raw_id=raw_id,
        response=assertion_response,
        type=data.get('type', 'public-key'),
    )


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _rp():
    """Read Relying Party configuration from environment variables.

    The Relying Party (RP) identifies this server to the browser and the
    authenticator.  The RP ID is typically just the domain name (e.g.
    'securevote.ie') and must match what the browser sees in its address bar —
    mismatches cause verification to fail.
    """
    # ── Read and split the origin(s) — may be a comma-separated list ──────────
    # In production we allow both the bare domain and www subdomain.
    origin_env = os.getenv('WEBAUTHN_ORIGIN', 'http://localhost:3000')
    origins = [o.strip() for o in origin_env.split(',') if o.strip()]
    return {
        'rp_id':   os.getenv('WEBAUTHN_RP_ID',   'localhost'),   # e.g. 'securevote.ie'
        'rp_name': os.getenv('WEBAUTHN_RP_NAME',  'SecureVote'), # displayed by the OS biometric prompt
        # If there's only one origin pass it as a string; otherwise pass the list.
        'origin':  origins if len(origins) > 1 else origins[0],
    }


def _decode_challenge(user):
    """Retrieve and decode the stored challenge bytes from the user document."""
    stored = user.get('pending_webauthn_challenge')
    if not stored:
        return None
    # The challenge was stored as a standard base64 string — decode it back to bytes.
    return base64.b64decode(stored)


def _challenge_valid(user):
    """Return True if the stored challenge has not yet expired (5-minute TTL)."""
    expiry = user.get('challenge_expiry')
    if not expiry:
        return False
    now = datetime.datetime.now(datetime.timezone.utc)
    # Handle legacy challenge documents that might be stored without timezone info.
    if expiry.tzinfo is None:
        expiry = expiry.replace(tzinfo=datetime.timezone.utc)
    return now < expiry  # True = still valid; False = expired


def _store_challenge(student_id, challenge_bytes):
    """Persist a new WebAuthn challenge on the user document with a 5-minute expiry.

    We store the challenge server-side (rather than in a cookie or session) because
    the application is stateless — this avoids needing sticky sessions or a Redis store.
    """
    # Encode bytes to base64 so they can be stored as a plain MongoDB string.
    challenge_b64 = base64.b64encode(challenge_bytes).decode()
    expiry = datetime.datetime.now(datetime.timezone.utc) + datetime.timedelta(minutes=5)
    # Write directly to the user's document in MongoDB.
    users_collection.update_one(
        {'student_id': student_id},
        {'$set': {'pending_webauthn_challenge': challenge_b64, 'challenge_expiry': expiry}}
    )


def _normalize_b64url(s):
    """Strip trailing '=' padding for consistent credential ID comparison."""
    # Different libraries may or may not include padding characters.
    # Stripping them from both sides before comparing avoids false mismatches.
    return s.rstrip('=') if s else ''


def _issue_jwt(student_id, role):
    """Issue a signed HS256 JWT for the given user — identical to password login."""
    # ── Build the token payload ───────────────────────────────────────────────
    # student_id: who the token belongs to.
    # role:       used by require_role() for RBAC on every API call.
    # exp:        token expires in 1 hour — the frontend must re-authenticate after that.
    return jwt.encode(
        {
            'student_id': student_id,
            'role': role,
            'exp': datetime.datetime.now(datetime.timezone.utc) + datetime.timedelta(hours=1),
        },
        _secret_key,
        algorithm='HS256',
    )


# ---------------------------------------------------------------------------
# Endpoint 1 — Register: Begin
# ---------------------------------------------------------------------------

@webauthn_bp.route('/register/begin', methods=['POST'])
@require_auth  # the user must be already logged in (via password) to add a biometric
def register_begin():
    """Generate WebAuthn registration options. Requires JWT."""
    user = get_current_user()
    student_id = user['student_id']
    rp = _rp()

    # ── Collect IDs of already-registered credentials ─────────────────────────
    # exclude_credentials tells the browser not to create a second credential on
    # a device that already has one registered for this account.  This prevents
    # duplicate passkeys from accumulating on the same device.
    existing = user.get('webauthn_credentials', [])
    exclude_credentials = [
        PublicKeyCredentialDescriptor(id=base64url_to_bytes(cred['credential_id']))
        for cred in existing
    ]

    # ── Ask py-webauthn to generate the registration challenge ────────────────
    # This produces a random 32-byte nonce (challenge) that the browser and
    # authenticator will sign.  The browser also receives RP metadata so the
    # OS biometric prompt can display "SecureVote is requesting Touch ID".
    options = generate_registration_options(
        rp_id=rp['rp_id'],
        rp_name=rp['rp_name'],
        user_id=student_id.encode(),  # WebAuthn user handle — must be bytes
        user_name=student_id,         # displayed in the OS passkey manager
        exclude_credentials=exclude_credentials,
    )

    # ── Save the challenge in MongoDB so we can verify it in /register/complete ─
    _store_challenge(student_id, options.challenge)

    # ── Serialise the options to JSON and return to the browser ───────────────
    # options_to_json() handles CBOR/bytes → JSON conversion internally.
    return jsonify(json.loads(options_to_json(options)))


# ---------------------------------------------------------------------------
# Endpoint 2 — Register: Complete
# ---------------------------------------------------------------------------

@webauthn_bp.route('/register/complete', methods=['POST'])
@require_auth  # still requires JWT — we're adding a credential to an existing account
def register_complete():
    """Verify WebAuthn registration response. Requires JWT."""
    user = get_current_user()
    student_id = user['student_id']

    # ── Re-fetch the user document to get the challenge written by /begin ──────
    # get_current_user() uses a cached copy attached to the Flask request context;
    # the challenge was written by a separate request so we need a fresh read.
    # Re-fetch to get the challenge written by register_begin
    user = users_collection.find_one({'student_id': student_id})

    # ── Validate the challenge is still within its 5-minute window ─────────────
    if not _challenge_valid(user):
        return jsonify({'error': 'Session expired. Please try again.'}), 400

    challenge_bytes = _decode_challenge(user)
    if not challenge_bytes:
        return jsonify({'error': 'Session expired. Please try again.'}), 400

    rp = _rp()
    body = request.get_json()  # the attestation object from the browser

    try:
        # ── Parse the browser's attestation response into a typed struct ───────
        credential = _build_registration_credential(body)

        # ── Verify the attestation with py-webauthn ────────────────────────────
        # This checks: the challenge matches, the origin matches our RP, the
        # attestation signature is valid, and the public key is well-formed.
        verification = verify_registration_response(
            credential=credential,
            expected_challenge=challenge_bytes,    # must match what we sent in /begin
            expected_origin=rp['origin'],          # must match the browser's origin
            expected_rp_id=rp['rp_id'],            # must match our server's domain
        )
    except (InvalidCBORData, InvalidAuthenticatorDataStructure) as exc:
        # ── Malformed response from the authenticator ──────────────────────────
        log.warning("WebAuthn registration: invalid CBOR/authenticator data: %s", exc)
        return jsonify({'error': 'Invalid authenticator response.'}), 400
    except Exception as exc:
        # ── Any other verification failure (wrong challenge, wrong origin, etc.) ─
        log.exception("WebAuthn registration verification failed")
        return jsonify({'error': f'Biometric verification failed: {exc}'}), 400

    # ── Extract the verified credential data ───────────────────────────────────
    credential_id_b64url = bytes_to_base64url(verification.credential_id)
    # The public key is in COSE format (a compact binary encoding) — we base64-
    # encode it for storage so it's a plain string in MongoDB.
    pub_key_b64 = base64.b64encode(verification.credential_public_key).decode()

    # ── Build the credential document to store on the user ────────────────────
    new_cred = {
        'credential_id':         credential_id_b64url,
        'credential_public_key': pub_key_b64,
        'sign_count':            verification.sign_count,  # replay-attack counter
        # device_type distinguishes between platform (Touch ID) and cross-platform (YubiKey).
        'device_type':           getattr(verification, 'credential_device_type', 'single_device'),
        'is_backed_up':          getattr(verification, 'credential_backed_up', False),
        'transports':            ['internal'],  # always 'internal' for platform authenticators
        'created_at':            datetime.datetime.now(datetime.timezone.utc).isoformat(),
    }

    # ── Persist the new credential and clear the one-time challenge ────────────
    # $push appends to the webauthn_credentials array; $unset removes the challenge
    # fields so they can't be replayed by an attacker who intercepted them.
    users_collection.update_one(
        {'student_id': student_id},
        {
            '$push':  {'webauthn_credentials': new_cred},
            '$unset': {'pending_webauthn_challenge': '', 'challenge_expiry': ''},
        }
    )

    return jsonify({'message': 'Biometric registered', 'credential_id': credential_id_b64url}), 201


# ---------------------------------------------------------------------------
# Endpoint 3 — Login: Begin
# ---------------------------------------------------------------------------

@webauthn_bp.route('/login/begin', methods=['POST'])
def login_begin():
    """Generate WebAuthn authentication options. Public endpoint."""
    # ── This endpoint is public — no JWT required ──────────────────────────────
    # The user is trying to log IN, so they don't have a token yet.
    data = request.get_json()
    student_id = (data or {}).get('student_id')

    if not student_id:
        return jsonify({'error': 'Student ID is required.'}), 400

    # ── Look up the user to get their registered credentials ──────────────────
    user = users_collection.find_one({'student_id': student_id})
    if not user:
        return jsonify({'error': 'User not found.'}), 404

    credentials = user.get('webauthn_credentials', [])
    if not credentials:
        return jsonify({'error': 'No biometrics registered for this account.'}), 400

    rp = _rp()

    # ── Build the allowed credential list for the browser ─────────────────────
    # allow_credentials tells the browser's credential manager which passkeys are
    # acceptable for this user — it will only try passkeys it recognises.
    allow_credentials = [
        PublicKeyCredentialDescriptor(id=base64url_to_bytes(cred['credential_id']))
        for cred in credentials
    ]

    # ── Generate the authentication challenge ─────────────────────────────────
    # user_verification=REQUIRED means the OS must verify the user biometrically
    # (Touch ID, Face ID, Windows Hello) rather than just detecting presence.
    options = generate_authentication_options(
        rp_id=rp['rp_id'],
        allow_credentials=allow_credentials,
        user_verification=UserVerificationRequirement.REQUIRED,
    )

    # ── Store the challenge server-side for verification in /login/complete ────
    _store_challenge(student_id, options.challenge)
    return jsonify(json.loads(options_to_json(options)))


# ---------------------------------------------------------------------------
# Endpoint 4 — Login: Complete
# ---------------------------------------------------------------------------

@webauthn_bp.route('/login/complete', methods=['POST'])
def login_complete():
    """Verify WebAuthn authentication response and issue JWT. Public endpoint."""
    data = request.get_json()
    student_id = (data or {}).get('student_id')
    assertion  = (data or {}).get('assertion')  # the signed assertion from the browser

    if not student_id or not assertion:
        return jsonify({'error': 'Student ID and assertion are required.'}), 400

    # ── Look up the user ──────────────────────────────────────────────────────
    user = users_collection.find_one({'student_id': student_id})
    if not user:
        return jsonify({'error': 'User not found.'}), 404

    # ── Check the challenge hasn't expired ────────────────────────────────────
    if not _challenge_valid(user):
        return jsonify({'error': 'Session expired. Please try again.'}), 400

    challenge_bytes = _decode_challenge(user)
    if not challenge_bytes:
        return jsonify({'error': 'Session expired. Please try again.'}), 400

    credentials = user.get('webauthn_credentials', [])
    if not credentials:
        return jsonify({'error': 'No biometrics registered for this account.'}), 400

    rp = _rp()

    # ── Match the assertion's credential ID to a stored credential ─────────────
    # The browser sends back the ID of the credential it used (the private key
    # lives in the Secure Enclave and never leaves the device).  We find the
    # corresponding stored public key so we can verify the signature.
    assertion_id = assertion.get('id') or assertion.get('rawId', '')
    matching_cred = next(
        (c for c in credentials
         if _normalize_b64url(c['credential_id']) == _normalize_b64url(assertion_id)),
        None
    )

    if not matching_cred:
        return jsonify({'error': 'Biometric verification failed.'}), 400

    # ── Retrieve the stored public key and sign count ─────────────────────────
    stored_pub_key_bytes = base64.b64decode(matching_cred['credential_public_key'])
    stored_sign_count    = matching_cred.get('sign_count', 0)

    try:
        # ── Parse the browser's assertion response into a typed struct ─────────
        auth_credential = _build_authentication_credential(assertion)

        # ── Verify the assertion with py-webauthn ─────────────────────────────
        # This performs several checks simultaneously:
        #  1. The challenge in clientDataJSON matches what we stored.
        #  2. The origin in clientDataJSON matches our RP origin.
        #  3. The RP ID hash in authenticatorData matches our rp_id.
        #  4. The ECDSA P-256 signature is mathematically valid against the stored
        #     public key — this cryptographically proves the Secure Enclave signed it.
        #  5. The sign_count has advanced — detects cloned credentials.
        verification = verify_authentication_response(
            credential=auth_credential,
            expected_challenge=challenge_bytes,
            expected_origin=rp['origin'],
            expected_rp_id=rp['rp_id'],
            credential_public_key=stored_pub_key_bytes,
            credential_current_sign_count=stored_sign_count,
        )
    except (InvalidCBORData, InvalidAuthenticatorDataStructure) as exc:
        log.warning("WebAuthn login: invalid CBOR/authenticator data: %s", exc)
        return jsonify({'error': 'Invalid authenticator response.'}), 400
    except Exception as exc:
        log.exception("WebAuthn login verification failed")
        return jsonify({'error': f'Biometric verification failed: {exc}'}), 400

    # ── Update sign_count and clear the used challenge ────────────────────────
    # Persisting the new sign_count is critical for replay protection:
    # if the count doesn't increment on the next login, we know something is wrong.
    # We use MongoDB's positional operator ($) to update only the matching credential
    # within the webauthn_credentials array without rewriting the entire array.
    # Update sign_count and clear challenge
    users_collection.update_one(
        {
            'student_id': student_id,
            'webauthn_credentials.credential_id': matching_cred['credential_id'],
        },
        {
            '$set':  {'webauthn_credentials.$.sign_count': verification.new_sign_count},
            '$unset': {'pending_webauthn_challenge': '', 'challenge_expiry': ''},
        }
    )

    # ── Issue the same JWT as password login ──────────────────────────────────
    # From this point on the frontend has a normal JWT; it doesn't matter how
    # the user authenticated — all subsequent API calls go through require_auth
    # and require_role exactly as they would for a password-authenticated user.
    role = user.get('role', 'student')
    token = _issue_jwt(student_id, role)

    return jsonify({'token': token, 'role': role, 'student_id': student_id})
