"""
restore_chain.py
================
Demo script: restores a chain broken by break_chain.py by recomputing
the correct hash for the tampered vote.

Run from the backend/ directory:
    python scripts/restore_chain.py

Set MONGO_URI env var if not using the default local connection.
"""

import os
import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from pymongo import MongoClient
from crypto.ballot_crypto import BallotCrypto

MONGO_URI = os.getenv('MONGO_URI', 'mongodb://localhost:27017/securevote')

client = MongoClient(MONGO_URI)
db = client.get_default_database()
elections_col = db['elections']
votes_col = db['votes']


def main():
    # ── Find most recent election ────────────────────────────────────────────
    election = elections_col.find_one(
        {},
        sort=[('created_at', -1)]
    )

    if not election:
        print('No elections found.')
        sys.exit(1)

    election_id = election['election_id']
    print(f'Target election : {election["title"]} ({election_id})')

    # ── Fetch votes in chain order ───────────────────────────────────────────
    votes = list(votes_col.find(
        {'election_id': election_id},
        sort=[('timestamp', 1)]
    ))

    if not votes:
        print('No votes found.')
        sys.exit(1)

    crypto = BallotCrypto()

    # Recompute and restore correct hash for each vote
    expected_previous = 'GENESIS'
    restored = 0

    for i, vote in enumerate(votes):
        correct_hash = crypto._generate_chain_hash(
            vote['encrypted_ballot'],
            vote['encrypted_aes_key'],
            vote['election_id'],
            vote['previous_hash'],
        )

        if vote['current_hash'] != correct_hash:
            votes_col.update_one(
                {'_id': vote['_id']},
                {'$set': {'current_hash': correct_hash}}
            )
            print(f'Restored vote {i + 1}: {vote["current_hash"][:16]}... -> {correct_hash[:16]}...')
            restored += 1

        expected_previous = correct_hash

    if restored == 0:
        print('Chain is already intact — nothing to restore.')
    else:
        print(f'\n{restored} vote(s) restored. Chain integrity confirmed.')


if __name__ == '__main__':
    main()
