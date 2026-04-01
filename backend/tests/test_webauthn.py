"""
SecureVote WebAuthn Tests
=========================
Tests for the WebAuthn (passkey/biometric) authentication endpoints.

Full registration/authentication ceremonies require a real browser authenticator
and cannot be automated in a unit test environment. These tests cover:
  - Authentication boundaries (missing/invalid JWT)
  - All error paths (missing credentials, unknown user, expired challenge)
  - Options shape returned by begin endpoints
  - Challenge storage and expiry enforcement

Run with: pytest tests/test_webauthn.py -v
"""

import pytest
import json
import os
import base64
import datetime
import tempfile
import shutil

os.environ['FLASK_ENV'] = 'testing'


class TestWebAuthnRegistration:
    """Tests for /auth/webauthn/register/begin and /auth/webauthn/register/complete."""

    @pytest.fixture(autouse=True)
    def setup(self):
        self.temp_keys_dir = tempfile.mkdtemp()

        from app import app, users_collection
        from crypto.key_manager import KeyManager
        from crypto.ballot_crypto import BallotCrypto
        import app as app_module

        km = KeyManager(keys_dir=self.temp_keys_dir)
        app_module.ballot_crypto = BallotCrypto(key_manager=km)
        app_module.limiter.enabled = False

        self.app = app
        self.client = app.test_client()
        self.users_collection = users_collection

        self.users_collection.delete_many({})
        yield
        self.users_collection.delete_many({})
        shutil.rmtree(self.temp_keys_dir)

    def _register_and_login(self, student_id='C99900001', password='TestPass123'):
        """Helper: create a user and return a valid JWT."""
        self.client.post('/auth/register',
            json={'student_id': student_id, 'password': password,
                  'programme': {'code': 'TU652', 'name': 'Computing'}},
            content_type='application/json')
        resp = self.client.post('/auth/login',
            json={'student_id': student_id, 'password': password},
            content_type='application/json')
        return json.loads(resp.data)['token']

    # ------------------------------------------------------------------
    # register/begin
    # ------------------------------------------------------------------

    def test_register_begin_requires_auth(self):
        """register/begin must reject unauthenticated requests."""
        resp = self.client.post('/auth/webauthn/register/begin',
            content_type='application/json')
        assert resp.status_code == 401

    def test_register_begin_requires_valid_token(self):
        """register/begin must reject requests with a bogus token."""
        resp = self.client.post('/auth/webauthn/register/begin',
            headers={'Authorization': 'Bearer not.a.real.token'},
            content_type='application/json')
        assert resp.status_code == 401

    def test_register_begin_returns_options(self):
        """register/begin returns a valid PublicKeyCredentialCreationOptions blob."""
        token = self._register_and_login()
        resp = self.client.post('/auth/webauthn/register/begin',
            headers={'Authorization': f'Bearer {token}'},
            content_type='application/json')

        assert resp.status_code == 200
        data = json.loads(resp.data)

        # Core WebAuthn fields must be present
        assert 'challenge' in data
        assert 'rp' in data
        assert 'user' in data
        assert 'pubKeyCredParams' in data

        # RP configuration
        assert data['rp']['name'] == 'SecureVote'

        # Challenge must be non-empty
        assert len(data['challenge']) > 0

    def test_register_begin_stores_challenge_in_db(self):
        """register/begin persists a challenge on the user document."""
        token = self._register_and_login(student_id='C99900002')
        self.client.post('/auth/webauthn/register/begin',
            headers={'Authorization': f'Bearer {token}'},
            content_type='application/json')

        user = self.users_collection.find_one({'student_id': 'C99900002'})
        assert user.get('pending_webauthn_challenge') is not None
        assert user.get('challenge_expiry') is not None

    def test_register_begin_challenge_has_5min_expiry(self):
        """Challenge expiry is approximately 5 minutes in the future."""
        token = self._register_and_login(student_id='C99900003')
        before = datetime.datetime.now(datetime.timezone.utc)
        self.client.post('/auth/webauthn/register/begin',
            headers={'Authorization': f'Bearer {token}'},
            content_type='application/json')
        after = datetime.datetime.now(datetime.timezone.utc)

        user = self.users_collection.find_one({'student_id': 'C99900003'})
        expiry = user['challenge_expiry']
        if expiry.tzinfo is None:
            expiry = expiry.replace(tzinfo=datetime.timezone.utc)

        # Expiry should be roughly 5 minutes from now (within a 10s window)
        delta = (expiry - before).total_seconds()
        assert 290 <= delta <= 310, f"Expected ~300s, got {delta}s"

    def test_register_begin_second_call_overwrites_challenge(self):
        """Calling register/begin twice replaces the stored challenge."""
        token = self._register_and_login(student_id='C99900004')
        headers = {'Authorization': f'Bearer {token}'}

        self.client.post('/auth/webauthn/register/begin',
            headers=headers, content_type='application/json')
        user_after_first = self.users_collection.find_one({'student_id': 'C99900004'})
        first_challenge = user_after_first['pending_webauthn_challenge']

        self.client.post('/auth/webauthn/register/begin',
            headers=headers, content_type='application/json')
        user_after_second = self.users_collection.find_one({'student_id': 'C99900004'})
        second_challenge = user_after_second['pending_webauthn_challenge']

        # Two separate calls should produce different challenges
        assert first_challenge != second_challenge

    # ------------------------------------------------------------------
    # register/complete — error paths (no real authenticator available)
    # ------------------------------------------------------------------

    def test_register_complete_requires_auth(self):
        """register/complete must reject unauthenticated requests."""
        resp = self.client.post('/auth/webauthn/register/complete',
            json={},
            content_type='application/json')
        assert resp.status_code == 401

    def test_register_complete_no_challenge_returns_400(self):
        """register/complete returns 400 when no challenge has been initiated."""
        token = self._register_and_login(student_id='C99900005')
        # Do NOT call register/begin first — user has no pending challenge
        resp = self.client.post('/auth/webauthn/register/complete',
            headers={'Authorization': f'Bearer {token}'},
            json={'id': 'fake', 'rawId': 'fake', 'response': {}, 'type': 'public-key'},
            content_type='application/json')
        assert resp.status_code == 400
        data = json.loads(resp.data)
        assert 'expired' in data['error'].lower() or 'session' in data['error'].lower()

    def test_register_complete_expired_challenge_returns_400(self):
        """register/complete returns 400 when the stored challenge has expired."""
        token = self._register_and_login(student_id='C99900006')

        # Inject an already-expired challenge directly into the DB
        past = datetime.datetime.now(datetime.timezone.utc) - datetime.timedelta(minutes=10)
        self.users_collection.update_one(
            {'student_id': 'C99900006'},
            {'$set': {
                'pending_webauthn_challenge': base64.b64encode(b'expired-challenge').decode(),
                'challenge_expiry': past,
            }}
        )

        resp = self.client.post('/auth/webauthn/register/complete',
            headers={'Authorization': f'Bearer {token}'},
            json={'id': 'fake', 'rawId': 'fake', 'response': {}, 'type': 'public-key'},
            content_type='application/json')
        assert resp.status_code == 400
        data = json.loads(resp.data)
        assert 'expired' in data['error'].lower() or 'session' in data['error'].lower()


class TestWebAuthnLogin:
    """Tests for /auth/webauthn/login/begin and /auth/webauthn/login/complete."""

    @pytest.fixture(autouse=True)
    def setup(self):
        self.temp_keys_dir = tempfile.mkdtemp()

        from app import app, users_collection
        from crypto.key_manager import KeyManager
        from crypto.ballot_crypto import BallotCrypto
        import app as app_module

        km = KeyManager(keys_dir=self.temp_keys_dir)
        app_module.ballot_crypto = BallotCrypto(key_manager=km)
        app_module.limiter.enabled = False

        self.app = app
        self.client = app.test_client()
        self.users_collection = users_collection

        self.users_collection.delete_many({})
        yield
        self.users_collection.delete_many({})
        shutil.rmtree(self.temp_keys_dir)

    def _create_user(self, student_id='C99910001', password='TestPass123'):
        self.client.post('/auth/register',
            json={'student_id': student_id, 'password': password,
                  'programme': {'code': 'TU652', 'name': 'Computing'}},
            content_type='application/json')

    def _create_user_with_credentials(self, student_id='C99910002'):
        """Insert a user who already has a fake WebAuthn credential in the DB."""
        self._create_user(student_id=student_id)
        fake_cred = {
            'credential_id': 'ZmFrZS1jcmVkZW50aWFsLWlk',
            'credential_public_key': base64.b64encode(b'fake-public-key-bytes').decode(),
            'sign_count': 0,
            'transports': ['internal'],
            'device_type': 'single_device',
            'is_backed_up': False,
            'created_at': datetime.datetime.now(datetime.timezone.utc).isoformat(),
        }
        self.users_collection.update_one(
            {'student_id': student_id},
            {'$set': {'webauthn_credentials': [fake_cred]}}
        )
        return student_id

    # ------------------------------------------------------------------
    # login/begin
    # ------------------------------------------------------------------

    def test_login_begin_missing_student_id(self):
        """login/begin returns 400 when student_id is missing."""
        resp = self.client.post('/auth/webauthn/login/begin',
            json={},
            content_type='application/json')
        assert resp.status_code == 400

    def test_login_begin_unknown_user(self):
        """login/begin returns 404 for a student ID that does not exist."""
        resp = self.client.post('/auth/webauthn/login/begin',
            json={'student_id': 'DOESNOTEXIST'},
            content_type='application/json')
        assert resp.status_code == 404

    def test_login_begin_no_credentials_registered(self):
        """login/begin returns 400 when the user has no biometric credentials."""
        self._create_user(student_id='C99910003')
        resp = self.client.post('/auth/webauthn/login/begin',
            json={'student_id': 'C99910003'},
            content_type='application/json')
        assert resp.status_code == 400
        data = json.loads(resp.data)
        assert 'biometric' in data['error'].lower() or 'no' in data['error'].lower()

    def test_login_begin_returns_options_when_credentials_exist(self):
        """login/begin returns a valid PublicKeyCredentialRequestOptions blob."""
        sid = self._create_user_with_credentials(student_id='C99910004')
        resp = self.client.post('/auth/webauthn/login/begin',
            json={'student_id': sid},
            content_type='application/json')

        assert resp.status_code == 200
        data = json.loads(resp.data)
        assert 'challenge' in data
        assert len(data['challenge']) > 0

    def test_login_begin_stores_challenge(self):
        """login/begin persists a challenge on the user document."""
        sid = self._create_user_with_credentials(student_id='C99910005')
        self.client.post('/auth/webauthn/login/begin',
            json={'student_id': sid},
            content_type='application/json')

        user = self.users_collection.find_one({'student_id': sid})
        assert user.get('pending_webauthn_challenge') is not None

    # ------------------------------------------------------------------
    # login/complete — error paths
    # ------------------------------------------------------------------

    def test_login_complete_missing_fields(self):
        """login/complete returns 400 when required fields are absent."""
        resp = self.client.post('/auth/webauthn/login/complete',
            json={'student_id': 'C99910006'},  # missing 'assertion'
            content_type='application/json')
        assert resp.status_code == 400

    def test_login_complete_unknown_user(self):
        """login/complete returns 404 for an unknown student ID."""
        resp = self.client.post('/auth/webauthn/login/complete',
            json={'student_id': 'GHOST', 'assertion': {'id': 'x', 'rawId': 'x',
                  'response': {}, 'type': 'public-key'}},
            content_type='application/json')
        assert resp.status_code == 404

    def test_login_complete_expired_challenge(self):
        """login/complete returns 400 when the stored challenge has expired."""
        sid = self._create_user_with_credentials(student_id='C99910007')

        past = datetime.datetime.now(datetime.timezone.utc) - datetime.timedelta(minutes=10)
        self.users_collection.update_one(
            {'student_id': sid},
            {'$set': {
                'pending_webauthn_challenge': base64.b64encode(b'old-challenge').decode(),
                'challenge_expiry': past,
            }}
        )

        resp = self.client.post('/auth/webauthn/login/complete',
            json={'student_id': sid, 'assertion': {
                'id': 'ZmFrZS1jcmVkZW50aWFsLWlk',
                'rawId': 'ZmFrZS1jcmVkZW50aWFsLWlk',
                'response': {'clientDataJSON': '', 'authenticatorData': '',
                             'signature': ''},
                'type': 'public-key',
            }},
            content_type='application/json')

        assert resp.status_code == 400
        data = json.loads(resp.data)
        assert 'expired' in data['error'].lower() or 'session' in data['error'].lower()

    def test_login_complete_no_matching_credential(self):
        """login/complete returns 400 when assertion ID doesn't match stored credentials."""
        sid = self._create_user_with_credentials(student_id='C99910008')

        # Give the user a valid (non-expired) challenge
        future = datetime.datetime.now(datetime.timezone.utc) + datetime.timedelta(minutes=5)
        self.users_collection.update_one(
            {'student_id': sid},
            {'$set': {
                'pending_webauthn_challenge': base64.b64encode(b'valid-challenge').decode(),
                'challenge_expiry': future,
            }}
        )

        resp = self.client.post('/auth/webauthn/login/complete',
            json={'student_id': sid, 'assertion': {
                'id': 'dGhpcy1pZC1kb2VzLW5vdC1leGlzdA',   # not in DB
                'rawId': 'dGhpcy1pZC1kb2VzLW5vdC1leGlzdA',
                'response': {'clientDataJSON': '', 'authenticatorData': '',
                             'signature': ''},
                'type': 'public-key',
            }},
            content_type='application/json')

        assert resp.status_code == 400


class TestAuthMeWebAuthn:
    """/auth/me should expose WebAuthn credential metadata."""

    @pytest.fixture(autouse=True)
    def setup(self):
        self.temp_keys_dir = tempfile.mkdtemp()

        from app import app, users_collection
        from crypto.key_manager import KeyManager
        from crypto.ballot_crypto import BallotCrypto
        import app as app_module

        km = KeyManager(keys_dir=self.temp_keys_dir)
        app_module.ballot_crypto = BallotCrypto(key_manager=km)
        app_module.limiter.enabled = False

        self.app = app
        self.client = app.test_client()
        self.users_collection = users_collection

        self.users_collection.delete_many({})
        yield
        self.users_collection.delete_many({})
        shutil.rmtree(self.temp_keys_dir)

    def _register_and_login(self, student_id='C99920001', password='TestPass123'):
        self.client.post('/auth/register',
            json={'student_id': student_id, 'password': password,
                  'programme': {'code': 'TU652', 'name': 'Computing'}},
            content_type='application/json')
        resp = self.client.post('/auth/login',
            json={'student_id': student_id, 'password': password},
            content_type='application/json')
        return json.loads(resp.data)['token']

    def test_me_has_webauthn_false_by_default(self):
        """New users have no WebAuthn credentials — has_webauthn should be False."""
        token = self._register_and_login()
        resp = self.client.get('/auth/me',
            headers={'Authorization': f'Bearer {token}'})
        data = json.loads(resp.data)
        assert data['has_webauthn'] is False
        assert data['credential_count'] == 0
        assert data['webauthn_credentials'] == []

    def test_me_reflects_registered_credentials(self):
        """After injecting a credential, has_webauthn becomes True."""
        token = self._register_and_login(student_id='C99920002')

        fake_cred = {
            'credential_id': 'dGVzdC1jcmVkLWlk',
            'credential_public_key': base64.b64encode(b'pk').decode(),
            'sign_count': 0,
            'transports': ['internal'],
            'device_type': 'single_device',
            'is_backed_up': False,
            'friendly_name': 'Test Device',
            'created_at': datetime.datetime.now(datetime.timezone.utc).isoformat(),
        }
        self.users_collection.update_one(
            {'student_id': 'C99920002'},
            {'$set': {'webauthn_credentials': [fake_cred]}}
        )

        resp = self.client.get('/auth/me',
            headers={'Authorization': f'Bearer {token}'})
        data = json.loads(resp.data)
        assert data['has_webauthn'] is True
        assert data['credential_count'] == 1
        assert len(data['webauthn_credentials']) == 1
        assert data['webauthn_credentials'][0]['credential_id'] == 'dGVzdC1jcmVkLWlk'
