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

# ── Flask imports ──────────────────────────────────────────────────────────────
# Blueprint: lets us group these routes separately from app.py and register them
#            later via app.register_blueprint().
# request:   gives us access to the incoming HTTP request body and query params.
# jsonify:   converts a Python dict into a proper JSON HTTP response.
from flask import Blueprint, request, jsonify

# datetime / timezone: used to record timestamps (e.g. when voting started/ended)
# and to compare date strings when updating election times.
from datetime import datetime, timezone

# ── Auth utilities ─────────────────────────────────────────────────────────────
# require_role: decorator that checks the JWT token's role claim.
#               Routes decorated with @require_role(['official']) will return 403
#               if a student tries to call them.
# require_auth: decorator that simply checks a valid JWT exists (any role).
# get_current_user: returns the full user document from MongoDB for the
#                   currently authenticated caller.
from utils.auth import require_role, require_auth, get_current_user

# ── Election model helpers ─────────────────────────────────────────────────────
# validate_election_data:    checks required fields and data types on POST/PUT bodies.
# prepare_election_document: converts the raw request body into a MongoDB document
#                            with all required fields (timestamps, generated IDs, etc.).
# format_election_response:  strips internal MongoDB fields (like _id) and formats
#                            dates as ISO strings before sending back to the client.
# can_transition_status:     enforces the election state machine
#                            (e.g. can't go draft → closed directly).
# ELECTION_STATUSES:         the allowed status values: draft, active, closed, archived.
from models.election import (
    validate_election_data,
    prepare_election_document,
    format_election_response,
    can_transition_status,
    ELECTION_STATUSES
)

# ── Blueprint definition ───────────────────────────────────────────────────────
# All routes in this file will be prefixed with /elections.
# e.g. the "" route below becomes GET /elections.
elections_bp = Blueprint('elections', __name__, url_prefix='/elections')

# ── Module-level DB / crypto handles ──────────────────────────────────────────
# These start as None and are filled in by init_elections_routes() when app.py
# registers this blueprint.  Using this pattern avoids circular imports because
# app.py can import the blueprint object without triggering any DB connection.
# Will be set when blueprint is registered
elections_collection = None  # MongoDB collection for election documents
votes_collection = None       # MongoDB collection for encrypted vote documents
ballot_crypto = None          # BallotCrypto instance (used for results tallying)


def init_elections_routes(elections_col, votes_col, crypto):
    """Initialize route dependencies."""
    # ── Inject MongoDB collections and the crypto service from app.py ──────────
    # This is called once at startup before any requests are handled.
    global elections_collection, votes_collection, ballot_crypto
    elections_collection = elections_col
    votes_collection = votes_col
    ballot_crypto = crypto


# ── GET /elections ─────────────────────────────────────────────────────────────
@elections_bp.route('', methods=['GET'])
@require_auth  # any logged-in user can list elections
def list_elections():
    """
    List all elections.

    Query params:
    - status: Filter by status (draft, active, closed, archived)
    - limit: Number of results (default 50)
    - skip: Pagination offset (default 0)
    """
    # ── Identify who is asking ─────────────────────────────────────────────────
    # We need the caller's role to decide which elections they're allowed to see.
    user = get_current_user()
    user_role = user.get('role', 'student')

    # ── Parse optional query parameters ───────────────────────────────────────
    status_filter = request.args.get('status')           # e.g. ?status=active
    limit = min(int(request.args.get('limit', 50)), 100) # cap at 100 to prevent huge payloads
    skip = int(request.args.get('skip', 0))              # used for pagination

    # ── Build the MongoDB query filter ────────────────────────────────────────
    query = {}
    if status_filter:
        # Reject unknown status values early so we don't do a DB round-trip for nothing.
        if status_filter not in ELECTION_STATUSES:
            return jsonify({'error': f'Invalid status. Must be one of: {ELECTION_STATUSES}'}), 400
        query['status'] = status_filter

    # ── Restrict students to visible elections only ────────────────────────────
    # Students must never see draft elections — those are for admins/officials to
    # set up before they're published.  We override (or set) the status filter
    # to only allow active or closed elections for this role.
    if user_role == 'student':
        query['status'] = {'$in': ['active', 'closed']}

    # ── Execute the MongoDB query ──────────────────────────────────────────────
    # Sort newest-first, skip for pagination, limit the result set.
    elections = list(elections_collection.find(query)
                     .sort('created_at', -1)
                     .skip(skip)
                     .limit(limit))

    # ── Filter by programme eligibility for students ───────────────────────────
    # Some elections are restricted to specific TUD programmes (e.g. only CS
    # students can vote for the CS class rep).  We filter the list here so
    # students only see elections they're actually eligible to vote in.
    if user_role == 'student':
        student_code = (user.get('programme') or {}).get('code')  # e.g. "TU856"
        def is_eligible(election):
            eligible = election.get('eligible_programmes', [])
            if not eligible:
                return True  # open to all — no programme restriction
            return student_code in [p['code'] for p in eligible]
        elections = [e for e in elections if is_eligible(e)]

    total = len(elections)

    # ── Serialise and return ───────────────────────────────────────────────────
    # format_election_response strips internal MongoDB fields and converts dates
    # to strings so the frontend can safely consume the JSON.
    return jsonify({
        'elections': [format_election_response(e) for e in elections],
        'total': total,
        'limit': limit,
        'skip': skip
    })


# ── POST /elections ────────────────────────────────────────────────────────────
@elections_bp.route('', methods=['POST'])
@require_role(['official', 'admin'])  # students cannot create elections
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

    # ── Validate the request body ──────────────────────────────────────────────
    # validate_election_data checks that required fields exist, that there are
    # at least two candidates, and that any datetime strings are valid ISO format.
    is_valid, errors = validate_election_data(data)
    if not is_valid:
        return jsonify({'error': 'Validation failed', 'details': errors}), 400

    # ── Build the MongoDB document ─────────────────────────────────────────────
    # prepare_election_document assigns a unique election_id, sets created_at,
    # sets initial status to "draft", and normalises the candidates list.
    election_doc = prepare_election_document(data, user['student_id'])

    # ── Prevent duplicate titles ───────────────────────────────────────────────
    # Two non-archived elections with the same title would be confusing for voters.
    # We allow duplicate titles only for archived elections (historical records).
    existing = elections_collection.find_one({
        'title': election_doc['title'],
        'status': {'$ne': 'archived'}
    })
    if existing:
        return jsonify({'error': 'An election with this title already exists'}), 409

    # ── Insert into MongoDB ────────────────────────────────────────────────────
    # insert_one() returns a result object whose inserted_id is the new document's
    # _id.  We add it back to the doc so format_election_response can use it.
    result = elections_collection.insert_one(election_doc)
    election_doc['_id'] = result.inserted_id

    # ── Return the created election with HTTP 201 Created ─────────────────────
    return jsonify({
        'message': 'Election created successfully',
        'election': format_election_response(election_doc)
    }), 201


# ── GET /elections/<election_id> ───────────────────────────────────────────────
@elections_bp.route('/<election_id>', methods=['GET'])
@require_auth  # any logged-in user can request a specific election
def get_election(election_id):
    """Get election details by election_id."""
    user = get_current_user()
    user_role = user.get('role', 'student')

    # ── Look up the election by its human-readable ID ──────────────────────────
    # We use election_id (e.g. "ELEC-2025-001") not MongoDB's _id ObjectId.
    election = elections_collection.find_one({'election_id': election_id})
    if not election:
        return jsonify({'error': 'Election not found'}), 404

    # ── Students cannot see draft elections ────────────────────────────────────
    # We return 404 (not 403) so students can't even tell a draft exists —
    # leaking the existence of a draft is an information disclosure risk.
    if user_role == 'student' and election['status'] not in ['active', 'closed']:
        return jsonify({'error': 'Election not found'}), 404

    # ── Students can only see elections they're eligible for ───────────────────
    # Again we return 404 rather than 403 to avoid disclosing programme-restricted
    # elections to ineligible students.
    if user_role == 'student':
        eligible_programmes = election.get('eligible_programmes', [])
        if eligible_programmes:
            student_code = (user.get('programme') or {}).get('code')
            if student_code not in [p['code'] for p in eligible_programmes]:
                return jsonify({'error': 'Election not found'}), 404

    # ── Build the response, adding vote count for privileged users ─────────────
    # Officials and admins see a live vote count alongside the election details.
    # Students never see the running total — that would break ballot secrecy.
    response = format_election_response(election)
    if user_role in ['official', 'admin']:
        vote_count = votes_collection.count_documents({'election_id': election_id})
        response['vote_count'] = vote_count

    return jsonify(response)


# ── PUT /elections/<election_id> ───────────────────────────────────────────────
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

    # ── Validate the incoming update data ─────────────────────────────────────
    # is_update=True tells the validator to relax the "at least 2 candidates"
    # requirement, since the caller might only be updating the description.
    is_valid, errors = validate_election_data(data, is_update=True)
    if not is_valid:
        return jsonify({'error': 'Validation failed', 'details': errors}), 400

    # ── Determine which fields are allowed to change based on election status ──
    # This enforces the election lifecycle: once voting opens, most settings
    # are locked in to prevent the rules being changed mid-election.
    status = election['status']
    update_fields = {}

    if status == 'draft':
        # ── Draft: full editing is allowed ────────────────────────────────────
        # Everything except the system-assigned election_id and audit timestamps
        # can be changed while the election is still being set up.
        allowed = ['title', 'description', 'candidates', 'start_time', 'end_time', 'settings']
        for field in allowed:
            if field in data:
                value = data[field]
                # ── Parse ISO datetime strings into Python datetime objects ───
                # MongoDB stores native datetimes; string input from JSON needs
                # to be converted.  The replace('Z', '+00:00') handles the
                # JavaScript-style UTC suffix that fromisoformat doesn't accept.
                if field in ['start_time', 'end_time'] and isinstance(value, str):
                    value = datetime.fromisoformat(value.replace('Z', '+00:00'))
                update_fields[field] = value

    elif status == 'active':
        # ── Active: only the end time can be extended ─────────────────────────
        # Once voting is open we can't change candidates or rules — but an admin
        # might need to give students extra time due to a technical issue.
        if 'end_time' in data:
            new_end = data['end_time']
            if isinstance(new_end, str):
                new_end = datetime.fromisoformat(new_end.replace('Z', '+00:00'))
            # Ensure the new end time is actually in the future relative to the
            # current end time — we only allow extensions, not shortening.
            if new_end <= election.get('end_time', datetime.now(timezone.utc)):
                return jsonify({'error': 'Can only extend end_time for active elections'}), 400
            update_fields['end_time'] = new_end
        else:
            return jsonify({'error': 'Active elections can only have end_time extended'}), 400

    elif status in ['closed', 'archived']:
        # ── Closed / archived: no changes allowed at all ──────────────────────
        # Closed elections are permanent records; altering them would be a
        # tampering risk and would invalidate the audit trail.
        return jsonify({'error': f'Cannot update {status} elections'}), 400

    if not update_fields:
        return jsonify({'error': 'No valid fields to update'}), 400

    # ── Write the changes to MongoDB ───────────────────────────────────────────
    # $set only overwrites the fields in update_fields — everything else stays.
    elections_collection.update_one(
        {'election_id': election_id},
        {'$set': update_fields}
    )

    updated = elections_collection.find_one({'election_id': election_id})
    return jsonify({
        'message': 'Election updated successfully',
        'election': format_election_response(updated)
    })


# ── DELETE /elections/<election_id> ───────────────────────────────────────────
@elections_bp.route('/<election_id>', methods=['DELETE'])
@require_role(['official', 'admin'])
def delete_election(election_id):
    """
    Delete an election.
    Only draft elections with no votes can be deleted.
    """
    election = elections_collection.find_one({'election_id': election_id})
    if not election:
        return jsonify({'error': 'Election not found'}), 404

    # ── Only draft elections may be deleted ───────────────────────────────────
    # Once an election has been published (active/closed), its record is
    # permanent for audit and legal accountability reasons.
    if election['status'] != 'draft':
        return jsonify({'error': 'Only draft elections can be deleted'}), 400

    # ── Refuse to delete if any test votes already exist ──────────────────────
    # A draft might have been used in testing.  If votes exist under this
    # election_id we keep them to preserve data integrity.
    vote_count = votes_collection.count_documents({'election_id': election_id})
    if vote_count > 0:
        return jsonify({'error': 'Cannot delete election with existing votes'}), 400

    # ── Permanently remove the election document ───────────────────────────────
    elections_collection.delete_one({'election_id': election_id})

    return jsonify({'message': 'Election deleted successfully'})


# ── POST /elections/<election_id>/start ───────────────────────────────────────
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

    # ── Check the state machine allows this transition ─────────────────────────
    # can_transition_status enforces valid paths: draft → active is allowed,
    # but closed → active is not (you can't reopen a finished election).
    can_transition, error = can_transition_status(election['status'], 'active')
    if not can_transition:
        return jsonify({'error': error}), 400

    # ── Ensure the election is ready to accept votes ───────────────────────────
    # An election needs at least two candidates — otherwise voters have no
    # meaningful choice and the election would be invalid.
    if len(election.get('candidates', [])) < 2:
        return jsonify({'error': 'Election must have at least 2 candidates'}), 400

    now = datetime.now(timezone.utc)

    # ── Set status to active and record the start timestamp ───────────────────
    # started_at is stored for the audit log and for calculating turnout stats.
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


# ── POST /elections/<election_id>/end ─────────────────────────────────────────
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

    # ── Validate the state transition ─────────────────────────────────────────
    # Only an active election can be closed; trying to close a draft or an
    # already-closed election is rejected.
    can_transition, error = can_transition_status(election['status'], 'closed')
    if not can_transition:
        return jsonify({'error': error}), 400

    now = datetime.now(timezone.utc)

    # ── Set status to closed and record the end timestamp ─────────────────────
    elections_collection.update_one(
        {'election_id': election_id},
        {
            '$set': {
                'status': 'closed',
                'ended_at': now
            }
        }
    )

    # ── Count the total votes cast for the summary response ───────────────────
    vote_count = votes_collection.count_documents({'election_id': election_id})

    updated = elections_collection.find_one({'election_id': election_id})
    return jsonify({
        'message': 'Election ended successfully. Voting is now closed.',
        'election': format_election_response(updated),
        'total_votes': vote_count
    })


# ── GET /elections/<election_id>/results ──────────────────────────────────────
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

    # ── Students must be eligible for this election to see its results ─────────
    # We don't want a student from one programme seeing results for an election
    # that was restricted to a different programme.
    if user_role == 'student':
        eligible_programmes = election.get('eligible_programmes', [])
        if eligible_programmes:
            student_code = (user.get('programme') or {}).get('code')
            if student_code not in [p['code'] for p in eligible_programmes]:
                return jsonify({'error': 'Election not found'}), 404

    # ── Enforce results visibility rules ──────────────────────────────────────
    # Draft elections have never opened — no results to show.
    if election['status'] == 'draft':
        return jsonify({'error': 'Election has not started'}), 400

    # Active elections: only admins can see live results (e.g. for monitoring).
    # Students and officials must wait until voting has closed.
    if election['status'] == 'active' and user_role != 'admin':
        return jsonify({'error': 'Results not available until election closes'}), 400

    # ── Fetch all encrypted vote records for this election ────────────────────
    # We only pull the fields needed for decryption — we don't need timestamps
    # or student_ids here, and excluding them reduces data exposure.
    votes = list(votes_collection.find(
        {'election_id': election_id},
        {'encrypted_ballot': 1, 'encrypted_aes_key': 1, 'election_id': 1}
    ))

    # ── Decrypt and tally the votes ────────────────────────────────────────────
    tally = {}             # maps candidate name → vote count
    failed_decryptions = 0 # counter for any votes that couldn't be decrypted (tampering indicator)

    for vote in votes:
        try:
            # Decrypt using the RSA private key + AES key recovery
            decrypted = ballot_crypto.decrypt_ballot(
                vote['encrypted_ballot'],
                vote['encrypted_aes_key'],
                vote['election_id']
            )
            candidate = decrypted.get('candidate')
            if candidate:
                # Increment the vote count for this candidate (default to 0 if first vote)
                tally[candidate] = tally.get(candidate, 0) + 1
        except Exception:
            # A decryption failure means the ballot was tampered with or corrupted.
            # We count these separately and keep going rather than aborting.
            failed_decryptions += 1
            continue

    # ── Ensure every candidate appears in the results, even with 0 votes ──────
    # Without this, a candidate who received no votes would simply not appear in
    # the tally dict, which would be confusing on the frontend.
    for candidate in election['candidates']:
        if candidate['name'] not in tally:
            tally[candidate['name']] = 0

    # ── Sort candidates highest-votes-first for convenient display ─────────────
    sorted_results = sorted(tally.items(), key=lambda x: x[1], reverse=True)

    return jsonify({
        'election_id': election_id,
        'title': election['title'],
        'status': election['status'],
        'total_votes': len(votes),
        'results': [{'name': name, 'votes': count} for name, count in sorted_results],
        'tally': tally,
        # Only admins see the failed decryption count — students don't need to
        # know about internal integrity issues.
        'failed_decryptions': failed_decryptions if user_role == 'admin' else None
    })


# ── POST /elections/<election_id>/candidates ──────────────────────────────────
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

    # ── Candidates can only be added while the election is still in draft ──────
    # Once voting opens, the candidate list is locked — adding a new candidate
    # mid-election would invalidate all previously cast votes.
    if election['status'] != 'draft':
        return jsonify({'error': 'Can only add candidates to draft elections'}), 400

    data = request.get_json()
    if not data.get('name'):
        return jsonify({'error': 'Candidate name is required'}), 400

    # ── Prevent duplicate candidate names (case-insensitive) ──────────────────
    # Two candidates named "Jane Doe" and "jane doe" would confuse voters and
    # break the vote tallying logic.
    existing_names = [c['name'].lower() for c in election['candidates']]
    if data['name'].lower() in existing_names:
        return jsonify({'error': 'Candidate with this name already exists'}), 409

    # ── Auto-assign the next sequential integer ID ────────────────────────────
    # Candidate IDs are used when a voter submits their choice.  We take the
    # current maximum ID and add 1 — or start at 1 if the list is empty.
    existing_ids = [c['id'] for c in election['candidates']]
    new_id = max(existing_ids) + 1 if existing_ids else 1

    new_candidate = {
        'id': new_id,
        'name': data['name'],
        'party': data.get('party')  # party affiliation is optional
    }

    # ── Append the new candidate to the election's candidates array in MongoDB ─
    # $push appends to a MongoDB array without replacing the whole field.
    elections_collection.update_one(
        {'election_id': election_id},
        {'$push': {'candidates': new_candidate}}
    )

    return jsonify({
        'message': 'Candidate added successfully',
        'candidate': new_candidate
    }), 201


# ── DELETE /elections/<election_id>/candidates/<candidate_id> ─────────────────
@elections_bp.route('/<election_id>/candidates/<int:candidate_id>', methods=['DELETE'])
@require_role(['official', 'admin'])
def remove_candidate(election_id, candidate_id):
    """Remove a candidate from a draft election."""
    election = elections_collection.find_one({'election_id': election_id})
    if not election:
        return jsonify({'error': 'Election not found'}), 404

    # ── Candidates can only be removed from draft elections ───────────────────
    if election['status'] != 'draft':
        return jsonify({'error': 'Can only remove candidates from draft elections'}), 400

    # ── Verify the candidate actually exists ───────────────────────────────────
    candidate = next((c for c in election['candidates'] if c['id'] == candidate_id), None)
    if not candidate:
        return jsonify({'error': 'Candidate not found'}), 404

    # ── Enforce the minimum two-candidate rule ────────────────────────────────
    # An election with only one candidate is not a meaningful choice.
    # We refuse to remove a candidate that would drop the count below 2.
    if len(election['candidates']) <= 2:
        return jsonify({'error': 'Election must have at least 2 candidates'}), 400

    # ── Remove the candidate document from the array using $pull ──────────────
    # $pull removes all array elements that match the given filter — in this case
    # the specific candidate id.
    elections_collection.update_one(
        {'election_id': election_id},
        {'$pull': {'candidates': {'id': candidate_id}}}
    )

    return jsonify({'message': 'Candidate removed successfully'})
