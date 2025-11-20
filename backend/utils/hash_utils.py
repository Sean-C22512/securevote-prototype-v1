import hashlib
import json

def generate_vote_hash(vote_data: dict) -> str:
    """
    PROTOTYPE-ONLY:
    Generates a SHA-256 hash of the vote payload.
    
    In the final system, this will be replaced by:
    - AES encryption of ballot contents
    - RSA encryption of the AES key
    - SHA-256 hash-chaining for audit logs
    """
    encoded = json.dumps(vote_data, sort_keys=True, default=str).encode()
    return hashlib.sha256(encoded).hexdigest()

