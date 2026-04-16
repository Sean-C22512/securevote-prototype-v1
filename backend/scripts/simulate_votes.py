"""
simulate_votes.py
=================
Demo script: casts a vote on behalf of every eligible student in the
most recent active election. Ineligible students are silently skipped.
Students who have already voted are also skipped.

Run from the backend/ directory:
    python scripts/simulate_votes.py

Set MONGO_URI env var to target production:
    MONGO_URI="mongodb+srv://..." python scripts/simulate_votes.py
"""

import os
import sys
import random
import datetime

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from pymongo import MongoClient
from pymongo.errors import DuplicateKeyError
from crypto.ballot_crypto import BallotCrypto

MONGO_URI = os.getenv('MONGO_URI', 'mongodb://localhost:27017/securevote')

client = MongoClient(MONGO_URI)
db = client.get_default_database()
elections_col = db['elections']
votes_col     = db['votes']
users_col     = db['users']


def main():
    # ── Find most recent active election ─────────────────────────────────────
    election = elections_col.find_one(
        {'status': 'active'},
        sort=[('created_at', -1)]
    )

    if not election:
        # Fall back to most recent election of any status for demo flexibility
        election = elections_col.find_one({}, sort=[('created_at', -1)])
        if not election:
            print('No elections found.')
            sys.exit(1)
        print(f'Warning: no active election found. Using most recent: "{election["title"]}" ({election["status"]})')
    else:
        print(f'Election : {election["title"]} ({election["election_id"]})')

    election_id        = election['election_id']
    candidates         = election.get('candidates', [])
    eligible_programmes = election.get('eligible_programmes', [])  # empty = open to all
    eligible_codes     = {p['code'] for p in eligible_programmes}
    open_to_all        = len(eligible_codes) == 0

    if not candidates:
        print('Election has no candidates.')
        sys.exit(1)

    print(f'Candidates       : {[c["name"] for c in candidates]}')
    print(f'Open to all      : {open_to_all}')
    if not open_to_all:
        print(f'Eligible programmes: {eligible_codes}')
    print()

    # ── Load all students ─────────────────────────────────────────────────────
    students = list(users_col.find({'role': 'student'}))
    print(f'Total students   : {len(students)}')

    crypto = BallotCrypto()

    voted = 0
    skipped_ineligible = 0
    skipped_already_voted = 0
    failed = 0

    for student in students:
        student_id = student['student_id']

        # ── Eligibility check ─────────────────────────────────────────────────
        if not open_to_all:
            programme = student.get('programme', {})
            code = programme.get('code') if programme else None
            if code not in eligible_codes:
                skipped_ineligible += 1
                continue

        # ── Duplicate vote check ──────────────────────────────────────────────
        if votes_col.find_one({'student_id': student_id, 'election_id': election_id}):
            skipped_already_voted += 1
            continue

        # ── Pick a random candidate ───────────────────────────────────────────
        candidate = random.choice(candidates)
        ballot_data = {
            'candidate_id': candidate['id'],
            'candidate':    candidate['name'],
            'timestamp':    datetime.datetime.now(datetime.timezone.utc),
        }

        # ── Atomic chain insertion (mirrors app.py logic) ─────────────────────
        max_retries = 10
        success = False
        for attempt in range(max_retries):
            last_vote = votes_col.find_one(
                {'election_id': election_id},
                sort=[('timestamp', -1)]
            )
            previous_hash = last_vote['current_hash'] if last_vote else None

            encrypted = crypto.encrypt_ballot(
                ballot_data,
                election_id,
                previous_hash=previous_hash
            )

            vote_record = {
                'student_id':      student_id,
                'election_id':     election_id,
                'encrypted_ballot':   encrypted['encrypted_ballot'],
                'encrypted_aes_key':  encrypted['encrypted_aes_key'],
                'current_hash':    encrypted['current_hash'],
                'previous_hash':   encrypted['previous_hash'],
                'timestamp':       datetime.datetime.now(datetime.timezone.utc),
                'sequence':        (last_vote.get('sequence', 0) + 1) if last_vote else 1,
            }

            try:
                votes_col.insert_one(vote_record)
                success = True
                break
            except DuplicateKeyError:
                if attempt == max_retries - 1:
                    break
                continue

        if success:
            print(f'  Voted  {student_id} -> {candidate["name"]}')
            voted += 1
        else:
            print(f'  FAILED {student_id} (chain conflict after {max_retries} retries)')
            failed += 1

    # ── Summary ───────────────────────────────────────────────────────────────
    print()
    print(f'Done.')
    print(f'  Votes cast        : {voted}')
    print(f'  Already voted     : {skipped_already_voted}')
    print(f'  Ineligible        : {skipped_ineligible}')
    print(f'  Failed            : {failed}')


if __name__ == '__main__':
    main()
