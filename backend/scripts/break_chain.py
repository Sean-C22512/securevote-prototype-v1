"""
break_chain.py
==============
Demo script: intentionally corrupts a single vote's current_hash in the
most recent election to simulate a tampered block.

Run from the backend/ directory:
    python scripts/break_chain.py

Set MONGO_URI env var if not using the default local connection.
"""

import os
import sys
from pymongo import MongoClient

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

    if len(votes) < 1:
        print('No votes found in this election — nothing to tamper.')
        sys.exit(1)

    # Pick the first vote to tamper (breaking all subsequent links)
    target = votes[0]
    original_hash = target['current_hash']
    tampered_hash = 'TAMPERED' + original_hash[8:]  # corrupt the first 8 chars

    votes_col.update_one(
        {'_id': target['_id']},
        {'$set': {'current_hash': tampered_hash}}
    )

    print(f'\nTampered vote  : index 1 (VOTE-001)')
    print(f'Original hash  : {original_hash}')
    print(f'Corrupted hash : {tampered_hash}')
    print(f'\nChain is now broken. Open the Audit Trail to see the tampered block.')
    print('Run restore_chain.py to undo.')


if __name__ == '__main__':
    main()
