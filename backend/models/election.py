"""
SecureVote Election Model
=========================
Defines the Election schema and lifecycle management.

Election States:
- draft: Election created but not yet open for voting
- active: Voting is open
- closed: Voting has ended, results available
- archived: Historical election (optional)

Schema:
{
    "_id": ObjectId,
    "election_id": "TUD-SU-2025-001",  # Human-readable ID
    "title": "Student Union President 2025",
    "description": "Annual SU presidential election",
    "candidates": [
        {"id": 1, "name": "Candidate A", "party": "Party Alpha"},
        {"id": 2, "name": "Candidate B", "party": "Party Beta"}
    ],
    "status": "draft|active|closed|archived",
    "created_by": "ADMIN001",
    "created_at": datetime,
    "start_time": datetime,  # When voting opens
    "end_time": datetime,    # When voting closes
    "started_at": datetime,  # Actual start time
    "ended_at": datetime,    # Actual end time
    "settings": {
        "allow_multiple_votes": false,  # Future: ranked choice
        "require_verification": false   # Future: 2FA requirement
    }
}
"""

import re
from datetime import datetime, timezone
from typing import Dict, Any, List, Optional
from bson import ObjectId


# Valid election statuses
ELECTION_STATUSES = ['draft', 'active', 'closed', 'archived']


def generate_election_id(title: str, year: int = None) -> str:
    """
    Generate a human-readable election ID from title.

    Example: "Student Union President 2025" -> "SU-PRESIDENT-2025-XXXX"
    """
    if year is None:
        year = datetime.now(timezone.utc).year

    # Clean title: uppercase, remove special chars, take first 3 words
    clean = re.sub(r'[^A-Za-z0-9\s]', '', title.upper())
    words = clean.split()[:3]
    prefix = '-'.join(words) if words else 'ELECTION'

    # Add random suffix for uniqueness
    import secrets
    suffix = secrets.token_hex(2).upper()

    return f"{prefix}-{year}-{suffix}"


def validate_election_data(data: Dict[str, Any], is_update: bool = False) -> tuple:
    """
    Validate election data for creation or update.

    Args:
        data: Election data dictionary
        is_update: If True, fields are optional

    Returns:
        (is_valid, errors) tuple
    """
    errors = []

    # Required fields for creation
    if not is_update:
        if not data.get('title'):
            errors.append('Title is required')
        if not data.get('candidates') or len(data.get('candidates', [])) < 2:
            errors.append('At least 2 candidates are required')

    # Validate title length
    if 'title' in data and data['title']:
        if len(data['title']) < 5:
            errors.append('Title must be at least 5 characters')
        if len(data['title']) > 200:
            errors.append('Title must be less than 200 characters')

    # Validate candidates structure
    if 'candidates' in data:
        candidates = data['candidates']
        if not isinstance(candidates, list):
            errors.append('Candidates must be a list')
        else:
            seen_ids = set()
            seen_names = set()
            for i, candidate in enumerate(candidates):
                if not isinstance(candidate, dict):
                    errors.append(f'Candidate {i+1} must be an object')
                    continue
                if not candidate.get('name'):
                    errors.append(f'Candidate {i+1} is missing a name')
                if candidate.get('name', '').lower() in seen_names:
                    errors.append(f'Duplicate candidate name: {candidate.get("name")}')
                seen_names.add(candidate.get('name', '').lower())

                if 'id' in candidate:
                    if candidate['id'] in seen_ids:
                        errors.append(f'Duplicate candidate ID: {candidate["id"]}')
                    seen_ids.add(candidate['id'])

    # Validate times if provided
    if 'start_time' in data and 'end_time' in data:
        start = data.get('start_time')
        end = data.get('end_time')
        if start and end:
            if isinstance(start, str):
                try:
                    start = datetime.fromisoformat(start.replace('Z', '+00:00'))
                except ValueError:
                    errors.append('Invalid start_time format')
            if isinstance(end, str):
                try:
                    end = datetime.fromisoformat(end.replace('Z', '+00:00'))
                except ValueError:
                    errors.append('Invalid end_time format')

            if isinstance(start, datetime) and isinstance(end, datetime):
                if end <= start:
                    errors.append('end_time must be after start_time')

    return (len(errors) == 0, errors)


def prepare_election_document(data: Dict[str, Any], created_by: str) -> Dict[str, Any]:
    """
    Prepare a new election document for insertion.

    Args:
        data: Validated election data
        created_by: Student ID of the creator

    Returns:
        Complete election document ready for MongoDB
    """
    now = datetime.now(timezone.utc)

    # Assign IDs to candidates if not provided
    candidates = data.get('candidates', [])
    for i, candidate in enumerate(candidates):
        if 'id' not in candidate:
            candidate['id'] = i + 1
        # Ensure party field exists
        if 'party' not in candidate:
            candidate['party'] = None

    # Parse datetime strings if needed
    start_time = data.get('start_time')
    end_time = data.get('end_time')

    if isinstance(start_time, str):
        start_time = datetime.fromisoformat(start_time.replace('Z', '+00:00'))
    if isinstance(end_time, str):
        end_time = datetime.fromisoformat(end_time.replace('Z', '+00:00'))

    return {
        'election_id': generate_election_id(data['title']),
        'title': data['title'],
        'description': data.get('description', ''),
        'candidates': candidates,
        'status': 'draft',
        'created_by': created_by,
        'created_at': now,
        'start_time': start_time,
        'end_time': end_time,
        'started_at': None,
        'ended_at': None,
        'settings': {
            'allow_multiple_votes': False,
            'require_verification': False
        }
    }


def can_transition_status(current: str, target: str) -> tuple:
    """
    Check if a status transition is allowed.

    Valid transitions:
    - draft -> active (start election)
    - active -> closed (end election)
    - closed -> archived (archive)
    - draft -> archived (cancel without running)

    Returns:
        (is_allowed, error_message) tuple
    """
    allowed_transitions = {
        'draft': ['active', 'archived'],
        'active': ['closed'],
        'closed': ['archived'],
        'archived': []
    }

    if current not in ELECTION_STATUSES:
        return (False, f'Invalid current status: {current}')

    if target not in ELECTION_STATUSES:
        return (False, f'Invalid target status: {target}')

    if target in allowed_transitions.get(current, []):
        return (True, None)

    return (False, f'Cannot transition from {current} to {target}')


def format_election_response(election: Dict[str, Any], include_id: bool = False) -> Dict[str, Any]:
    """
    Format an election document for API response.

    Args:
        election: MongoDB election document
        include_id: Whether to include MongoDB _id

    Returns:
        Formatted election dictionary
    """
    response = {
        'election_id': election['election_id'],
        'title': election['title'],
        'description': election.get('description', ''),
        'candidates': election['candidates'],
        'status': election['status'],
        'created_by': election['created_by'],
        'created_at': election['created_at'].isoformat() if election.get('created_at') else None,
        'start_time': election['start_time'].isoformat() if election.get('start_time') else None,
        'end_time': election['end_time'].isoformat() if election.get('end_time') else None,
        'started_at': election['started_at'].isoformat() if election.get('started_at') else None,
        'ended_at': election['ended_at'].isoformat() if election.get('ended_at') else None,
        'settings': election.get('settings', {})
    }

    if include_id:
        response['_id'] = str(election['_id'])

    return response
