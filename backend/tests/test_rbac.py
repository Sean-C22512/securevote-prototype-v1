"""
SecureVote RBAC Tests
=====================
Tests for Role-Based Access Control.

Run with: pytest tests/test_rbac.py -v
"""

import pytest
import json
import os
import tempfile
import shutil

os.environ['ELECTION_ID'] = 'TEST-ELECTION-001'


class TestRBAC:
    """Tests for role-based access control."""

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

        # Clean up
        self.votes_collection.delete_many({'election_id': 'TEST-ELECTION-001'})
        self.users_collection.delete_many({})

        yield

        self.votes_collection.delete_many({'election_id': 'TEST-ELECTION-001'})
        self.users_collection.delete_many({})
        shutil.rmtree(self.temp_keys_dir)

    def create_user_with_role(self, student_id, role):
        """Helper to create a user with a specific role."""
        import datetime
        self.users_collection.insert_one({
            'student_id': student_id,
            'role': role,
            'created_at': datetime.datetime.now(datetime.timezone.utc)
        })

    def get_token(self, student_id):
        """Helper to get JWT token."""
        response = self.client.post('/auth/login',
            json={'student_id': student_id},
            content_type='application/json'
        )
        return json.loads(response.data).get('token')

    # =========================================================================
    # Login Tests
    # =========================================================================

    def test_login_returns_role(self):
        """Test that login response includes user role."""
        response = self.client.post('/auth/login',
            json={'student_id': 'C22512873'},
            content_type='application/json'
        )

        assert response.status_code == 200
        data = json.loads(response.data)
        assert 'role' in data
        assert data['role'] == 'student'  # Default role

    def test_login_returns_existing_user_role(self):
        """Test that login returns correct role for existing user."""
        self.create_user_with_role('ADMIN001', 'admin')

        response = self.client.post('/auth/login',
            json={'student_id': 'ADMIN001'},
            content_type='application/json'
        )

        data = json.loads(response.data)
        assert data['role'] == 'admin'

    def test_new_user_gets_student_role(self):
        """Test that new users are created with 'student' role."""
        self.client.post('/auth/login',
            json={'student_id': 'NEWUSER001'},
            content_type='application/json'
        )

        user = self.users_collection.find_one({'student_id': 'NEWUSER001'})
        assert user['role'] == 'student'

    # =========================================================================
    # /auth/me Tests
    # =========================================================================

    def test_auth_me_returns_user_info(self):
        """Test /auth/me endpoint returns current user info."""
        self.create_user_with_role('C22512873', 'official')
        token = self.get_token('C22512873')

        response = self.client.get('/auth/me',
            headers={'Authorization': f'Bearer {token}'}
        )

        assert response.status_code == 200
        data = json.loads(response.data)
        assert data['student_id'] == 'C22512873'
        assert data['role'] == 'official'

    def test_auth_me_requires_auth(self):
        """Test /auth/me requires authentication."""
        response = self.client.get('/auth/me')
        assert response.status_code == 401

    # =========================================================================
    # Vote Endpoint Role Tests
    # =========================================================================

    def test_student_can_vote(self):
        """Test that students can vote."""
        self.create_user_with_role('C22512873', 'student')
        token = self.get_token('C22512873')

        response = self.client.post('/vote',
            json={'candidate_id': 1},
            headers={'Authorization': f'Bearer {token}'},
            content_type='application/json'
        )

        assert response.status_code == 201

    def test_official_can_vote(self):
        """Test that officials can vote (inherits student permissions)."""
        self.create_user_with_role('OFFICIAL001', 'official')
        token = self.get_token('OFFICIAL001')

        response = self.client.post('/vote',
            json={'candidate_id': 1},
            headers={'Authorization': f'Bearer {token}'},
            content_type='application/json'
        )

        assert response.status_code == 201

    def test_admin_can_vote(self):
        """Test that admins can vote (inherits all permissions)."""
        self.create_user_with_role('ADMIN001', 'admin')
        token = self.get_token('ADMIN001')

        response = self.client.post('/vote',
            json={'candidate_id': 1},
            headers={'Authorization': f'Bearer {token}'},
            content_type='application/json'
        )

        assert response.status_code == 201

    # =========================================================================
    # Results Endpoint Role Tests
    # =========================================================================

    def test_student_cannot_view_results(self):
        """Test that students cannot view results."""
        self.create_user_with_role('C22512873', 'student')
        token = self.get_token('C22512873')

        response = self.client.get('/results',
            headers={'Authorization': f'Bearer {token}'}
        )

        assert response.status_code == 403
        data = json.loads(response.data)
        assert 'Insufficient permissions' in data['error']

    def test_official_can_view_results(self):
        """Test that officials can view results."""
        self.create_user_with_role('OFFICIAL001', 'official')
        token = self.get_token('OFFICIAL001')

        response = self.client.get('/results',
            headers={'Authorization': f'Bearer {token}'}
        )

        assert response.status_code == 200

    def test_admin_can_view_results(self):
        """Test that admins can view results."""
        self.create_user_with_role('ADMIN001', 'admin')
        token = self.get_token('ADMIN001')

        response = self.client.get('/results',
            headers={'Authorization': f'Bearer {token}'}
        )

        assert response.status_code == 200

    # =========================================================================
    # Audit Endpoint Role Tests
    # =========================================================================

    def test_student_cannot_access_audit_verify(self):
        """Test that students cannot access audit/verify."""
        self.create_user_with_role('C22512873', 'student')
        token = self.get_token('C22512873')

        response = self.client.get('/audit/verify',
            headers={'Authorization': f'Bearer {token}'}
        )

        assert response.status_code == 403

    def test_official_cannot_access_audit_verify(self):
        """Test that officials cannot access audit/verify."""
        self.create_user_with_role('OFFICIAL001', 'official')
        token = self.get_token('OFFICIAL001')

        response = self.client.get('/audit/verify',
            headers={'Authorization': f'Bearer {token}'}
        )

        assert response.status_code == 403

    def test_admin_can_access_audit_verify(self):
        """Test that admins can access audit/verify."""
        self.create_user_with_role('ADMIN001', 'admin')
        token = self.get_token('ADMIN001')

        response = self.client.get('/audit/verify',
            headers={'Authorization': f'Bearer {token}'}
        )

        assert response.status_code == 200

    def test_admin_can_access_audit_stats(self):
        """Test that admins can access audit/stats."""
        self.create_user_with_role('ADMIN001', 'admin')
        token = self.get_token('ADMIN001')

        response = self.client.get('/audit/stats',
            headers={'Authorization': f'Bearer {token}'}
        )

        assert response.status_code == 200

    # =========================================================================
    # Admin User Management Tests
    # =========================================================================

    def test_admin_can_list_users(self):
        """Test that admins can list all users."""
        self.create_user_with_role('ADMIN001', 'admin')
        self.create_user_with_role('C22512873', 'student')
        self.create_user_with_role('OFFICIAL001', 'official')
        token = self.get_token('ADMIN001')

        response = self.client.get('/admin/users',
            headers={'Authorization': f'Bearer {token}'}
        )

        assert response.status_code == 200
        data = json.loads(response.data)
        assert data['total'] == 3

    def test_non_admin_cannot_list_users(self):
        """Test that non-admins cannot list users."""
        self.create_user_with_role('OFFICIAL001', 'official')
        token = self.get_token('OFFICIAL001')

        response = self.client.get('/admin/users',
            headers={'Authorization': f'Bearer {token}'}
        )

        assert response.status_code == 403

    def test_admin_can_update_user_role(self):
        """Test that admins can update user roles."""
        self.create_user_with_role('ADMIN001', 'admin')
        self.create_user_with_role('C22512873', 'student')
        token = self.get_token('ADMIN001')

        response = self.client.put('/admin/users/C22512873/role',
            json={'role': 'official'},
            headers={'Authorization': f'Bearer {token}'},
            content_type='application/json'
        )

        assert response.status_code == 200

        # Verify role was updated
        user = self.users_collection.find_one({'student_id': 'C22512873'})
        assert user['role'] == 'official'

    def test_admin_cannot_demote_self(self):
        """Test that admins cannot demote themselves."""
        self.create_user_with_role('ADMIN001', 'admin')
        token = self.get_token('ADMIN001')

        response = self.client.put('/admin/users/ADMIN001/role',
            json={'role': 'student'},
            headers={'Authorization': f'Bearer {token}'},
            content_type='application/json'
        )

        assert response.status_code == 400
        data = json.loads(response.data)
        assert 'Cannot demote yourself' in data['error']

    def test_update_role_invalid_role(self):
        """Test that invalid roles are rejected."""
        self.create_user_with_role('ADMIN001', 'admin')
        self.create_user_with_role('C22512873', 'student')
        token = self.get_token('ADMIN001')

        response = self.client.put('/admin/users/C22512873/role',
            json={'role': 'superadmin'},
            headers={'Authorization': f'Bearer {token}'},
            content_type='application/json'
        )

        assert response.status_code == 400
        data = json.loads(response.data)
        assert 'Invalid role' in data['error']

    def test_update_role_user_not_found(self):
        """Test that updating non-existent user returns 404."""
        self.create_user_with_role('ADMIN001', 'admin')
        token = self.get_token('ADMIN001')

        response = self.client.put('/admin/users/NONEXISTENT/role',
            json={'role': 'official'},
            headers={'Authorization': f'Bearer {token}'},
            content_type='application/json'
        )

        assert response.status_code == 404

    def test_admin_can_create_user(self):
        """Test that admins can create new users with roles."""
        self.create_user_with_role('ADMIN001', 'admin')
        token = self.get_token('ADMIN001')

        response = self.client.post('/admin/users',
            json={'student_id': 'NEWOFFICIAL', 'role': 'official'},
            headers={'Authorization': f'Bearer {token}'},
            content_type='application/json'
        )

        assert response.status_code == 201

        user = self.users_collection.find_one({'student_id': 'NEWOFFICIAL'})
        assert user['role'] == 'official'

    def test_create_duplicate_user_fails(self):
        """Test that creating duplicate user returns 409."""
        self.create_user_with_role('ADMIN001', 'admin')
        self.create_user_with_role('C22512873', 'student')
        token = self.get_token('ADMIN001')

        response = self.client.post('/admin/users',
            json={'student_id': 'C22512873', 'role': 'official'},
            headers={'Authorization': f'Bearer {token}'},
            content_type='application/json'
        )

        assert response.status_code == 409

    # =========================================================================
    # Authentication Error Tests
    # =========================================================================

    def test_missing_token_returns_401(self):
        """Test that missing token returns 401."""
        response = self.client.get('/results')
        assert response.status_code == 401

    def test_invalid_token_returns_401(self):
        """Test that invalid token returns 401."""
        response = self.client.get('/results',
            headers={'Authorization': 'Bearer invalid_token'}
        )
        assert response.status_code == 401

    def test_expired_token_returns_401(self):
        """Test that expired token returns 401."""
        import jwt
        import datetime
        from flask import current_app

        self.create_user_with_role('C22512873', 'admin')

        with self.app.app_context():
            expired_token = jwt.encode({
                'student_id': 'C22512873',
                'exp': datetime.datetime.now(datetime.timezone.utc) - datetime.timedelta(hours=1)
            }, self.app.config['SECRET_KEY'], algorithm='HS256')

        response = self.client.get('/results',
            headers={'Authorization': f'Bearer {expired_token}'}
        )
        assert response.status_code == 401


class TestRoleHierarchy:
    """Tests for role hierarchy (inheritance)."""

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
        self.users_collection = users_collection
        self.votes_collection = votes_collection

        self.users_collection.delete_many({})
        self.votes_collection.delete_many({'election_id': 'TEST-ELECTION-001'})

        yield

        self.users_collection.delete_many({})
        self.votes_collection.delete_many({'election_id': 'TEST-ELECTION-001'})
        shutil.rmtree(self.temp_keys_dir)

    def create_user_with_role(self, student_id, role):
        """Helper to create user with role."""
        import datetime
        self.users_collection.insert_one({
            'student_id': student_id,
            'role': role,
            'created_at': datetime.datetime.now(datetime.timezone.utc)
        })

    def get_token(self, student_id):
        """Helper to get token."""
        response = self.client.post('/auth/login',
            json={'student_id': student_id},
            content_type='application/json'
        )
        return json.loads(response.data).get('token')

    def test_admin_inherits_official_permissions(self):
        """Test that admin can do everything official can do."""
        self.create_user_with_role('ADMIN001', 'admin')
        token = self.get_token('ADMIN001')

        # Admin should be able to view results (official permission)
        response = self.client.get('/results',
            headers={'Authorization': f'Bearer {token}'}
        )
        assert response.status_code == 200

    def test_admin_inherits_student_permissions(self):
        """Test that admin can do everything student can do."""
        self.create_user_with_role('ADMIN001', 'admin')
        token = self.get_token('ADMIN001')

        # Admin should be able to vote (student permission)
        response = self.client.post('/vote',
            json={'candidate_id': 1},
            headers={'Authorization': f'Bearer {token}'},
            content_type='application/json'
        )
        assert response.status_code == 201

    def test_official_inherits_student_permissions(self):
        """Test that official can do everything student can do."""
        self.create_user_with_role('OFFICIAL001', 'official')
        token = self.get_token('OFFICIAL001')

        # Official should be able to vote
        response = self.client.post('/vote',
            json={'candidate_id': 1},
            headers={'Authorization': f'Bearer {token}'},
            content_type='application/json'
        )
        assert response.status_code == 201

    def test_official_cannot_do_admin_tasks(self):
        """Test that official cannot do admin-only tasks."""
        self.create_user_with_role('OFFICIAL001', 'official')
        token = self.get_token('OFFICIAL001')

        # Official should NOT be able to verify chain
        response = self.client.get('/audit/verify',
            headers={'Authorization': f'Bearer {token}'}
        )
        assert response.status_code == 403

    def test_student_has_minimal_permissions(self):
        """Test that student has only basic permissions."""
        self.create_user_with_role('C22512873', 'student')
        token = self.get_token('C22512873')

        # Student can vote
        vote_response = self.client.post('/vote',
            json={'candidate_id': 1},
            headers={'Authorization': f'Bearer {token}'},
            content_type='application/json'
        )
        assert vote_response.status_code == 201

        # Student cannot view results
        results_response = self.client.get('/results',
            headers={'Authorization': f'Bearer {token}'}
        )
        assert results_response.status_code == 403

        # Student cannot access audit
        audit_response = self.client.get('/audit/verify',
            headers={'Authorization': f'Bearer {token}'}
        )
        assert audit_response.status_code == 403
