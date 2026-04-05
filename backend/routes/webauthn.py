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

import os
import base64
import datetime
import json
import logging

from flask import Blueprint, request, jsonify
import jwt

from webauthn import (
    generate_registration_options,
    verify_registration_response,
    generate_authentication_options,
    verify_authentication_response,
    options_to_json,
)
from webauthn.helpers.structs import (
    UserVerificationRequirement,
    PublicKeyCredentialDescriptor,
    RegistrationCredential,
    AuthenticationCredential,
    AuthenticatorAttestationResponse,
    AuthenticatorAssertionResponse,
)

try:
    from webauthn.helpers.structs import AuthenticatorTransport
    _TRANSPORT_AVAILABLE = True
except ImportError:
    _TRANSPORT_AVAILABLE = False

try:
    from webauthn.helpers.exceptions import (
        InvalidCBORData,
        InvalidAuthenticatorDataStructure,
    )
except ImportError:
    # Fallback: these won't match anything but the generic handler will still catch
    class InvalidCBORData(Exception): pass
    class InvalidAuthenticatorDataStructure(Exception): pass

from utils.auth import require_auth, get_current_user

log = logging.getLogger(__name__)

webauthn_bp = Blueprint('webauthn', __name__, url_prefix='/auth/webauthn')

# Injected by init_webauthn_routes
users_collection = None
_secret_key = None


def init_webauthn_routes(users_col, secret_key):
    """Initialize route dependencies (called from app.py)."""
    global users_collection, _secret_key
    users_collection = users_col
    _secret_key = secret_key


# ---------------------------------------------------------------------------
# base64url helpers (not always exported from webauthn top-level in all versions)
# ---------------------------------------------------------------------------

def base64url_to_bytes(value: str) -> bytes:
    """Decode a base64url string (with or without padding) to bytes."""
    if not value:
        return b''
    padding = 4 - len(value) % 4
    if padding != 4:
        value += '=' * padding
    return base64.urlsafe_b64decode(value)


def bytes_to_base64url(value: bytes) -> str:
    """Encode bytes to an unpadded base64url string."""
    return base64.urlsafe_b64encode(value).rstrip(b'=').decode('ascii')


# ---------------------------------------------------------------------------
# Credential builders — construct structs from the JSON dict that
# SimpleWebAuthn returns, avoiding pydantic v1/v2 parse_raw differences.
# ---------------------------------------------------------------------------

def _build_registration_credential(data):
    """Build RegistrationCredential from a SimpleWebAuthn JSON response dict."""
    resp = data.get('response', {})
    raw_id = base64url_to_bytes(data.get('rawId') or data.get('id', ''))
    client_data_json = base64url_to_bytes(resp.get('clientDataJSON', ''))
    attestation_object = base64url_to_bytes(resp.get('attestationObject', ''))

    # Build response object — try with transports first, fall back without
    attestation_kwargs = dict(
        client_data_json=client_data_json,
        attestation_object=attestation_object,
    )
    if _TRANSPORT_AVAILABLE and resp.get('transports'):
        transports = []
        for t in resp['transports']:
            try:
                transports.append(AuthenticatorTransport(t))
            except Exception:
                pass
        if transports:
            attestation_kwargs['transports'] = transports

    try:
        attestation_response = AuthenticatorAttestationResponse(**attestation_kwargs)
    except TypeError:
        # Some versions don't accept 'transports' kwarg
        attestation_kwargs.pop('transports', None)
        attestation_response = AuthenticatorAttestationResponse(**attestation_kwargs)

    return RegistrationCredential(
        id=data.get('id', ''),
        raw_id=raw_id,
        response=attestation_response,
        type=data.get('type', 'public-key'),
    )


def _build_authentication_credential(data):
    """Build AuthenticationCredential from a SimpleWebAuthn JSON assertion dict."""
    resp = data.get('response', {})
    raw_id = base64url_to_bytes(data.get('rawId') or data.get('id', ''))
    client_data_json = base64url_to_bytes(resp.get('clientDataJSON', ''))
    authenticator_data = base64url_to_bytes(resp.get('authenticatorData', ''))
    signature = base64url_to_bytes(resp.get('signature', ''))
    user_handle_str = resp.get('userHandle')
    user_handle = base64url_to_bytes(user_handle_str) if user_handle_str else None

    assertion_response = AuthenticatorAssertionResponse(
        client_data_json=client_data_json,
        authenticator_data=authenticator_data,
        signature=signature,
        user_handle=user_handle,
    )

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
    origin_env = os.getenv('WEBAUTHN_ORIGIN', 'http://localhost:3000')
    origins = [o.strip() for o in origin_env.split(',') if o.strip()]
    return {
        'rp_id':   os.getenv('WEBAUTHN_RP_ID',   'localhost'),
        'rp_name': os.getenv('WEBAUTHN_RP_NAME',  'SecureVote'),
        'origin':  origins if len(origins) > 1 else origins[0],
    }


def _decode_challenge(user):
    stored = user.get('pending_webauthn_challenge')
    if not stored:
        return None
    return base64.b64decode(stored)


def _challenge_valid(user):
    expiry = user.get('challenge_expiry')
    if not expiry:
        return False
    now = datetime.datetime.now(datetime.timezone.utc)
    if expiry.tzinfo is None:
        expiry = expiry.replace(tzinfo=datetime.timezone.utc)
    return now < expiry


def _store_challenge(student_id, challenge_bytes):
    challenge_b64 = base64.b64encode(challenge_bytes).decode()
    expiry = datetime.datetime.now(datetime.timezone.utc) + datetime.timedelta(minutes=5)
    users_collection.update_one(
        {'student_id': student_id},
        {'$set': {'pending_webauthn_challenge': challenge_b64, 'challenge_expiry': expiry}}
    )


def _normalize_b64url(s):
    return s.rstrip('=') if s else ''


def _issue_jwt(student_id, role):
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
@require_auth
def register_begin():
    """Generate WebAuthn registration options. Requires JWT."""
    user = get_current_user()
    student_id = user['student_id']
    rp = _rp()

    existing = user.get('webauthn_credentials', [])
    exclude_credentials = [
        PublicKeyCredentialDescriptor(id=base64url_to_bytes(cred['credential_id']))
        for cred in existing
    ]

    options = generate_registration_options(
        rp_id=rp['rp_id'],
        rp_name=rp['rp_name'],
        user_id=student_id.encode(),
        user_name=student_id,
        exclude_credentials=exclude_credentials,
    )

    _store_challenge(student_id, options.challenge)
    return jsonify(json.loads(options_to_json(options)))


# ---------------------------------------------------------------------------
# Endpoint 2 — Register: Complete
# ---------------------------------------------------------------------------

@webauthn_bp.route('/register/complete', methods=['POST'])
@require_auth
def register_complete():
    """Verify WebAuthn registration response. Requires JWT."""
    user = get_current_user()
    student_id = user['student_id']

    # Re-fetch to get the challenge written by register_begin
    user = users_collection.find_one({'student_id': student_id})

    if not _challenge_valid(user):
        return jsonify({'error': 'Session expired. Please try again.'}), 400

    challenge_bytes = _decode_challenge(user)
    if not challenge_bytes:
        return jsonify({'error': 'Session expired. Please try again.'}), 400

    rp = _rp()
    body = request.get_json()

    try:
        credential = _build_registration_credential(body)
        verification = verify_registration_response(
            credential=credential,
            expected_challenge=challenge_bytes,
            expected_origin=rp['origin'],
            expected_rp_id=rp['rp_id'],
        )
    except (InvalidCBORData, InvalidAuthenticatorDataStructure) as exc:
        log.warning("WebAuthn registration: invalid CBOR/authenticator data: %s", exc)
        return jsonify({'error': 'Invalid authenticator response.'}), 400
    except Exception as exc:
        log.exception("WebAuthn registration verification failed")
        return jsonify({'error': f'Biometric verification failed: {exc}'}), 400

    credential_id_b64url = bytes_to_base64url(verification.credential_id)
    pub_key_b64 = base64.b64encode(verification.credential_public_key).decode()

    new_cred = {
        'credential_id':         credential_id_b64url,
        'credential_public_key': pub_key_b64,
        'sign_count':            verification.sign_count,
        'device_type':           getattr(verification, 'credential_device_type', 'single_device'),
        'is_backed_up':          getattr(verification, 'credential_backed_up', False),
        'transports':            ['internal'],
        'created_at':            datetime.datetime.now(datetime.timezone.utc).isoformat(),
    }

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
    data = request.get_json()
    student_id = (data or {}).get('student_id')

    if not student_id:
        return jsonify({'error': 'Student ID is required.'}), 400

    user = users_collection.find_one({'student_id': student_id})
    if not user:
        return jsonify({'error': 'User not found.'}), 404

    credentials = user.get('webauthn_credentials', [])
    if not credentials:
        return jsonify({'error': 'No biometrics registered for this account.'}), 400

    rp = _rp()

    allow_credentials = [
        PublicKeyCredentialDescriptor(id=base64url_to_bytes(cred['credential_id']))
        for cred in credentials
    ]

    options = generate_authentication_options(
        rp_id=rp['rp_id'],
        allow_credentials=allow_credentials,
        user_verification=UserVerificationRequirement.REQUIRED,
    )

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
    assertion  = (data or {}).get('assertion')

    if not student_id or not assertion:
        return jsonify({'error': 'Student ID and assertion are required.'}), 400

    user = users_collection.find_one({'student_id': student_id})
    if not user:
        return jsonify({'error': 'User not found.'}), 404

    if not _challenge_valid(user):
        return jsonify({'error': 'Session expired. Please try again.'}), 400

    challenge_bytes = _decode_challenge(user)
    if not challenge_bytes:
        return jsonify({'error': 'Session expired. Please try again.'}), 400

    credentials = user.get('webauthn_credentials', [])
    if not credentials:
        return jsonify({'error': 'No biometrics registered for this account.'}), 400

    rp = _rp()

    assertion_id = assertion.get('id') or assertion.get('rawId', '')
    matching_cred = next(
        (c for c in credentials
         if _normalize_b64url(c['credential_id']) == _normalize_b64url(assertion_id)),
        None
    )

    if not matching_cred:
        return jsonify({'error': 'Biometric verification failed.'}), 400

    stored_pub_key_bytes = base64.b64decode(matching_cred['credential_public_key'])
    stored_sign_count    = matching_cred.get('sign_count', 0)

    try:
        auth_credential = _build_authentication_credential(assertion)
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

    role = user.get('role', 'student')
    token = _issue_jwt(student_id, role)

    return jsonify({'token': token, 'role': role, 'student_id': student_id})
