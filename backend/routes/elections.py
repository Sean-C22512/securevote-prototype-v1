"""
SecureVote Election Routes
==========================
API endpoints for election management.

Endpoints:
- GET    /elections              List all elections
- POST   /elections              Create new election (official/admin)
- GET    /elections/<id>         Get election details
- PUT    /elections/<id>         Update election (official/admin)
- DELETE /elections/<id>         Delete draft election (admin)
- POST   /elections/<id>/start   Start voting (official/admin)
- POST   /elections/<id>/end     End voting (official/admin)
- GET    /elections/<id>/results Get election results (official/admin)
"""

from flask import Blueprint, request, jsonify
from datetime import datetime, timezone

from utils.auth import require_role, require_auth, get_current_user
from models.election import (
    validate_election_data,
    prepare_election_document,
    format_election_response,
    can_transition_status,
    ELECTION_STATUSES
)

elections_bp = Blueprint('elections', __name__, url_prefix='/elections')

# Will be set when blueprint is registered
elections_collection = None
votes_collection = None
ballot_crypto = None


def init_elections_routes(elections_col, votes_col, crypto):
    """Initialize route dependencies."""
    global elections_collection, votes_collection, ballot_crypto
    elections_collection = elections_col
    votes_collection = votes_col
    ballot_crypto = crypto


@elections_bp.route('', methods=['GET'])
@require_auth
def list_elections():
    """
    List all elections.

    Query params:
    - status: Filter by status (draft, active, closed, archived)
    - limit: Number of results (default 50)
    - skip: Pagination offset (default 0)
    """
    user = get_current_user()
    user_role = user.get('role', 'student')

    # Parse query params
    status_filter = request.args.get('status')
    limit = min(int(request.args.get('limit', 50)), 100)
    skip = int(request.args.get('skip', 0))

    # Build query
    query = {}
    if status_filter:
        if status_filter not in ELECTION_STATUSES:
            return jsonify({'error': f'Invalid status. Must be one of: {ELECTION_STATUSES}'}), 400
        query['status'] = status_filter

    # Students can only see active/closed elections
    if user_role == 'student':
        query['status'] = {'$in': ['active', 'closed']}

    # Fetch elections
    elections = list(elections_collection.find(query)
                     .sort('created_at', -1)
                     .skip(skip)
                     .limit(limit))

    # Filter by programme eligibility for students
    if user_role == 'student':
        student_code = (user.get('programme') or {}).get('code')
        def is_eligible(election):
            eligible = election.get('eligible_programmes', [])
            if not eligible:
                return True  # open to all
            return student_code in [p['code'] for p in eligible]
        elections = [e for e in elections if is_eligible(e)]

    total = len(elections)

    return jsonify({
        'elections': [format_election_response(e) for e in elections],
        'total': total,
        'limit': limit,
        'skip': skip
    })


@elections_bp.route('', methods=['POST'])
@require_role(['official', 'admin'])
def create_election():
    """
    Create a new election.

    Body:
    {
        "title": "Student Union President 2025",
        "description": "Annual election for SU President",
        "candidates": [
            {"name": "Candidate A", "party": "Party Alpha"},
            {"name": "Candidate B", "party": "Party Beta"}
        ],
        "start_time": "2025-03-01T09:00:00Z",  // Optional
        "end_time": "2025-03-01T18:00:00Z"     // Optional
    }
    """
    data = request.get_json()
    user = get_current_user()

    # Validate
    is_valid, errors = validate_election_data(data)
    if not is_valid:
        return jsonify({'error': 'Validation failed', 'details': errors}), 400

    # Prepare document
    election_doc = prepare_election_document(data, user['student_id'])

    # Check for duplicate title
    existing = elections_collection.find_one({
        'title': election_doc['title'],
        'status': {'$ne': 'archived'}
    })
    if existing:
        return jsonify({'error': 'An election with this title already exists'}), 409

    # Insert
    result = elections_collection.insert_one(election_doc)
    election_doc['_id'] = result.inserted_id

    return jsonify({
        'message': 'Election created successfully',
        'election': format_election_response(election_doc)
    }), 201


@elections_bp.route('/<election_id>', methods=['GET'])
@require_auth
def get_election(election_id):
    """Get election details by election_id."""
    user = get_current_user()
    user_role = user.get('role', 'student')

    election = elections_collection.find_one({'election_id': election_id})
    if not election:
        return jsonify({'error': 'Election not found'}), 404

    # Students can only see active/closed elections
    if user_role == 'student' and election['status'] not in ['active', 'closed']:
        return jsonify({'error': 'Election not found'}), 404

    # Add vote count for officials/admins
    response = format_election_response(election)
    if user_role in ['official', 'admin']:
        vote_count = votes_collection.count_documents({'election_id': election_id})
        response['vote_count'] = vote_count

    return jsonify(response)


@elections_bp.route('/<election_id>', methods=['PUT'])
@require_role(['official', 'admin'])
def update_election(election_id):
    """
    Update election details.
    Only draft elections can be fully updated.
    Active elections can only update end_time.
    """
    data = request.get_json()

    election = elections_collection.find_one({'election_id': election_id})
    if not election:
        return jsonify({'error': 'Election not found'}), 404

    # Validate update data
    is_valid, errors = validate_election_data(data, is_update=True)
    if not is_valid:
        return jsonify({'error': 'Validation failed', 'details': errors}), 400

    # Determine what can be updated based on status
    status = election['status']
    update_fields = {}

    if status == 'draft':
        # Can update everything except election_id and created_*
        allowed = ['title', 'description', 'candidates', 'start_time', 'end_time', 'settings']
        for field in allowed:
            if field in data:
                value = data[field]
                # Parse datetime strings
                if field in ['start_time', 'end_time'] and isinstance(value, str):
                    value = datetime.fromisoformat(value.replace('Z', '+00:00'))
                update_fields[field] = value

    elif status == 'active':
        # Can only extend end_time
        if 'end_time' in data:
            new_end = data['end_time']
            if isinstance(new_end, str):
                new_end = datetime.fromisoformat(new_end.replace('Z', '+00:00'))
            if new_end <= election.get('end_time', datetime.now(timezone.utc)):
                return jsonify({'error': 'Can only extend end_time for active elections'}), 400
            update_fields['end_time'] = new_end
        else:
            return jsonify({'error': 'Active elections can only have end_time extended'}), 400

    elif status in ['closed', 'archived']:
        return jsonify({'error': f'Cannot update {status} elections'}), 400

    if not update_fields:
        return jsonify({'error': 'No valid fields to update'}), 400

    # Perform update
    elections_collection.update_one(
        {'election_id': election_id},
        {'$set': update_fields}
    )

    updated = elections_collection.find_one({'election_id': election_id})
    return jsonify({
        'message': 'Election updated successfully',
        'election': format_election_response(updated)
    })


@elections_bp.route('/<election_id>', methods=['DELETE'])
@require_role('admin')
def delete_election(election_id):
    """
    Delete an election.
    Only draft elections with no votes can be deleted.
    """
    election = elections_collection.find_one({'election_id': election_id})
    if not election:
        return jsonify({'error': 'Election not found'}), 404

    if election['status'] != 'draft':
        return jsonify({'error': 'Only draft elections can be deleted'}), 400

    # Check for votes
    vote_count = votes_collection.count_documents({'election_id': election_id})
    if vote_count > 0:
        return jsonify({'error': 'Cannot delete election with existing votes'}), 400

    elections_collection.delete_one({'election_id': election_id})

    return jsonify({'message': 'Election deleted successfully'})


@elections_bp.route('/<election_id>/start', methods=['POST'])
@require_role(['official', 'admin'])
def start_election(election_id):
    """
    Start an election (transition from draft to active).
    This opens voting.
    """
    election = elections_collection.find_one({'election_id': election_id})
    if not election:
        return jsonify({'error': 'Election not found'}), 404

    # Check transition is allowed
    can_transition, error = can_transition_status(election['status'], 'active')
    if not can_transition:
        return jsonify({'error': error}), 400

    # Validate election is ready
    if len(election.get('candidates', [])) < 2:
        return jsonify({'error': 'Election must have at least 2 candidates'}), 400

    now = datetime.now(timezone.utc)

    # Update status
    elections_collection.update_one(
        {'election_id': election_id},
        {
            '$set': {
                'status': 'active',
                'started_at': now
            }
        }
    )

    updated = elections_collection.find_one({'election_id': election_id})
    return jsonify({
        'message': 'Election started successfully. Voting is now open.',
        'election': format_election_response(updated)
    })


@elections_bp.route('/<election_id>/end', methods=['POST'])
@require_role(['official', 'admin'])
def end_election(election_id):
    """
    End an election (transition from active to closed).
    This closes voting and makes results available.
    """
    election = elections_collection.find_one({'election_id': election_id})
    if not election:
        return jsonify({'error': 'Election not found'}), 404

    # Check transition is allowed
    can_transition, error = can_transition_status(election['status'], 'closed')
    if not can_transition:
        return jsonify({'error': error}), 400

    now = datetime.now(timezone.utc)

    # Update status
    elections_collection.update_one(
        {'election_id': election_id},
        {
            '$set': {
                'status': 'closed',
                'ended_at': now
            }
        }
    )

    # Get vote count
    vote_count = votes_collection.count_documents({'election_id': election_id})

    updated = elections_collection.find_one({'election_id': election_id})
    return jsonify({
        'message': 'Election ended successfully. Voting is now closed.',
        'election': format_election_response(updated),
        'total_votes': vote_count
    })


@elections_bp.route('/<election_id>/results', methods=['GET'])
@require_role(['student', 'official', 'admin'])
def get_election_results(election_id):
    """
    Get election results.
    Only available for closed elections (or active for admins).
    """
    user = get_current_user()
    user_role = user.get('role', 'student')

    election = elections_collection.find_one({'election_id': election_id})
    if not election:
        return jsonify({'error': 'Election not found'}), 404

    # Check if results can be viewed
    if election['status'] == 'draft':
        return jsonify({'error': 'Election has not started'}), 400

    if election['status'] == 'active' and user_role != 'admin':
        return jsonify({'error': 'Results not available until election closes'}), 400

    # Fetch and decrypt votes
    votes = list(votes_collection.find(
        {'election_id': election_id},
        {'encrypted_ballot': 1, 'encrypted_aes_key': 1, 'election_id': 1}
    ))

    # Tally votes
    tally = {}
    failed_decryptions = 0

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
            failed_decryptions += 1
            continue

    # Ensure all candidates are represented
    for candidate in election['candidates']:
        if candidate['name'] not in tally:
            tally[candidate['name']] = 0

    # Sort by votes descending
    sorted_results = sorted(tally.items(), key=lambda x: x[1], reverse=True)

    return jsonify({
        'election_id': election_id,
        'title': election['title'],
        'status': election['status'],
        'total_votes': len(votes),
        'results': [{'name': name, 'votes': count} for name, count in sorted_results],
        'tally': tally,
        'failed_decryptions': failed_decryptions if user_role == 'admin' else None
    })


@elections_bp.route('/<election_id>/candidates', methods=['POST'])
@require_role(['official', 'admin'])
def add_candidate(election_id):
    """
    Add a candidate to a draft election.

    Body: {"name": "Candidate Name", "party": "Party Name"}
    """
    election = elections_collection.find_one({'election_id': election_id})
    if not election:
        return jsonify({'error': 'Election not found'}), 404

    if election['status'] != 'draft':
        return jsonify({'error': 'Can only add candidates to draft elections'}), 400

    data = request.get_json()
    if not data.get('name'):
        return jsonify({'error': 'Candidate name is required'}), 400

    # Check for duplicate name
    existing_names = [c['name'].lower() for c in election['candidates']]
    if data['name'].lower() in existing_names:
        return jsonify({'error': 'Candidate with this name already exists'}), 409

    # Generate new ID
    existing_ids = [c['id'] for c in election['candidates']]
    new_id = max(existing_ids) + 1 if existing_ids else 1

    new_candidate = {
        'id': new_id,
        'name': data['name'],
        'party': data.get('party')
    }

    elections_collection.update_one(
        {'election_id': election_id},
        {'$push': {'candidates': new_candidate}}
    )

    return jsonify({
        'message': 'Candidate added successfully',
        'candidate': new_candidate
    }), 201


@elections_bp.route('/<election_id>/candidates/<int:candidate_id>', methods=['DELETE'])
@require_role(['official', 'admin'])
def remove_candidate(election_id, candidate_id):
    """Remove a candidate from a draft election."""
    election = elections_collection.find_one({'election_id': election_id})
    if not election:
        return jsonify({'error': 'Election not found'}), 404

    if election['status'] != 'draft':
        return jsonify({'error': 'Can only remove candidates from draft elections'}), 400

    # Check candidate exists
    candidate = next((c for c in election['candidates'] if c['id'] == candidate_id), None)
    if not candidate:
        return jsonify({'error': 'Candidate not found'}), 404

    # Ensure at least 2 candidates remain
    if len(election['candidates']) <= 2:
        return jsonify({'error': 'Election must have at least 2 candidates'}), 400

    elections_collection.update_one(
        {'election_id': election_id},
        {'$pull': {'candidates': {'id': candidate_id}}}
    )

    return jsonify({'message': 'Candidate removed successfully'})
