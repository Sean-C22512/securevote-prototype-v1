"""
SecureVote API Integration Tests
================================
Tests for the Flask API endpoints with encrypted voting.

Run with: pytest tests/test_api.py -v
"""

import pytest
import json
import os
import tempfile
import shutil
from datetime import datetime

# Set test environment before importing app
os.environ['ELECTION_ID'] = 'TEST-ELECTION-001'


class TestVotingAPI:
    """Integration tests for the voting API."""

    @pytest.fixture(autouse=True)
    def setup(self, monkeypatch):
        """Set up test environment with clean database and keys."""
        # Create temp directory for keys
        self.temp_keys_dir = tempfile.mkdtemp()

        # Import app after setting environment
        from app import app, votes_collection, users_collection
        from crypto.key_manager import KeyManager
        from crypto.ballot_crypto import BallotCrypto
        import app as app_module

        # Use temp keys directory
        km = KeyManager(keys_dir=self.temp_keys_dir)
        app_module.ballot_crypto = BallotCrypto(key_manager=km)

        self.app = app
        self.client = app.test_client()
        self.votes_collection = votes_collection
        self.users_collection = users_collection

        # Clean collections before each test
        self.votes_collection.delete_many({'election_id': 'TEST-ELECTION-001'})
        self.users_collection.delete_many({})

        yield

        # Cleanup
        self.votes_collection.delete_many({'election_id': 'TEST-ELECTION-001'})
        self.users_collection.delete_many({})
        shutil.rmtree(self.temp_keys_dir)

    def get_auth_token(self, student_id):
        """Helper to get JWT token for a student."""
        response = self.client.post('/auth/login',
            json={'student_id': student_id},
            content_type='application/json'
        )
        data = json.loads(response.data)
        return data.get('token')

    def create_user_with_role(self, student_id, role):
        """Helper to create a user with a specific role."""
        import datetime
        self.users_collection.delete_one({'student_id': student_id})
        self.users_collection.insert_one({
            'student_id': student_id,
            'role': role,
            'created_at': datetime.datetime.now(datetime.timezone.utc)
        })

    def test_login_creates_user(self):
        """Test that login creates a new user if not exists."""
        response = self.client.post('/auth/login',
            json={'student_id': 'C22512873'},
            content_type='application/json'
        )

        assert response.status_code == 200
        data = json.loads(response.data)
        assert 'token' in data

        # Verify user was created
        user = self.users_collection.find_one({'student_id': 'C22512873'})
        assert user is not None

    def test_login_requires_student_id(self):
        """Test that login requires student_id."""
        response = self.client.post('/auth/login',
            json={},
            content_type='application/json'
        )

        assert response.status_code == 400

    def test_get_candidates(self):
        """Test retrieving candidate list."""
        response = self.client.get('/candidates')

        assert response.status_code == 200
        data = json.loads(response.data)
        assert len(data) == 3
        assert data[0]['name'] == 'Candidate A'

    def test_cast_vote_success(self):
        """Test successful vote casting with encryption."""
        token = self.get_auth_token('C22512873')

        response = self.client.post('/vote',
            json={'candidate_id': 1},
            headers={'Authorization': f'Bearer {token}'},
            content_type='application/json'
        )

        assert response.status_code == 201
        data = json.loads(response.data)
        assert 'message' in data
        assert 'vote_hash' in data

        # Verify vote was stored encrypted
        vote = self.votes_collection.find_one({'student_id': 'C22512873'})
        assert vote is not None
        assert 'encrypted_ballot' in vote
        assert 'encrypted_aes_key' in vote
        assert 'current_hash' in vote
        assert 'previous_hash' in vote

    def test_cast_vote_requires_auth(self):
        """Test that voting requires authentication."""
        response = self.client.post('/vote',
            json={'candidate_id': 1},
            content_type='application/json'
        )

        assert response.status_code == 401

    def test_cast_vote_invalid_token(self):
        """Test that invalid token is rejected."""
        response = self.client.post('/vote',
            json={'candidate_id': 1},
            headers={'Authorization': 'Bearer invalid_token'},
            content_type='application/json'
        )

        assert response.status_code == 401

    def test_cast_vote_once_only(self):
        """Test that users can only vote once."""
        token = self.get_auth_token('C22512873')

        # First vote
        response1 = self.client.post('/vote',
            json={'candidate_id': 1},
            headers={'Authorization': f'Bearer {token}'},
            content_type='application/json'
        )
        assert response1.status_code == 201

        # Second vote attempt
        response2 = self.client.post('/vote',
            json={'candidate_id': 2},
            headers={'Authorization': f'Bearer {token}'},
            content_type='application/json'
        )
        assert response2.status_code == 403

    def test_cast_vote_invalid_candidate(self):
        """Test rejection of invalid candidate."""
        token = self.get_auth_token('C22512873')

        response = self.client.post('/vote',
            json={'candidate_id': 999},
            headers={'Authorization': f'Bearer {token}'},
            content_type='application/json'
        )

        assert response.status_code == 400

    def test_vote_chain_linking(self):
        """Test that votes are properly chain-linked."""
        # Cast multiple votes from different users
        students = ['C22512871', 'C22512872', 'C22512873']

        for i, student_id in enumerate(students):
            token = self.get_auth_token(student_id)
            self.client.post('/vote',
                json={'candidate_id': (i % 3) + 1},
                headers={'Authorization': f'Bearer {token}'},
                content_type='application/json'
            )

        # Fetch votes in order
        votes = list(self.votes_collection.find(
            {'election_id': 'TEST-ELECTION-001'},
            sort=[('timestamp', 1)]
        ))

        # Verify chain linking
        assert votes[0]['previous_hash'] == 'GENESIS'
        assert votes[1]['previous_hash'] == votes[0]['current_hash']
        assert votes[2]['previous_hash'] == votes[1]['current_hash']

    def test_results_with_encrypted_votes(self):
        """Test that results correctly decrypt and tally votes."""
        # Cast votes
        votes = [
            ('C22512871', 1),  # Candidate A
            ('C22512872', 1),  # Candidate A
            ('C22512873', 2),  # Candidate B
            ('C22512874', 3),  # Candidate C
            ('C22512875', 1),  # Candidate A
        ]

        for student_id, candidate_id in votes:
            token = self.get_auth_token(student_id)
            self.client.post('/vote',
                json={'candidate_id': candidate_id},
                headers={'Authorization': f'Bearer {token}'},
                content_type='application/json'
            )

        # Get results (requires official or admin role)
        self.create_user_with_role('OFFICIAL001', 'official')
        official_token = self.get_auth_token('OFFICIAL001')

        response = self.client.get('/results',
            headers={'Authorization': f'Bearer {official_token}'}
        )

        assert response.status_code == 200
        data = json.loads(response.data)

        assert data['Candidate A'] == 3
        assert data['Candidate B'] == 1
        assert data['Candidate C'] == 1

    def test_results_empty_election(self):
        """Test results for election with no votes."""
        # Requires official or admin role
        self.create_user_with_role('OFFICIAL001', 'official')
        token = self.get_auth_token('OFFICIAL001')

        response = self.client.get('/results',
            headers={'Authorization': f'Bearer {token}'}
        )

        assert response.status_code == 200
        data = json.loads(response.data)

        assert data['Candidate A'] == 0
        assert data['Candidate B'] == 0
        assert data['Candidate C'] == 0


class TestAuditAPI:
    """Tests for audit endpoints."""

    @pytest.fixture(autouse=True)
    def setup(self, monkeypatch):
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
        import datetime
        self.users_collection.delete_one({'student_id': student_id})
        self.users_collection.insert_one({
            'student_id': student_id,
            'role': role,
            'created_at': datetime.datetime.now(datetime.timezone.utc)
        })

    def get_admin_token(self):
        """Helper to get an admin token for audit endpoints."""
        self.create_user_with_role('ADMIN001', 'admin')
        return self.get_auth_token('ADMIN001')

    def test_verify_empty_chain(self):
        """Test chain verification with no votes."""
        admin_token = self.get_admin_token()

        response = self.client.get('/audit/verify',
            headers={'Authorization': f'Bearer {admin_token}'}
        )

        assert response.status_code == 200
        data = json.loads(response.data)
        assert data['valid'] is True
        assert data['total_votes'] == 0

    def test_verify_valid_chain(self):
        """Test verification of a valid vote chain."""
        # Cast several votes
        for i in range(5):
            token = self.get_auth_token(f'C2251287{i}')
            self.client.post('/vote',
                json={'candidate_id': (i % 3) + 1},
                headers={'Authorization': f'Bearer {token}'},
                content_type='application/json'
            )

        admin_token = self.get_admin_token()
        response = self.client.get('/audit/verify',
            headers={'Authorization': f'Bearer {admin_token}'}
        )

        assert response.status_code == 200
        data = json.loads(response.data)
        assert data['valid'] is True
        assert data['total_votes'] == 5

    def test_verify_detects_tampering(self):
        """Test that chain verification detects tampering."""
        # Cast votes
        for i in range(3):
            token = self.get_auth_token(f'C2251287{i}')
            self.client.post('/vote',
                json={'candidate_id': (i % 3) + 1},
                headers={'Authorization': f'Bearer {token}'},
                content_type='application/json'
            )

        # Tamper with middle vote's hash
        votes = list(self.votes_collection.find(
            {'election_id': 'TEST-ELECTION-001'},
            sort=[('timestamp', 1)]
        ))

        self.votes_collection.update_one(
            {'_id': votes[1]['_id']},
            {'$set': {'current_hash': 'TAMPERED_HASH_VALUE'}}
        )

        admin_token = self.get_admin_token()
        response = self.client.get('/audit/verify',
            headers={'Authorization': f'Bearer {admin_token}'}
        )

        assert response.status_code == 400
        data = json.loads(response.data)
        assert data['valid'] is False

    def test_audit_stats(self):
        """Test audit statistics endpoint."""
        # Create some users and votes
        for i in range(3):
            token = self.get_auth_token(f'C2251287{i}')
            self.client.post('/vote',
                json={'candidate_id': (i % 3) + 1},
                headers={'Authorization': f'Bearer {token}'},
                content_type='application/json'
            )

        admin_token = self.get_admin_token()
        response = self.client.get('/audit/stats',
            headers={'Authorization': f'Bearer {admin_token}'}
        )

        assert response.status_code == 200
        data = json.loads(response.data)
        assert data['election_id'] == 'TEST-ELECTION-001'
        assert data['total_votes'] == 3
        assert data['registered_users'] == 4  # 3 voters + 1 admin
        assert data['first_vote'] is not None
        assert data['last_vote'] is not None
