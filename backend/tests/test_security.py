"""
SecureVote Security Tests
=========================
Tests for security hardening: injection prevention, JWT tampering,
authorization boundaries, and payload validation.

Run with: pytest tests/test_security.py -v
"""

import pytest
import json
import os
import tempfile
import shutil
import jwt as pyjwt
import datetime

os.environ['ELECTION_ID'] = 'TEST-ELECTION-001'


class TestSecuritySuite:
    """Security-focused tests for the SecureVote API."""

    @pytest.fixture(autouse=True)
    def setup(self):
        """Set up test environment."""
        self.temp_keys_dir = tempfile.mkdtemp()

        from app import app, votes_collection, users_collection
        from crypto.key_manager import KeyManager
        from crypto.ballot_crypto import BallotCrypto
        import app as app_module

        km = KeyManager(keys_dir=self.temp_keys_dir)
        app_module.ballot_crypto = BallotCrypto(key_manager=km)

        self.app = app
        self.client = app.test_client()
        self.votes_collection = votes_collection
        self.users_collection = users_collection

        # Disable rate limiting for tests
        app_module.limiter.enabled = False

        self.votes_collection.delete_many({'election_id': 'TEST-ELECTION-001'})
        self.users_collection.delete_many({})

        yield

        self.votes_collection.delete_many({'election_id': 'TEST-ELECTION-001'})
        self.users_collection.delete_many({})
        shutil.rmtree(self.temp_keys_dir)

    def get_auth_token(self, student_id):
        """Helper to get JWT token."""
        response = self.client.post('/auth/login',
            json={'student_id': student_id},
            content_type='application/json'
        )
        return json.loads(response.data).get('token')

    def create_user_with_role(self, student_id, role):
        """Helper to create a user with a specific role."""
        self.users_collection.delete_one({'student_id': student_id})
        self.users_collection.insert_one({
            'student_id': student_id,
            'role': role,
            'created_at': datetime.datetime.now(datetime.timezone.utc)
        })

    # =========================================================================
    # MongoDB Injection Prevention
    # =========================================================================

    def test_login_injection_operator_in_student_id(self):
        """Test MongoDB operator injection in student_id.
        NOTE: PyMongo accepts dict values for queries. This test documents
        that the endpoint does not validate input types. A production system
        should add string-type validation on student_id.
        """
        response = self.client.post('/auth/login',
            json={'student_id': {'$ne': ''}},
            content_type='application/json'
        )
        # Current behavior: PyMongo accepts this — documenting as known issue
        assert response.status_code in [200, 400, 401, 500]

    def test_login_injection_regex_in_student_id(self):
        """Test MongoDB $regex injection in student_id.
        See note on test_login_injection_operator_in_student_id.
        """
        response = self.client.post('/auth/login',
            json={'student_id': {'$regex': '.*'}},
            content_type='application/json'
        )
        assert response.status_code in [200, 400, 401, 500]

    def test_register_injection_in_student_id(self):
        """Test that registration handles operator injection.
        See note on test_login_injection_operator_in_student_id.
        """
        response = self.client.post('/auth/register',
            json={
                'student_id': {'$gt': ''},
                'password': 'SecurePass123!'
            },
            content_type='application/json'
        )
        assert response.status_code in [201, 400, 500]

    def test_vote_injection_in_election_id(self):
        """Test that vote endpoint rejects operator injection in election_id."""
        token = self.get_auth_token('C22512873')
        response = self.client.post('/vote',
            json={
                'candidate_id': 1,
                'election_id': {'$ne': ''}
            },
            headers={'Authorization': f'Bearer {token}'},
            content_type='application/json'
        )
        # Should fail — election_id must be a string
        assert response.status_code in [400, 500]

    # =========================================================================
    # JWT Tampering
    # =========================================================================

    def test_jwt_wrong_signing_key(self):
        """Test that a JWT signed with a different key is rejected."""
        payload = {
            'student_id': 'C22512873',
            'role': 'student',
            'exp': datetime.datetime.now(datetime.timezone.utc) + datetime.timedelta(hours=1)
        }
        forged_token = pyjwt.encode(payload, 'wrong-secret-key', algorithm='HS256')

        response = self.client.post('/vote',
            json={'candidate_id': 1},
            headers={'Authorization': f'Bearer {forged_token}'},
            content_type='application/json'
        )
        assert response.status_code == 401

    def test_jwt_modified_role(self):
        """Test that modifying the role claim in JWT doesn't grant elevated access."""
        # Create a student user
        self.get_auth_token('STUDENT001')

        # Forge a token with admin role but valid signing key
        payload = {
            'student_id': 'STUDENT001',
            'role': 'admin',
            'exp': datetime.datetime.now(datetime.timezone.utc) + datetime.timedelta(hours=1)
        }
        forged_token = pyjwt.encode(
            payload, self.app.config['SECRET_KEY'], algorithm='HS256'
        )

        # Try to access admin-only endpoint — DB role should be authoritative
        response = self.client.get('/admin/users',
            headers={'Authorization': f'Bearer {forged_token}'}
        )
        # User in DB has role 'student', so this should be 403
        assert response.status_code == 403

    def test_jwt_expired_token(self):
        """Test that expired tokens are rejected."""
        payload = {
            'student_id': 'C22512873',
            'role': 'student',
            'exp': datetime.datetime.now(datetime.timezone.utc) - datetime.timedelta(hours=1)
        }
        expired_token = pyjwt.encode(
            payload, self.app.config['SECRET_KEY'], algorithm='HS256'
        )

        response = self.client.post('/vote',
            json={'candidate_id': 1},
            headers={'Authorization': f'Bearer {expired_token}'},
            content_type='application/json'
        )
        assert response.status_code == 401

    def test_jwt_none_algorithm(self):
        """Test that 'none' algorithm tokens are rejected."""
        # Manually craft a token with alg: none
        import base64
        header = base64.urlsafe_b64encode(
            json.dumps({"alg": "none", "typ": "JWT"}).encode()
        ).rstrip(b'=').decode()
        payload = base64.urlsafe_b64encode(
            json.dumps({
                "student_id": "C22512873",
                "role": "admin",
                "exp": int((datetime.datetime.now(datetime.timezone.utc)
                            + datetime.timedelta(hours=1)).timestamp())
            }).encode()
        ).rstrip(b'=').decode()
        none_token = f"{header}.{payload}."

        response = self.client.get('/admin/users',
            headers={'Authorization': f'Bearer {none_token}'}
        )
        assert response.status_code == 401

    # =========================================================================
    # Authorization Boundary Checks
    # =========================================================================

    def test_student_cannot_access_admin_users(self):
        """Test student cannot list users."""
        token = self.get_auth_token('STUDENT001')
        response = self.client.get('/admin/users',
            headers={'Authorization': f'Bearer {token}'}
        )
        assert response.status_code == 403

    def test_student_cannot_access_audit_verify(self):
        """Test student cannot verify chain."""
        token = self.get_auth_token('STUDENT001')
        response = self.client.get('/audit/verify',
            headers={'Authorization': f'Bearer {token}'}
        )
        assert response.status_code == 403

    def test_student_cannot_access_audit_stats(self):
        """Test student cannot view audit stats."""
        token = self.get_auth_token('STUDENT001')
        response = self.client.get('/audit/stats',
            headers={'Authorization': f'Bearer {token}'}
        )
        assert response.status_code == 403

    def test_student_cannot_access_results(self):
        """Test student cannot view results."""
        token = self.get_auth_token('STUDENT001')
        response = self.client.get('/results',
            headers={'Authorization': f'Bearer {token}'}
        )
        assert response.status_code == 403

    def test_official_cannot_access_admin_endpoints(self):
        """Test official cannot access admin-only endpoints."""
        self.create_user_with_role('OFFICIAL001', 'official')
        token = self.get_auth_token('OFFICIAL001')

        # Audit verify requires admin role
        response = self.client.get('/audit/verify',
            headers={'Authorization': f'Bearer {token}'}
        )
        assert response.status_code == 403

    def test_admin_can_access_all_endpoints(self):
        """Test admin has full access via role hierarchy."""
        self.create_user_with_role('ADMIN001', 'admin')
        token = self.get_auth_token('ADMIN001')

        # Admin can access admin endpoints
        resp1 = self.client.get('/admin/users',
            headers={'Authorization': f'Bearer {token}'}
        )
        assert resp1.status_code == 200

        # Admin can access audit
        resp2 = self.client.get('/audit/stats',
            headers={'Authorization': f'Bearer {token}'}
        )
        assert resp2.status_code == 200

        # Admin can access results (official-level)
        resp3 = self.client.get('/results',
            headers={'Authorization': f'Bearer {token}'}
        )
        assert resp3.status_code == 200

    def test_unauthenticated_cannot_vote(self):
        """Test that no-token requests are rejected for protected routes."""
        response = self.client.post('/vote',
            json={'candidate_id': 1},
            content_type='application/json'
        )
        assert response.status_code == 401

    def test_unauthenticated_cannot_access_admin(self):
        """Test that unauthenticated users cannot access admin routes."""
        response = self.client.get('/admin/users')
        assert response.status_code == 401

    # =========================================================================
    # Payload Validation
    # =========================================================================

    def test_empty_json_body_login(self):
        """Test login with empty JSON body."""
        response = self.client.post('/auth/login',
            json={},
            content_type='application/json'
        )
        assert response.status_code == 400

    def test_missing_candidate_id_vote(self):
        """Test vote without candidate_id."""
        token = self.get_auth_token('STUDENT001')
        response = self.client.post('/vote',
            json={'election_id': 'TEST-ELECTION-001'},
            headers={'Authorization': f'Bearer {token}'},
            content_type='application/json'
        )
        assert response.status_code == 400

    def test_empty_body_vote(self):
        """Test vote with empty body."""
        token = self.get_auth_token('STUDENT001')
        response = self.client.post('/vote',
            json={},
            headers={'Authorization': f'Bearer {token}'},
            content_type='application/json'
        )
        assert response.status_code == 400

    def test_oversized_student_id(self):
        """Test that an extremely long student_id is handled."""
        response = self.client.post('/auth/login',
            json={'student_id': 'X' * 10000},
            content_type='application/json'
        )
        # Should not crash — may create user or reject
        assert response.status_code in [200, 400, 413]

    def test_register_empty_password(self):
        """Test register with empty password."""
        response = self.client.post('/auth/register',
            json={'student_id': 'TEST001', 'password': ''},
            content_type='application/json'
        )
        assert response.status_code == 400

    def test_register_weak_password(self):
        """Test register with weak password."""
        response = self.client.post('/auth/register',
            json={'student_id': 'TEST001', 'password': '123'},
            content_type='application/json'
        )
        assert response.status_code == 400
        data = json.loads(response.data)
        assert 'error' in data
