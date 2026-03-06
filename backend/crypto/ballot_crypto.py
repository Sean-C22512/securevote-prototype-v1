"""
SecureVote Ballot Cryptography
==============================
High-level API for encrypting and decrypting ballot data.

Encryption Flow:
1. Generate random AES-256 session key
2. Encrypt ballot data with AES-GCM (authenticated)
3. Encrypt AES key with RSA public key
4. Generate SHA-256 hash for audit chain
5. Return encrypted package for MongoDB storage

This implements the hybrid cryptographic system described in:
- FR2: Cryptographic Voting & Integrity
- Section 4.3.3: Security Architecture
"""

import hashlib
import json
import base64
from datetime import datetime, timezone
from typing import Dict, Any, Optional

from .key_manager import KeyManager, get_key_manager
from .aes_cipher import AESCipher


class BallotCrypto:
    """
    High-level ballot encryption/decryption service.

    Usage:
        crypto = BallotCrypto()

        # Encrypt a ballot
        encrypted = crypto.encrypt_ballot({
            'candidate_id': 1,
            'candidate': 'Candidate A',
            'timestamp': datetime.utcnow()
        }, election_id='ELEC-2025-001')

        # Store encrypted['encrypted_ballot'], encrypted['encrypted_aes_key'],
        # encrypted['current_hash'] in MongoDB

        # Decrypt (admin only - for tallying)
        ballot = crypto.decrypt_ballot(
            encrypted['encrypted_ballot'],
            encrypted['encrypted_aes_key'],
            election_id='ELEC-2025-001'
        )
    """

    def __init__(self, key_manager: KeyManager = None):
        """
        Initialize BallotCrypto.

        Args:
            key_manager: KeyManager instance. Uses default if None.
        """
        self.key_manager = key_manager or get_key_manager()

        # Ensure RSA keys exist
        if not self.key_manager.keys_exist():
            self.key_manager.generate_keys()

    def encrypt_ballot(self, ballot_data: Dict[str, Any],
                       election_id: str,
                       previous_hash: str = None) -> Dict[str, str]:
        """
        Encrypt a ballot for secure storage.

        Args:
            ballot_data: Dictionary containing vote information.
                        Should include: candidate_id, candidate (name), timestamp
            election_id: Unique identifier for the election.
                        Used as Associated Authenticated Data (AAD).
            previous_hash: Hash of the previous vote in the chain.
                          Use "GENESIS" or None for the first vote.

        Returns:
            Dictionary containing:
            - encrypted_ballot: Base64-encoded AES-encrypted ballot
            - encrypted_aes_key: Base64-encoded RSA-encrypted AES key
            - current_hash: SHA-256 hash for chain linking
            - previous_hash: The previous hash (for verification)
            - election_id: The election identifier
        """
        # Ensure timestamp is serializable
        ballot_to_encrypt = self._prepare_ballot_data(ballot_data)

        # Generate unique AES key for this ballot
        aes_cipher = AESCipher()
        aes_key = aes_cipher.key

        # Use election_id as AAD (authenticated but not encrypted)
        aad = election_id.encode('utf-8')

        # Encrypt ballot data with AES-GCM
        encrypted_ballot_bytes = aes_cipher.encrypt(ballot_to_encrypt, aad)
        encrypted_ballot_b64 = base64.b64encode(encrypted_ballot_bytes).decode('ascii')

        # Encrypt AES key with RSA
        encrypted_aes_key_bytes = self.key_manager.encrypt_aes_key(aes_key)
        encrypted_aes_key_b64 = base64.b64encode(encrypted_aes_key_bytes).decode('ascii')

        # Generate hash for audit chain
        prev_hash = previous_hash or "GENESIS"
        current_hash = self._generate_chain_hash(
            encrypted_ballot_b64,
            encrypted_aes_key_b64,
            election_id,
            prev_hash
        )

        return {
            'encrypted_ballot': encrypted_ballot_b64,
            'encrypted_aes_key': encrypted_aes_key_b64,
            'current_hash': current_hash,
            'previous_hash': prev_hash,
            'election_id': election_id
        }

    def decrypt_ballot(self, encrypted_ballot_b64: str,
                       encrypted_aes_key_b64: str,
                       election_id: str) -> Dict[str, Any]:
        """
        Decrypt a ballot (admin operation for tallying).

        Args:
            encrypted_ballot_b64: Base64-encoded encrypted ballot
            encrypted_aes_key_b64: Base64-encoded encrypted AES key
            election_id: Election ID (must match encryption AAD)

        Returns:
            Decrypted ballot data as dictionary.

        Raises:
            InvalidTag: If ballot was tampered with (authentication failed)
        """
        # Decode from base64
        encrypted_ballot = base64.b64decode(encrypted_ballot_b64)
        encrypted_aes_key = base64.b64decode(encrypted_aes_key_b64)

        # Decrypt AES key using RSA private key
        aes_key = self.key_manager.decrypt_aes_key(encrypted_aes_key)

        # Recreate AES cipher with decrypted key
        aes_cipher = AESCipher(aes_key)

        # Decrypt ballot (AAD must match)
        aad = election_id.encode('utf-8')
        ballot_data = aes_cipher.decrypt_to_dict(encrypted_ballot, aad)

        return ballot_data

    def verify_chain_link(self, encrypted_ballot_b64: str,
                          encrypted_aes_key_b64: str,
                          election_id: str,
                          previous_hash: str,
                          claimed_hash: str) -> bool:
        """
        Verify a single link in the hash chain (tamper detection).

        Args:
            encrypted_ballot_b64: Stored encrypted ballot
            encrypted_aes_key_b64: Stored encrypted AES key
            election_id: Election identifier
            previous_hash: Claimed previous hash
            claimed_hash: Hash claimed for this vote

        Returns:
            True if hash is valid, False if tampering detected.
        """
        computed_hash = self._generate_chain_hash(
            encrypted_ballot_b64,
            encrypted_aes_key_b64,
            election_id,
            previous_hash
        )
        return computed_hash == claimed_hash

    def verify_chain(self, votes: list) -> Dict[str, Any]:
        """
        Verify an entire chain of votes for an election.

        Args:
            votes: List of vote documents from MongoDB, ordered by timestamp.
                  Each must have: encrypted_ballot, encrypted_aes_key,
                  election_id, previous_hash, current_hash

        Returns:
            Dictionary with:
            - valid: True if entire chain is valid
            - verified_count: Number of votes verified
            - broken_at: Index of first broken link (if invalid)
            - details: List of verification results per vote
        """
        if not votes:
            return {'valid': True, 'verified_count': 0, 'details': []}

        results = []
        expected_previous = "GENESIS"

        for i, vote in enumerate(votes):
            # Verify this vote's hash
            hash_valid = self.verify_chain_link(
                vote['encrypted_ballot'],
                vote['encrypted_aes_key'],
                vote['election_id'],
                vote['previous_hash'],
                vote['current_hash']
            )

            # Verify chain continuity
            chain_valid = vote['previous_hash'] == expected_previous

            is_valid = hash_valid and chain_valid

            results.append({
                'index': i,
                'hash_valid': hash_valid,
                'chain_valid': chain_valid,
                'valid': is_valid
            })

            if not is_valid:
                return {
                    'valid': False,
                    'verified_count': i,
                    'broken_at': i,
                    'details': results
                }

            expected_previous = vote['current_hash']

        return {
            'valid': True,
            'verified_count': len(votes),
            'details': results
        }

    def _prepare_ballot_data(self, ballot_data: Dict[str, Any]) -> Dict[str, Any]:
        """Prepare ballot data for encryption (handle datetime serialization)."""
        prepared = {}
        for key, value in ballot_data.items():
            if isinstance(value, datetime):
                prepared[key] = value.isoformat()
            else:
                prepared[key] = value
        return prepared

    def _generate_chain_hash(self, encrypted_ballot: str,
                             encrypted_aes_key: str,
                             election_id: str,
                             previous_hash: str) -> str:
        """
        Generate SHA-256 hash for audit chain.

        The hash includes:
        - Encrypted ballot data
        - Encrypted AES key
        - Election ID
        - Previous vote's hash

        This creates an immutable chain where modifying any vote
        breaks all subsequent hashes.
        """
        hash_input = json.dumps({
            'encrypted_ballot': encrypted_ballot,
            'encrypted_aes_key': encrypted_aes_key,
            'election_id': election_id,
            'previous_hash': previous_hash
        }, sort_keys=True)

        return hashlib.sha256(hash_input.encode()).hexdigest()


# Module-level convenience function
_default_ballot_crypto = None

def get_ballot_crypto() -> BallotCrypto:
    """Get or create the default BallotCrypto instance."""
    global _default_ballot_crypto
    if _default_ballot_crypto is None:
        _default_ballot_crypto = BallotCrypto()
    return _default_ballot_crypto
