"""
SecureVote End-to-End Integration Test
=======================================
Full lifecycle test: admin creates users -> official creates/starts election
-> students vote -> official ends election -> results verified -> chain audited.

Run with: pytest tests/test_e2e_workflow.py -v
"""

import pytest
import json
import os
import tempfile
import shutil
import datetime

os.environ['ELECTION_ID'] = 'TEST-ELECTION-001'


class TestE2EWorkflow:
    """Full end-to-end lifecycle integration test."""

    @pytest.fixture(autouse=True)
    def setup(self):
        """Set up test environment with clean database."""
        self.temp_keys_dir = tempfile.mkdtemp()

        from app import app, votes_collection, users_collection, elections_collection
        from crypto.key_manager import KeyManager
        from crypto.ballot_crypto import BallotCrypto
        import app as app_module
        import routes.elections as elections_module

        km = KeyManager(keys_dir=self.temp_keys_dir)
        crypto = BallotCrypto(key_manager=km)
        app_module.ballot_crypto = crypto
        elections_module.ballot_crypto = crypto

        self.app = app
        self.client = app.test_client()
        self.votes_collection = votes_collection
        self.users_collection = users_collection
        self.elections_collection = elections_collection

        # Disable rate limiting for tests
        app_module.limiter.enabled = False

        # Clean up
        self.users_collection.delete_many({})
        self.elections_collection.delete_many({})
        self.votes_collection.delete_many({})

        yield

        self.users_collection.delete_many({})
        self.elections_collection.delete_many({})
        self.votes_collection.delete_many({})
        shutil.rmtree(self.temp_keys_dir)

    def create_user_with_role(self, student_id, role):
        self.users_collection.delete_one({'student_id': student_id})
        self.users_collection.insert_one({
            'student_id': student_id,
            'role': role,
            'created_at': datetime.datetime.now(datetime.timezone.utc)
        })

    def get_auth_token(self, student_id):
        response = self.client.post('/auth/login',
            json={'student_id': student_id},
            content_type='application/json'
        )
        return json.loads(response.data).get('token')

    def test_full_election_lifecycle(self):
        """
        Full lifecycle:
        1. Admin creates users (official + students)
        2. Official creates election with candidates
        3. Official starts the election
        4. Students cast votes
        5. Official ends the election
        6. Admin views results
        7. Admin verifies chain integrity
        8. Admin checks audit stats
        """
        # =====================================================================
        # Step 1: Admin creates users
        # =====================================================================
        self.create_user_with_role('ADMIN001', 'admin')
        admin_token = self.get_auth_token('ADMIN001')

        # Admin creates an official
        resp = self.client.post('/admin/users',
            json={'student_id': 'OFFICIAL001', 'role': 'official'},
            headers={'Authorization': f'Bearer {admin_token}'},
            content_type='application/json'
        )
        assert resp.status_code == 201

        # Admin creates students
        for i in range(1, 6):
            resp = self.client.post('/admin/users',
                json={'student_id': f'STUDENT00{i}', 'role': 'student'},
                headers={'Authorization': f'Bearer {admin_token}'},
                content_type='application/json'
            )
            assert resp.status_code == 201

        # =====================================================================
        # Step 2: Official creates election
        # =====================================================================
        official_token = self.get_auth_token('OFFICIAL001')

        resp = self.client.post('/elections',
            json={
                'title': 'E2E Test Election 2025',
                'description': 'End-to-end test election',
                'candidates': [
                    {'name': 'Alice Johnson', 'party': 'Innovation Party'},
                    {'name': 'Bob Smith', 'party': 'Progress Party'},
                    {'name': 'Carol Davis', 'party': 'Unity Party'}
                ]
            },
            headers={'Authorization': f'Bearer {official_token}'},
            content_type='application/json'
        )
        assert resp.status_code == 201
        election_data = json.loads(resp.data)
        election_id = election_data['election']['election_id']
        assert election_data['election']['status'] == 'draft'

        # Verify election has 3 candidates
        candidates = election_data['election']['candidates']
        assert len(candidates) == 3

        # =====================================================================
        # Step 3: Official starts election
        # =====================================================================
        resp = self.client.post(f'/elections/{election_id}/start',
            headers={'Authorization': f'Bearer {official_token}'}
        )
        assert resp.status_code == 200
        start_data = json.loads(resp.data)
        assert start_data['election']['status'] == 'active'

        # =====================================================================
        # Step 4: Students vote
        # =====================================================================
        vote_map = {
            'STUDENT001': candidates[0]['id'],  # Alice
            'STUDENT002': candidates[0]['id'],  # Alice
            'STUDENT003': candidates[1]['id'],  # Bob
            'STUDENT004': candidates[2]['id'],  # Carol
            'STUDENT005': candidates[0]['id'],  # Alice
        }

        for student_id, candidate_id in vote_map.items():
            student_token = self.get_auth_token(student_id)
            resp = self.client.post('/vote',
                json={'candidate_id': candidate_id, 'election_id': election_id},
                headers={'Authorization': f'Bearer {student_token}'},
                content_type='application/json'
            )
            assert resp.status_code == 201, f"Vote failed for {student_id}: {resp.data}"
            vote_result = json.loads(resp.data)
            assert 'vote_hash' in vote_result

        # Verify duplicate vote is rejected
        dup_token = self.get_auth_token('STUDENT001')
        resp = self.client.post('/vote',
            json={'candidate_id': candidates[1]['id'], 'election_id': election_id},
            headers={'Authorization': f'Bearer {dup_token}'},
            content_type='application/json'
        )
        assert resp.status_code == 403

        # =====================================================================
        # Step 5: Official ends election
        # =====================================================================
        resp = self.client.post(f'/elections/{election_id}/end',
            headers={'Authorization': f'Bearer {official_token}'}
        )
        assert resp.status_code == 200
        end_data = json.loads(resp.data)
        assert end_data['election']['status'] == 'closed'
        assert end_data['total_votes'] == 5

        # =====================================================================
        # Step 6: View results
        # =====================================================================
        resp = self.client.get(f'/elections/{election_id}/results',
            headers={'Authorization': f'Bearer {admin_token}'}
        )
        assert resp.status_code == 200
        results = json.loads(resp.data)
        assert results['total_votes'] == 5
        assert results['tally']['Alice Johnson'] == 3
        assert results['tally']['Bob Smith'] == 1
        assert results['tally']['Carol Davis'] == 1

        # =====================================================================
        # Step 7: Admin verifies chain integrity
        # =====================================================================
        resp = self.client.get('/audit/verify',
            query_string={'election_id': election_id},
            headers={'Authorization': f'Bearer {admin_token}'}
        )
        assert resp.status_code == 200
        verify_data = json.loads(resp.data)
        assert verify_data['valid'] is True
        assert verify_data['total_votes'] == 5

        # =====================================================================
        # Step 8: Admin checks audit stats
        # =====================================================================
        resp = self.client.get('/audit/stats',
            query_string={'election_id': election_id},
            headers={'Authorization': f'Bearer {admin_token}'}
        )
        assert resp.status_code == 200
        stats = json.loads(resp.data)
        assert stats['total_votes'] == 5
        assert stats['chain_length'] == 5
        assert stats['unique_voters'] == 5
        assert stats['chain_valid'] is True

    def test_election_draft_cannot_receive_votes(self):
        """Test that votes cannot be cast on a draft election."""
        self.create_user_with_role('OFFICIAL001', 'official')
        official_token = self.get_auth_token('OFFICIAL001')

        # Create election (stays in draft)
        resp = self.client.post('/elections',
            json={
                'title': 'Draft Test Election 2025',
                'candidates': [
                    {'name': 'Candidate X'},
                    {'name': 'Candidate Y'}
                ]
            },
            headers={'Authorization': f'Bearer {official_token}'},
            content_type='application/json'
        )
        assert resp.status_code == 201
        election_id = json.loads(resp.data)['election']['election_id']

        # Student tries to vote on draft election
        token = self.get_auth_token('STUDENT001')
        resp = self.client.post('/vote',
            json={'candidate_id': 1, 'election_id': election_id},
            headers={'Authorization': f'Bearer {token}'},
            content_type='application/json'
        )
        assert resp.status_code == 400

    def test_closed_election_rejects_votes(self):
        """Test that votes cannot be cast after election ends."""
        self.create_user_with_role('OFFICIAL001', 'official')
        official_token = self.get_auth_token('OFFICIAL001')

        # Create and start election
        resp = self.client.post('/elections',
            json={
                'title': 'Closed Test Election 2025',
                'candidates': [
                    {'name': 'Candidate A'},
                    {'name': 'Candidate B'}
                ]
            },
            headers={'Authorization': f'Bearer {official_token}'},
            content_type='application/json'
        )
        election_id = json.loads(resp.data)['election']['election_id']

        self.client.post(f'/elections/{election_id}/start',
            headers={'Authorization': f'Bearer {official_token}'}
        )
        self.client.post(f'/elections/{election_id}/end',
            headers={'Authorization': f'Bearer {official_token}'}
        )

        # Student tries to vote on closed election
        token = self.get_auth_token('STUDENT001')
        resp = self.client.post('/vote',
            json={'candidate_id': 1, 'election_id': election_id},
            headers={'Authorization': f'Bearer {token}'},
            content_type='application/json'
        )
        assert resp.status_code == 400

    def test_user_role_management(self):
        """Test admin can create and update user roles."""
        self.create_user_with_role('ADMIN001', 'admin')
        admin_token = self.get_auth_token('ADMIN001')

        # Create student
        resp = self.client.post('/admin/users',
            json={'student_id': 'PROMOTE_ME', 'role': 'student'},
            headers={'Authorization': f'Bearer {admin_token}'},
            content_type='application/json'
        )
        assert resp.status_code == 201

        # Promote to official
        resp = self.client.put('/admin/users/PROMOTE_ME/role',
            json={'role': 'official'},
            headers={'Authorization': f'Bearer {admin_token}'},
            content_type='application/json'
        )
        assert resp.status_code == 200
        assert json.loads(resp.data)['new_role'] == 'official'

        # Verify they can now create elections
        promoted_token = self.get_auth_token('PROMOTE_ME')
        resp = self.client.post('/elections',
            json={
                'title': 'Promoted User Election Test',
                'candidates': [
                    {'name': 'Test Candidate A'},
                    {'name': 'Test Candidate B'}
                ]
            },
            headers={'Authorization': f'Bearer {promoted_token}'},
            content_type='application/json'
        )
        assert resp.status_code == 201
