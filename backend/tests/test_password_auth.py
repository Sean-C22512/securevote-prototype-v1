"""
SecureVote Password Authentication Tests
========================================
Tests for user registration, login with password, and password management.

Run with: pytest tests/test_password_auth.py -v
"""

import pytest
import json
import os
import tempfile
import shutil
from datetime import datetime, timezone

os.environ['ELECTION_ID'] = 'TEST-ELECTION-001'


class TestPasswordUtilities:
    """Tests for password hashing and validation utilities."""

    def test_hash_password(self):
        """Test password hashing."""
        from utils.password import hash_password

        hashed = hash_password("TestPassword123")

        assert hashed is not None
        assert hashed != "TestPassword123"
        assert hashed.startswith("$2b$")  # bcrypt prefix

    def test_hash_different_each_time(self):
        """Test that same password produces different hashes (salting)."""
        from utils.password import hash_password

        hash1 = hash_password("TestPassword123")
        hash2 = hash_password("TestPassword123")

        assert hash1 != hash2

    def test_verify_password_correct(self):
        """Test verifying correct password."""
        from utils.password import hash_password, verify_password

        password = "TestPassword123"
        hashed = hash_password(password)

        assert verify_password(password, hashed) is True

    def test_verify_password_incorrect(self):
        """Test verifying incorrect password."""
        from utils.password import hash_password, verify_password

        hashed = hash_password("TestPassword123")

        assert verify_password("WrongPassword", hashed) is False

    def test_validate_password_strength_valid(self):
        """Test password that meets all requirements."""
        from utils.password import validate_password_strength

        is_valid, errors = validate_password_strength("SecurePass123")

        assert is_valid is True
        assert len(errors) == 0

    def test_validate_password_too_short(self):
        """Test password that is too short."""
        from utils.password import validate_password_strength

        is_valid, errors = validate_password_strength("Short1")

        assert is_valid is False
        assert any("at least" in e.lower() for e in errors)

    def test_validate_password_no_uppercase(self):
        """Test password without uppercase."""
        from utils.password import validate_password_strength

        is_valid, errors = validate_password_strength("lowercase123")

        assert is_valid is False
        assert any("uppercase" in e.lower() for e in errors)

    def test_validate_password_no_lowercase(self):
        """Test password without lowercase."""
        from utils.password import validate_password_strength

        is_valid, errors = validate_password_strength("UPPERCASE123")

        assert is_valid is False
        assert any("lowercase" in e.lower() for e in errors)

    def test_validate_password_no_digit(self):
        """Test password without digit."""
        from utils.password import validate_password_strength

        is_valid, errors = validate_password_strength("NoDigitsHere")

        assert is_valid is False
        assert any("digit" in e.lower() for e in errors)

    def test_validate_common_password(self):
        """Test rejection of common passwords."""
        from utils.password import validate_password_strength

        is_valid, errors = validate_password_strength("password123")

        assert is_valid is False
        assert any("common" in e.lower() for e in errors)


class TestUserRegistration:
    """Tests for user registration."""

    @pytest.fixture(autouse=True)
    def setup(self):
        """Set up test environment."""
        self.temp_keys_dir = tempfile.mkdtemp()

        from app import app, users_collection
        from crypto.key_manager import KeyManager
        from crypto.ballot_crypto import BallotCrypto
        import app as app_module

        km = KeyManager(keys_dir=self.temp_keys_dir)
        app_module.ballot_crypto = BallotCrypto(key_manager=km)

        self.app = app
        self.client = app.test_client()
        self.users_collection = users_collection

        self.users_collection.delete_many({})

        yield

        self.users_collection.delete_many({})
        shutil.rmtree(self.temp_keys_dir)

    def test_register_success(self):
        """Test successful user registration."""
        response = self.client.post('/auth/register',
            json={
                'student_id': 'C22512873',
                'password': 'SecurePass123',
                'email': 'student@tudublin.ie'
            },
            content_type='application/json'
        )

        assert response.status_code == 201
        data = json.loads(response.data)
        assert data['student_id'] == 'C22512873'

        # Verify user was created with password hash
        user = self.users_collection.find_one({'student_id': 'C22512873'})
        assert user is not None
        assert 'password_hash' in user
        assert user['password_hash'].startswith('$2b$')
        assert user['email'] == 'student@tudublin.ie'

    def test_register_without_email(self):
        """Test registration without optional email."""
        response = self.client.post('/auth/register',
            json={
                'student_id': 'C22512874',
                'password': 'SecurePass123'
            },
            content_type='application/json'
        )

        assert response.status_code == 201

    def test_register_duplicate_user(self):
        """Test registration of duplicate user."""
        # Register first time
        self.client.post('/auth/register',
            json={'student_id': 'C22512873', 'password': 'SecurePass123'},
            content_type='application/json'
        )

        # Try to register again
        response = self.client.post('/auth/register',
            json={'student_id': 'C22512873', 'password': 'AnotherPass456'},
            content_type='application/json'
        )

        assert response.status_code == 409

    def test_register_weak_password(self):
        """Test registration with weak password."""
        response = self.client.post('/auth/register',
            json={'student_id': 'C22512873', 'password': 'weak'},
            content_type='application/json'
        )

        assert response.status_code == 400
        data = json.loads(response.data)
        assert 'requirements' in data
        assert 'details' in data

    def test_register_missing_student_id(self):
        """Test registration without student ID."""
        response = self.client.post('/auth/register',
            json={'password': 'SecurePass123'},
            content_type='application/json'
        )

        assert response.status_code == 400

    def test_register_missing_password(self):
        """Test registration without password."""
        response = self.client.post('/auth/register',
            json={'student_id': 'C22512873'},
            content_type='application/json'
        )

        assert response.status_code == 400


class TestLoginWithPassword:
    """Tests for login with password."""

    @pytest.fixture(autouse=True)
    def setup(self):
        """Set up test environment."""
        self.temp_keys_dir = tempfile.mkdtemp()

        from app import app, users_collection
        from crypto.key_manager import KeyManager
        from crypto.ballot_crypto import BallotCrypto
        import app as app_module

        km = KeyManager(keys_dir=self.temp_keys_dir)
        app_module.ballot_crypto = BallotCrypto(key_manager=km)

        self.app = app
        self.client = app.test_client()
        self.users_collection = users_collection

        self.users_collection.delete_many({})

        yield

        self.users_collection.delete_many({})
        shutil.rmtree(self.temp_keys_dir)

    def register_user(self, student_id, password):
        """Helper to register a user."""
        self.client.post('/auth/register',
            json={'student_id': student_id, 'password': password},
            content_type='application/json'
        )

    def test_login_success(self):
        """Test successful login with password."""
        self.register_user('C22512873', 'SecurePass123')

        response = self.client.post('/auth/login',
            json={'student_id': 'C22512873', 'password': 'SecurePass123'},
            content_type='application/json'
        )

        assert response.status_code == 200
        data = json.loads(response.data)
        assert 'token' in data
        assert data['student_id'] == 'C22512873'
        assert data['role'] == 'student'

    def test_login_wrong_password(self):
        """Test login with wrong password."""
        self.register_user('C22512873', 'SecurePass123')

        response = self.client.post('/auth/login',
            json={'student_id': 'C22512873', 'password': 'WrongPassword'},
            content_type='application/json'
        )

        assert response.status_code == 401

    def test_login_missing_password(self):
        """Test login without password for user who has password."""
        self.register_user('C22512873', 'SecurePass123')

        response = self.client.post('/auth/login',
            json={'student_id': 'C22512873'},
            content_type='application/json'
        )

        assert response.status_code == 400

    def test_login_nonexistent_user_with_password(self):
        """Test login with password for non-existent user."""
        response = self.client.post('/auth/login',
            json={'student_id': 'NONEXISTENT', 'password': 'SomePass123'},
            content_type='application/json'
        )

        assert response.status_code == 401

    def test_login_legacy_user_no_password(self):
        """Test login for legacy user without password (backward compatibility)."""
        # Create legacy user without password
        self.users_collection.insert_one({
            'student_id': 'LEGACY001',
            'role': 'student',
            'created_at': datetime.now(timezone.utc)
        })

        response = self.client.post('/auth/login',
            json={'student_id': 'LEGACY001'},
            content_type='application/json'
        )

        assert response.status_code == 200
        data = json.loads(response.data)
        assert 'token' in data


class TestPasswordManagement:
    """Tests for password change and set operations."""

    @pytest.fixture(autouse=True)
    def setup(self):
        """Set up test environment."""
        self.temp_keys_dir = tempfile.mkdtemp()

        from app import app, users_collection
        from crypto.key_manager import KeyManager
        from crypto.ballot_crypto import BallotCrypto
        import app as app_module

        km = KeyManager(keys_dir=self.temp_keys_dir)
        app_module.ballot_crypto = BallotCrypto(key_manager=km)

        self.app = app
        self.client = app.test_client()
        self.users_collection = users_collection

        self.users_collection.delete_many({})

        yield

        self.users_collection.delete_many({})
        shutil.rmtree(self.temp_keys_dir)

    def register_and_login(self, student_id, password):
        """Helper to register and get token."""
        self.client.post('/auth/register',
            json={'student_id': student_id, 'password': password},
            content_type='application/json'
        )
        response = self.client.post('/auth/login',
            json={'student_id': student_id, 'password': password},
            content_type='application/json'
        )
        return json.loads(response.data)['token']

    def test_change_password_success(self):
        """Test successful password change."""
        token = self.register_and_login('C22512873', 'OldPassword123')

        response = self.client.post('/auth/change-password',
            json={
                'current_password': 'OldPassword123',
                'new_password': 'NewPassword456'
            },
            headers={'Authorization': f'Bearer {token}'},
            content_type='application/json'
        )

        assert response.status_code == 200

        # Verify can login with new password
        login_response = self.client.post('/auth/login',
            json={'student_id': 'C22512873', 'password': 'NewPassword456'},
            content_type='application/json'
        )
        assert login_response.status_code == 200

        # Verify cannot login with old password
        old_login = self.client.post('/auth/login',
            json={'student_id': 'C22512873', 'password': 'OldPassword123'},
            content_type='application/json'
        )
        assert old_login.status_code == 401

    def test_change_password_wrong_current(self):
        """Test password change with wrong current password."""
        token = self.register_and_login('C22512873', 'OldPassword123')

        response = self.client.post('/auth/change-password',
            json={
                'current_password': 'WrongCurrent',
                'new_password': 'NewPassword456'
            },
            headers={'Authorization': f'Bearer {token}'},
            content_type='application/json'
        )

        assert response.status_code == 401

    def test_change_password_weak_new(self):
        """Test password change with weak new password."""
        token = self.register_and_login('C22512873', 'OldPassword123')

        response = self.client.post('/auth/change-password',
            json={
                'current_password': 'OldPassword123',
                'new_password': 'weak'
            },
            headers={'Authorization': f'Bearer {token}'},
            content_type='application/json'
        )

        assert response.status_code == 400

    def test_set_password_for_legacy_user(self):
        """Test setting password for legacy user."""
        # Create legacy user without password
        self.users_collection.insert_one({
            'student_id': 'LEGACY001',
            'role': 'student',
            'created_at': datetime.now(timezone.utc)
        })

        # Login as legacy user
        login_response = self.client.post('/auth/login',
            json={'student_id': 'LEGACY001'},
            content_type='application/json'
        )
        token = json.loads(login_response.data)['token']

        # Set password
        response = self.client.post('/auth/set-password',
            json={'password': 'NewSecurePass123'},
            headers={'Authorization': f'Bearer {token}'},
            content_type='application/json'
        )

        assert response.status_code == 200

        # Verify can now login with password
        new_login = self.client.post('/auth/login',
            json={'student_id': 'LEGACY001', 'password': 'NewSecurePass123'},
            content_type='application/json'
        )
        assert new_login.status_code == 200

    def test_set_password_already_has_password(self):
        """Test set-password fails if user already has password."""
        token = self.register_and_login('C22512873', 'ExistingPass123')

        response = self.client.post('/auth/set-password',
            json={'password': 'AnotherPass456'},
            headers={'Authorization': f'Bearer {token}'},
            content_type='application/json'
        )

        assert response.status_code == 400
        assert 'change-password' in json.loads(response.data)['error'].lower()

    def test_auth_me_shows_has_password(self):
        """Test /auth/me shows whether user has password."""
        token = self.register_and_login('C22512873', 'SecurePass123')

        response = self.client.get('/auth/me',
            headers={'Authorization': f'Bearer {token}'}
        )

        assert response.status_code == 200
        data = json.loads(response.data)
        assert data['has_password'] is True

    def test_auth_me_legacy_user_no_password(self):
        """Test /auth/me for legacy user without password."""
        self.users_collection.insert_one({
            'student_id': 'LEGACY001',
            'role': 'student',
            'created_at': datetime.now(timezone.utc)
        })

        login_response = self.client.post('/auth/login',
            json={'student_id': 'LEGACY001'},
            content_type='application/json'
        )
        token = json.loads(login_response.data)['token']

        response = self.client.get('/auth/me',
            headers={'Authorization': f'Bearer {token}'}
        )

        assert response.status_code == 200
        data = json.loads(response.data)
        assert data['has_password'] is False


class TestPasswordRequirements:
    """Tests for password requirements endpoint."""

    @pytest.fixture(autouse=True)
    def setup(self):
        from app import app
        self.client = app.test_client()

    def test_get_password_requirements(self):
        """Test getting password requirements."""
        response = self.client.get('/auth/password-requirements')

        assert response.status_code == 200
        data = json.loads(response.data)
        assert 'min_length' in data
        assert 'require_uppercase' in data
        assert 'require_lowercase' in data
        assert 'require_digit' in data

    def test_password_requirements_no_auth_required(self):
        """Test that password requirements doesn't need auth."""
        response = self.client.get('/auth/password-requirements')
        assert response.status_code == 200
