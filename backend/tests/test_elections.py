"""
SecureVote Election Management Tests
====================================
Tests for election CRUD, lifecycle, and voting with dynamic elections.

Run with: pytest tests/test_elections.py -v
"""

import pytest
import json
import os
import tempfile
import shutil
from datetime import datetime, timedelta, timezone

os.environ['ELECTION_ID'] = 'TEST-ELECTION-001'


class TestElectionCRUD:
    """Tests for election create, read, update, delete operations."""

    @pytest.fixture(autouse=True)
    def setup(self):
        """Set up test environment."""
        self.temp_keys_dir = tempfile.mkdtemp()

        from app import app, elections_collection, votes_collection, users_collection
        from crypto.key_manager import KeyManager
        from crypto.ballot_crypto import BallotCrypto
        import app as app_module

        km = KeyManager(keys_dir=self.temp_keys_dir)
        app_module.ballot_crypto = BallotCrypto(key_manager=km)

        self.app = app
        self.client = app.test_client()
        self.elections_collection = elections_collection
        self.votes_collection = votes_collection
        self.users_collection = users_collection

        # Clean up
        self.elections_collection.delete_many({})
        self.votes_collection.delete_many({})
        self.users_collection.delete_many({})

        yield

        self.elections_collection.delete_many({})
        self.votes_collection.delete_many({})
        self.users_collection.delete_many({})
        shutil.rmtree(self.temp_keys_dir)

    def create_user_with_role(self, student_id, role):
        """Helper to create a user with a specific role."""
        self.users_collection.delete_one({'student_id': student_id})
        self.users_collection.insert_one({
            'student_id': student_id,
            'role': role,
            'created_at': datetime.now(timezone.utc)
        })

    def get_token(self, student_id):
        """Helper to get JWT token."""
        response = self.client.post('/auth/login',
            json={'student_id': student_id},
            content_type='application/json'
        )
        return json.loads(response.data).get('token')

    def get_official_token(self):
        """Get token for an official user."""
        self.create_user_with_role('OFFICIAL001', 'official')
        return self.get_token('OFFICIAL001')

    def get_admin_token(self):
        """Get token for an admin user."""
        self.create_user_with_role('ADMIN001', 'admin')
        return self.get_token('ADMIN001')

    # =========================================================================
    # Create Election Tests
    # =========================================================================

    def test_create_election_success(self):
        """Test creating a new election."""
        token = self.get_official_token()

        response = self.client.post('/elections',
            json={
                'title': 'Student Union President 2025',
                'description': 'Annual SU presidential election',
                'candidates': [
                    {'name': 'Alice Smith', 'party': 'Progress Party'},
                    {'name': 'Bob Jones', 'party': 'Unity Party'}
                ]
            },
            headers={'Authorization': f'Bearer {token}'},
            content_type='application/json'
        )

        assert response.status_code == 201
        data = json.loads(response.data)
        assert 'election' in data
        assert data['election']['title'] == 'Student Union President 2025'
        assert data['election']['status'] == 'draft'
        assert len(data['election']['candidates']) == 2

    def test_create_election_requires_official_role(self):
        """Test that students cannot create elections."""
        self.create_user_with_role('STUDENT001', 'student')
        token = self.get_token('STUDENT001')

        response = self.client.post('/elections',
            json={
                'title': 'Test Election',
                'candidates': [
                    {'name': 'Candidate A'},
                    {'name': 'Candidate B'}
                ]
            },
            headers={'Authorization': f'Bearer {token}'},
            content_type='application/json'
        )

        assert response.status_code == 403

    def test_create_election_requires_minimum_candidates(self):
        """Test that election requires at least 2 candidates."""
        token = self.get_official_token()

        response = self.client.post('/elections',
            json={
                'title': 'Invalid Election',
                'candidates': [{'name': 'Only One'}]
            },
            headers={'Authorization': f'Bearer {token}'},
            content_type='application/json'
        )

        assert response.status_code == 400
        data = json.loads(response.data)
        assert 'at least 2 candidates' in str(data['details']).lower()

    def test_create_election_assigns_candidate_ids(self):
        """Test that candidate IDs are auto-assigned."""
        token = self.get_official_token()

        response = self.client.post('/elections',
            json={
                'title': 'Auto ID Election',
                'candidates': [
                    {'name': 'Candidate A'},
                    {'name': 'Candidate B'},
                    {'name': 'Candidate C'}
                ]
            },
            headers={'Authorization': f'Bearer {token}'},
            content_type='application/json'
        )

        assert response.status_code == 201
        data = json.loads(response.data)
        candidates = data['election']['candidates']
        assert candidates[0]['id'] == 1
        assert candidates[1]['id'] == 2
        assert candidates[2]['id'] == 3

    # =========================================================================
    # Read Election Tests
    # =========================================================================

    def test_list_elections(self):
        """Test listing elections."""
        token = self.get_official_token()

        # Create a few elections
        for i in range(3):
            self.client.post('/elections',
                json={
                    'title': f'Election {i+1}',
                    'candidates': [
                        {'name': 'Candidate A'},
                        {'name': 'Candidate B'}
                    ]
                },
                headers={'Authorization': f'Bearer {token}'},
                content_type='application/json'
            )

        response = self.client.get('/elections',
            headers={'Authorization': f'Bearer {token}'}
        )

        assert response.status_code == 200
        data = json.loads(response.data)
        assert data['total'] == 3

    def test_students_only_see_active_elections(self):
        """Test that students can only see active/closed elections."""
        official_token = self.get_official_token()

        # Create draft election
        self.client.post('/elections',
            json={
                'title': 'Draft Election',
                'candidates': [
                    {'name': 'Candidate A'},
                    {'name': 'Candidate B'}
                ]
            },
            headers={'Authorization': f'Bearer {official_token}'},
            content_type='application/json'
        )

        # Student should not see draft elections
        self.create_user_with_role('STUDENT001', 'student')
        student_token = self.get_token('STUDENT001')

        response = self.client.get('/elections',
            headers={'Authorization': f'Bearer {student_token}'}
        )

        assert response.status_code == 200
        data = json.loads(response.data)
        assert data['total'] == 0

    def test_get_election_by_id(self):
        """Test getting a specific election."""
        token = self.get_official_token()

        # Create election
        create_response = self.client.post('/elections',
            json={
                'title': 'Specific Election',
                'candidates': [
                    {'name': 'Candidate A'},
                    {'name': 'Candidate B'}
                ]
            },
            headers={'Authorization': f'Bearer {token}'},
            content_type='application/json'
        )
        election_id = json.loads(create_response.data)['election']['election_id']

        # Get election
        response = self.client.get(f'/elections/{election_id}',
            headers={'Authorization': f'Bearer {token}'}
        )

        assert response.status_code == 200
        data = json.loads(response.data)
        assert data['election_id'] == election_id

    # =========================================================================
    # Update Election Tests
    # =========================================================================

    def test_update_draft_election(self):
        """Test updating a draft election."""
        token = self.get_official_token()

        # Create election
        create_response = self.client.post('/elections',
            json={
                'title': 'Original Title',
                'candidates': [
                    {'name': 'Candidate A'},
                    {'name': 'Candidate B'}
                ]
            },
            headers={'Authorization': f'Bearer {token}'},
            content_type='application/json'
        )
        election_id = json.loads(create_response.data)['election']['election_id']

        # Update election
        response = self.client.put(f'/elections/{election_id}',
            json={'title': 'Updated Title', 'description': 'New description'},
            headers={'Authorization': f'Bearer {token}'},
            content_type='application/json'
        )

        assert response.status_code == 200
        data = json.loads(response.data)
        assert data['election']['title'] == 'Updated Title'

    def test_cannot_update_closed_election(self):
        """Test that closed elections cannot be updated."""
        token = self.get_official_token()

        # Create and start and end election
        create_response = self.client.post('/elections',
            json={
                'title': 'Closed Election',
                'candidates': [
                    {'name': 'Candidate A'},
                    {'name': 'Candidate B'}
                ]
            },
            headers={'Authorization': f'Bearer {token}'},
            content_type='application/json'
        )
        election_id = json.loads(create_response.data)['election']['election_id']

        self.client.post(f'/elections/{election_id}/start',
            headers={'Authorization': f'Bearer {token}'}
        )
        self.client.post(f'/elections/{election_id}/end',
            headers={'Authorization': f'Bearer {token}'}
        )

        # Try to update
        response = self.client.put(f'/elections/{election_id}',
            json={'title': 'New Title'},
            headers={'Authorization': f'Bearer {token}'},
            content_type='application/json'
        )

        assert response.status_code == 400

    # =========================================================================
    # Delete Election Tests
    # =========================================================================

    def test_delete_draft_election(self):
        """Test deleting a draft election."""
        token = self.get_admin_token()

        # Create election
        create_response = self.client.post('/elections',
            json={
                'title': 'To Delete',
                'candidates': [
                    {'name': 'Candidate A'},
                    {'name': 'Candidate B'}
                ]
            },
            headers={'Authorization': f'Bearer {token}'},
            content_type='application/json'
        )
        election_id = json.loads(create_response.data)['election']['election_id']

        # Delete
        response = self.client.delete(f'/elections/{election_id}',
            headers={'Authorization': f'Bearer {token}'}
        )

        assert response.status_code == 200

        # Verify deleted
        get_response = self.client.get(f'/elections/{election_id}',
            headers={'Authorization': f'Bearer {token}'}
        )
        assert get_response.status_code == 404

    def test_cannot_delete_active_election(self):
        """Test that active elections cannot be deleted."""
        token = self.get_admin_token()

        # Create and start election
        create_response = self.client.post('/elections',
            json={
                'title': 'Active Election',
                'candidates': [
                    {'name': 'Candidate A'},
                    {'name': 'Candidate B'}
                ]
            },
            headers={'Authorization': f'Bearer {token}'},
            content_type='application/json'
        )
        election_id = json.loads(create_response.data)['election']['election_id']

        self.client.post(f'/elections/{election_id}/start',
            headers={'Authorization': f'Bearer {token}'}
        )

        # Try to delete
        response = self.client.delete(f'/elections/{election_id}',
            headers={'Authorization': f'Bearer {token}'}
        )

        assert response.status_code == 400


class TestElectionLifecycle:
    """Tests for election lifecycle (start, end, etc.)."""

    @pytest.fixture(autouse=True)
    def setup(self):
        """Set up test environment."""
        self.temp_keys_dir = tempfile.mkdtemp()

        from app import app, elections_collection, votes_collection, users_collection
        from crypto.key_manager import KeyManager
        from crypto.ballot_crypto import BallotCrypto
        import app as app_module

        km = KeyManager(keys_dir=self.temp_keys_dir)
        app_module.ballot_crypto = BallotCrypto(key_manager=km)

        self.app = app
        self.client = app.test_client()
        self.elections_collection = elections_collection
        self.votes_collection = votes_collection
        self.users_collection = users_collection

        self.elections_collection.delete_many({})
        self.votes_collection.delete_many({})
        self.users_collection.delete_many({})

        yield

        self.elections_collection.delete_many({})
        self.votes_collection.delete_many({})
        self.users_collection.delete_many({})
        shutil.rmtree(self.temp_keys_dir)

    def create_user_with_role(self, student_id, role):
        self.users_collection.delete_one({'student_id': student_id})
        self.users_collection.insert_one({
            'student_id': student_id,
            'role': role,
            'created_at': datetime.now(timezone.utc)
        })

    def get_token(self, student_id):
        response = self.client.post('/auth/login',
            json={'student_id': student_id},
            content_type='application/json'
        )
        return json.loads(response.data).get('token')

    def get_official_token(self):
        self.create_user_with_role('OFFICIAL001', 'official')
        return self.get_token('OFFICIAL001')

    def create_election(self, token, title='Test Election'):
        """Helper to create a draft election."""
        response = self.client.post('/elections',
            json={
                'title': title,
                'candidates': [
                    {'name': 'Candidate A'},
                    {'name': 'Candidate B'}
                ]
            },
            headers={'Authorization': f'Bearer {token}'},
            content_type='application/json'
        )
        return json.loads(response.data)['election']['election_id']

    def test_start_election(self):
        """Test starting an election."""
        token = self.get_official_token()
        election_id = self.create_election(token)

        response = self.client.post(f'/elections/{election_id}/start',
            headers={'Authorization': f'Bearer {token}'}
        )

        assert response.status_code == 200
        data = json.loads(response.data)
        assert data['election']['status'] == 'active'
        assert data['election']['started_at'] is not None

    def test_end_election(self):
        """Test ending an election."""
        token = self.get_official_token()
        election_id = self.create_election(token)

        # Start election
        self.client.post(f'/elections/{election_id}/start',
            headers={'Authorization': f'Bearer {token}'}
        )

        # End election
        response = self.client.post(f'/elections/{election_id}/end',
            headers={'Authorization': f'Bearer {token}'}
        )

        assert response.status_code == 200
        data = json.loads(response.data)
        assert data['election']['status'] == 'closed'
        assert data['election']['ended_at'] is not None

    def test_cannot_start_already_active(self):
        """Test that active elections cannot be started again."""
        token = self.get_official_token()
        election_id = self.create_election(token)

        self.client.post(f'/elections/{election_id}/start',
            headers={'Authorization': f'Bearer {token}'}
        )

        response = self.client.post(f'/elections/{election_id}/start',
            headers={'Authorization': f'Bearer {token}'}
        )

        assert response.status_code == 400

    def test_cannot_end_draft_election(self):
        """Test that draft elections cannot be ended directly."""
        token = self.get_official_token()
        election_id = self.create_election(token)

        response = self.client.post(f'/elections/{election_id}/end',
            headers={'Authorization': f'Bearer {token}'}
        )

        assert response.status_code == 400


class TestVotingWithElections:
    """Tests for voting in dynamic elections."""

    @pytest.fixture(autouse=True)
    def setup(self):
        """Set up test environment."""
        self.temp_keys_dir = tempfile.mkdtemp()

        from app import app, elections_collection, votes_collection, users_collection
        from crypto.key_manager import KeyManager
        from crypto.ballot_crypto import BallotCrypto
        import app as app_module

        km = KeyManager(keys_dir=self.temp_keys_dir)
        app_module.ballot_crypto = BallotCrypto(key_manager=km)

        self.app = app
        self.client = app.test_client()
        self.elections_collection = elections_collection
        self.votes_collection = votes_collection
        self.users_collection = users_collection

        self.elections_collection.delete_many({})
        self.votes_collection.delete_many({})
        self.users_collection.delete_many({})

        yield

        self.elections_collection.delete_many({})
        self.votes_collection.delete_many({})
        self.users_collection.delete_many({})
        shutil.rmtree(self.temp_keys_dir)

    def create_user_with_role(self, student_id, role):
        self.users_collection.delete_one({'student_id': student_id})
        self.users_collection.insert_one({
            'student_id': student_id,
            'role': role,
            'created_at': datetime.now(timezone.utc)
        })

    def get_token(self, student_id):
        response = self.client.post('/auth/login',
            json={'student_id': student_id},
            content_type='application/json'
        )
        return json.loads(response.data).get('token')

    def create_and_start_election(self, title='Test Election'):
        """Helper to create and start an election."""
        self.create_user_with_role('OFFICIAL001', 'official')
        official_token = self.get_token('OFFICIAL001')

        create_response = self.client.post('/elections',
            json={
                'title': title,
                'candidates': [
                    {'name': 'Candidate A'},
                    {'name': 'Candidate B'},
                    {'name': 'Candidate C'}
                ]
            },
            headers={'Authorization': f'Bearer {official_token}'},
            content_type='application/json'
        )
        election_id = json.loads(create_response.data)['election']['election_id']

        self.client.post(f'/elections/{election_id}/start',
            headers={'Authorization': f'Bearer {official_token}'}
        )

        return election_id

    def test_vote_in_active_election(self):
        """Test voting in an active election."""
        election_id = self.create_and_start_election()

        # Vote as student
        student_token = self.get_token('STUDENT001')

        response = self.client.post('/vote',
            json={'election_id': election_id, 'candidate_id': 1},
            headers={'Authorization': f'Bearer {student_token}'},
            content_type='application/json'
        )

        assert response.status_code == 201
        data = json.loads(response.data)
        assert data['election_id'] == election_id

    def test_cannot_vote_in_draft_election(self):
        """Test that voting in draft elections is not allowed."""
        self.create_user_with_role('OFFICIAL001', 'official')
        official_token = self.get_token('OFFICIAL001')

        # Create but don't start
        create_response = self.client.post('/elections',
            json={
                'title': 'Draft Election',
                'candidates': [
                    {'name': 'Candidate A'},
                    {'name': 'Candidate B'}
                ]
            },
            headers={'Authorization': f'Bearer {official_token}'},
            content_type='application/json'
        )
        election_id = json.loads(create_response.data)['election']['election_id']

        # Try to vote
        student_token = self.get_token('STUDENT001')
        response = self.client.post('/vote',
            json={'election_id': election_id, 'candidate_id': 1},
            headers={'Authorization': f'Bearer {student_token}'},
            content_type='application/json'
        )

        assert response.status_code == 400
        assert 'not started' in json.loads(response.data)['error'].lower()

    def test_cannot_vote_in_closed_election(self):
        """Test that voting in closed elections is not allowed."""
        election_id = self.create_and_start_election()

        # End election
        self.create_user_with_role('OFFICIAL001', 'official')
        official_token = self.get_token('OFFICIAL001')
        self.client.post(f'/elections/{election_id}/end',
            headers={'Authorization': f'Bearer {official_token}'}
        )

        # Try to vote
        student_token = self.get_token('STUDENT002')
        response = self.client.post('/vote',
            json={'election_id': election_id, 'candidate_id': 1},
            headers={'Authorization': f'Bearer {student_token}'},
            content_type='application/json'
        )

        assert response.status_code == 400
        assert 'ended' in json.loads(response.data)['error'].lower()

    def test_cannot_vote_twice_in_same_election(self):
        """Test that users can only vote once per election."""
        election_id = self.create_and_start_election()

        student_token = self.get_token('STUDENT001')

        # First vote
        self.client.post('/vote',
            json={'election_id': election_id, 'candidate_id': 1},
            headers={'Authorization': f'Bearer {student_token}'},
            content_type='application/json'
        )

        # Second vote attempt
        response = self.client.post('/vote',
            json={'election_id': election_id, 'candidate_id': 2},
            headers={'Authorization': f'Bearer {student_token}'},
            content_type='application/json'
        )

        assert response.status_code == 403
        assert 'already voted' in json.loads(response.data)['error'].lower()

    def test_can_vote_in_multiple_elections(self):
        """Test that users can vote in different elections."""
        election1_id = self.create_and_start_election('Election 1')
        election2_id = self.create_and_start_election('Election 2')

        student_token = self.get_token('STUDENT001')

        # Vote in first election
        response1 = self.client.post('/vote',
            json={'election_id': election1_id, 'candidate_id': 1},
            headers={'Authorization': f'Bearer {student_token}'},
            content_type='application/json'
        )
        assert response1.status_code == 201

        # Vote in second election
        response2 = self.client.post('/vote',
            json={'election_id': election2_id, 'candidate_id': 2},
            headers={'Authorization': f'Bearer {student_token}'},
            content_type='application/json'
        )
        assert response2.status_code == 201

    def test_invalid_candidate_for_election(self):
        """Test that invalid candidate IDs are rejected."""
        election_id = self.create_and_start_election()

        student_token = self.get_token('STUDENT001')

        response = self.client.post('/vote',
            json={'election_id': election_id, 'candidate_id': 999},
            headers={'Authorization': f'Bearer {student_token}'},
            content_type='application/json'
        )

        assert response.status_code == 400
        assert 'invalid candidate' in json.loads(response.data)['error'].lower()


class TestElectionResults:
    """Tests for election results."""

    @pytest.fixture(autouse=True)
    def setup(self):
        """Set up test environment."""
        self.temp_keys_dir = tempfile.mkdtemp()

        from app import app, elections_collection, votes_collection, users_collection
        from crypto.key_manager import KeyManager
        from crypto.ballot_crypto import BallotCrypto
        from routes.elections import init_elections_routes
        import app as app_module

        km = KeyManager(keys_dir=self.temp_keys_dir)
        test_crypto = BallotCrypto(key_manager=km)
        app_module.ballot_crypto = test_crypto
        # Reinitialize elections routes with test crypto
        init_elections_routes(elections_collection, votes_collection, test_crypto)

        self.app = app
        self.client = app.test_client()
        self.elections_collection = elections_collection
        self.votes_collection = votes_collection
        self.users_collection = users_collection

        self.elections_collection.delete_many({})
        self.votes_collection.delete_many({})
        self.users_collection.delete_many({})

        yield

        self.elections_collection.delete_many({})
        self.votes_collection.delete_many({})
        self.users_collection.delete_many({})
        shutil.rmtree(self.temp_keys_dir)

    def create_user_with_role(self, student_id, role):
        self.users_collection.delete_one({'student_id': student_id})
        self.users_collection.insert_one({
            'student_id': student_id,
            'role': role,
            'created_at': datetime.now(timezone.utc)
        })

    def get_token(self, student_id):
        response = self.client.post('/auth/login',
            json={'student_id': student_id},
            content_type='application/json'
        )
        return json.loads(response.data).get('token')

    def test_get_election_results(self):
        """Test getting results for a closed election."""
        # Create and start election
        self.create_user_with_role('OFFICIAL001', 'official')
        official_token = self.get_token('OFFICIAL001')

        create_response = self.client.post('/elections',
            json={
                'title': 'Results Test Election',
                'candidates': [
                    {'name': 'Alice'},
                    {'name': 'Bob'},
                    {'name': 'Charlie'}
                ]
            },
            headers={'Authorization': f'Bearer {official_token}'},
            content_type='application/json'
        )
        election_id = json.loads(create_response.data)['election']['election_id']

        self.client.post(f'/elections/{election_id}/start',
            headers={'Authorization': f'Bearer {official_token}'}
        )

        # Cast some votes
        votes = [
            ('STUDENT001', 1),  # Alice
            ('STUDENT002', 1),  # Alice
            ('STUDENT003', 2),  # Bob
            ('STUDENT004', 1),  # Alice
            ('STUDENT005', 3),  # Charlie
        ]

        for student_id, candidate_id in votes:
            token = self.get_token(student_id)
            self.client.post('/vote',
                json={'election_id': election_id, 'candidate_id': candidate_id},
                headers={'Authorization': f'Bearer {token}'},
                content_type='application/json'
            )

        # End election
        self.client.post(f'/elections/{election_id}/end',
            headers={'Authorization': f'Bearer {official_token}'}
        )

        # Get results
        response = self.client.get(f'/elections/{election_id}/results',
            headers={'Authorization': f'Bearer {official_token}'}
        )

        assert response.status_code == 200
        data = json.loads(response.data)
        assert data['total_votes'] == 5
        assert data['tally']['Alice'] == 3
        assert data['tally']['Bob'] == 1
        assert data['tally']['Charlie'] == 1

    def test_officials_cannot_see_active_results(self):
        """Test that officials cannot see results while voting is active."""
        self.create_user_with_role('OFFICIAL001', 'official')
        official_token = self.get_token('OFFICIAL001')

        create_response = self.client.post('/elections',
            json={
                'title': 'Active Election',
                'candidates': [
                    {'name': 'Candidate A'},
                    {'name': 'Candidate B'}
                ]
            },
            headers={'Authorization': f'Bearer {official_token}'},
            content_type='application/json'
        )
        election_id = json.loads(create_response.data)['election']['election_id']

        self.client.post(f'/elections/{election_id}/start',
            headers={'Authorization': f'Bearer {official_token}'}
        )

        # Try to get results
        response = self.client.get(f'/elections/{election_id}/results',
            headers={'Authorization': f'Bearer {official_token}'}
        )

        assert response.status_code == 400
        assert 'not available' in json.loads(response.data)['error'].lower()

    def test_admins_can_see_active_results(self):
        """Test that admins can see results even while voting is active."""
        self.create_user_with_role('ADMIN001', 'admin')
        admin_token = self.get_token('ADMIN001')

        create_response = self.client.post('/elections',
            json={
                'title': 'Admin View Election',
                'candidates': [
                    {'name': 'Candidate A'},
                    {'name': 'Candidate B'}
                ]
            },
            headers={'Authorization': f'Bearer {admin_token}'},
            content_type='application/json'
        )
        election_id = json.loads(create_response.data)['election']['election_id']

        self.client.post(f'/elections/{election_id}/start',
            headers={'Authorization': f'Bearer {admin_token}'}
        )

        # Admin can see results
        response = self.client.get(f'/elections/{election_id}/results',
            headers={'Authorization': f'Bearer {admin_token}'}
        )

        assert response.status_code == 200
