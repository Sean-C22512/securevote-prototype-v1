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

# ── Standard library imports ──────────────────────────────────────────────────
# hashlib: gives us SHA-256 for generating the audit chain hashes
# json: used to turn the ballot dictionary into a consistent string before hashing
# base64: lets us encode raw bytes as ASCII-safe text so they can be stored in MongoDB
# datetime / timezone: used to handle timestamps when preparing ballot data
# Dict, Any, Optional: Python type hints — purely for readability and IDE support
import hashlib
import json
import base64
from datetime import datetime, timezone
from typing import Dict, Any, Optional

# ── Internal crypto module imports ────────────────────────────────────────────
# KeyManager handles the RSA key pair — generating, loading, and using them.
# AESCipher handles AES-256-GCM symmetric encryption of the actual ballot content.
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
        # ── Step 1: Attach a KeyManager ────────────────────────────────────────
        # If the caller didn't provide one, grab the shared singleton.
        # The KeyManager is responsible for the RSA key pair that protects every
        # per-ballot AES key.
        self.key_manager = key_manager or get_key_manager()

        # ── Step 2: Ensure RSA keys exist on disk ──────────────────────────────
        # If the server has never been started before (or the keys were deleted),
        # generate a fresh 2048-bit RSA key pair and save it to disk so that
        # previously encrypted ballots can still be decrypted later.
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
        # ── Step 1: Sanitise the ballot data ───────────────────────────────────
        # MongoDB datetime objects can't be JSON-serialised directly.
        # _prepare_ballot_data converts any datetime values to ISO-8601 strings
        # so they survive the JSON round-trip inside the encrypted payload.
        ballot_to_encrypt = self._prepare_ballot_data(ballot_data)

        # ── Step 2: Create a fresh, unique AES-256 key for this ballot ─────────
        # Every single ballot gets its own random 32-byte (256-bit) AES key.
        # This is the "hybrid" part of hybrid encryption: fast symmetric AES
        # encrypts the data, and slower asymmetric RSA protects the AES key.
        aes_cipher = AESCipher()
        aes_key = aes_cipher.key  # extract the raw key bytes so we can RSA-encrypt them

        # ── Step 3: Set the election ID as Associated Authenticated Data (AAD) ─
        # AAD is "authenticated but not encrypted" — it's included in the GCM
        # authentication tag but not hidden. This means if someone swaps the
        # ballot from one election to another, decryption will fail.
        aad = election_id.encode('utf-8')

        # ── Step 4: Encrypt the ballot payload with AES-256-GCM ───────────────
        # AES-GCM gives us both confidentiality (no one can read the vote) and
        # integrity (any tampering with the ciphertext is detected).
        # The result is raw bytes; we base64-encode it so it can be stored as a
        # plain string in MongoDB.
        encrypted_ballot_bytes = aes_cipher.encrypt(ballot_to_encrypt, aad)
        encrypted_ballot_b64 = base64.b64encode(encrypted_ballot_bytes).decode('ascii')

        # ── Step 5: Protect the AES key with RSA ──────────────────────────────
        # We encrypt the 32-byte AES key using the RSA public key (OAEP padding).
        # Only the holder of the RSA private key (the admin server) can recover
        # the AES key and therefore decrypt the ballot.
        encrypted_aes_key_bytes = self.key_manager.encrypt_aes_key(aes_key)
        encrypted_aes_key_b64 = base64.b64encode(encrypted_aes_key_bytes).decode('ascii')

        # ── Step 6: Build the hash chain link ─────────────────────────────────
        # If no previous hash was supplied, this is the first vote — label it
        # "GENESIS" (a common blockchain convention for the starting block).
        # The chain hash ties this ballot to the one before it, so deleting or
        # reordering votes breaks all subsequent hashes.
        prev_hash = previous_hash or "GENESIS"
        current_hash = self._generate_chain_hash(
            encrypted_ballot_b64,
            encrypted_aes_key_b64,
            election_id,
            prev_hash
        )

        # ── Step 7: Return the complete encrypted package ─────────────────────
        # Everything here gets stored in MongoDB as a single vote document.
        # Only the encrypted_ballot and encrypted_aes_key fields contain secret
        # data; the hashes are public and used for audit verification.
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
        # ── Step 1: Decode from base64 back to raw bytes ───────────────────────
        # MongoDB stores everything as strings; we reverse the base64 encoding
        # to get the raw ciphertext bytes back before we can decrypt.
        encrypted_ballot = base64.b64decode(encrypted_ballot_b64)
        encrypted_aes_key = base64.b64decode(encrypted_aes_key_b64)

        # ── Step 2: Decrypt the AES key using the RSA private key ─────────────
        # The RSA private key lives on disk (key_manager manages it).
        # This step recovers the original 32-byte AES session key.
        aes_key = self.key_manager.decrypt_aes_key(encrypted_aes_key)

        # ── Step 3: Recreate the AES cipher using the recovered key ───────────
        # We pass the recovered key explicitly so AESCipher uses it instead of
        # generating a new random one.
        aes_cipher = AESCipher(aes_key)

        # ── Step 4: Decrypt the ballot (AAD must match exactly) ───────────────
        # The election_id was used as AAD during encryption.  If a ballot was
        # copied from a different election and someone tries to decrypt it here,
        # the GCM authentication tag will not match and this line will raise.
        # decrypt_to_dict also JSON-parses the plaintext and returns a dict.
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
        # ── Recompute the hash from the stored data ────────────────────────────
        # We feed the exact same inputs that were used at encryption time into
        # _generate_chain_hash.  If any field was modified after storage the
        # computed hash will not match the stored one.
        computed_hash = self._generate_chain_hash(
            encrypted_ballot_b64,
            encrypted_aes_key_b64,
            election_id,
            previous_hash
        )
        # ── Compare computed vs claimed ────────────────────────────────────────
        # This is a plain equality check — if they differ, something was tampered.
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
        # ── Edge case: no votes yet ────────────────────────────────────────────
        # If the election has received zero votes, the chain is trivially valid.
        if not votes:
            return {'valid': True, 'verified_count': 0, 'details': []}

        results = []
        # ── Start the chain check from the GENESIS sentinel ───────────────────
        # The very first vote in every election must have previous_hash == "GENESIS".
        expected_previous = "GENESIS"

        # ── Walk every vote in chronological order ────────────────────────────
        for i, vote in enumerate(votes):
            # ── Check 1: Does recomputing this vote's hash match what's stored? ─
            # This detects any modification to the ballot ciphertext, the AES key,
            # or the hash fields themselves.
            hash_valid = self.verify_chain_link(
                vote['encrypted_ballot'],
                vote['encrypted_aes_key'],
                vote['election_id'],
                vote['previous_hash'],
                vote['current_hash']
            )

            # ── Check 2: Does this vote correctly reference the previous vote? ──
            # Even if a vote's own hash is valid, it might have been inserted
            # in the wrong position.  We verify continuity by checking that
            # previous_hash equals the hash of the vote immediately before it.
            chain_valid = vote['previous_hash'] == expected_previous

            is_valid = hash_valid and chain_valid

            results.append({
                'index': i,
                'hash_valid': hash_valid,
                'chain_valid': chain_valid,
                'valid': is_valid
            })

            # ── Short-circuit on first failure ────────────────────────────────
            # As soon as one link is broken, every subsequent link will also
            # fail (because their previous_hash expectations will be wrong).
            # We stop early and report which index was first corrupted.
            if not is_valid:
                return {
                    'valid': False,
                    'verified_count': i,  # number of votes verified BEFORE the break
                    'broken_at': i,       # index of the first bad link
                    'details': results
                }

            # ── Advance expected_previous for the next iteration ───────────────
            # The next vote must claim THIS vote's hash as its previous_hash.
            expected_previous = vote['current_hash']

        # ── All votes passed both checks — chain is intact ────────────────────
        return {
            'valid': True,
            'verified_count': len(votes),
            'details': results
        }

    def _prepare_ballot_data(self, ballot_data: Dict[str, Any]) -> Dict[str, Any]:
        """Prepare ballot data for encryption (handle datetime serialization)."""
        # ── Convert any datetime objects to ISO-8601 strings ──────────────────
        # Python datetime objects can't be directly serialised to JSON, which
        # is the format AESCipher uses internally.  We convert them here so the
        # encryption step always receives a JSON-serialisable dictionary.
        prepared = {}
        for key, value in ballot_data.items():
            if isinstance(value, datetime):
                prepared[key] = value.isoformat()  # e.g. "2025-03-01T09:00:00+00:00"
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
        # ── Build a deterministic JSON string from all four inputs ─────────────
        # sort_keys=True ensures the JSON key order is always the same regardless
        # of dictionary insertion order — without this, the hash could differ
        # across Python versions or implementations.
        hash_input = json.dumps({
            'encrypted_ballot': encrypted_ballot,
            'encrypted_aes_key': encrypted_aes_key,
            'election_id': election_id,
            'previous_hash': previous_hash
        }, sort_keys=True)

        # ── Hash the JSON string with SHA-256 ─────────────────────────────────
        # SHA-256 produces a 256-bit (32-byte) digest, returned as a 64-character
        # lowercase hex string.  This is what gets stored in current_hash and
        # referenced by the next vote's previous_hash.
        return hashlib.sha256(hash_input.encode()).hexdigest()


# ── Module-level singleton ─────────────────────────────────────────────────────
# Rather than creating a new BallotCrypto (and loading the RSA keys from disk)
# on every single request, we keep one shared instance alive for the lifetime
# of the process.  get_ballot_crypto() is called once from app.py at startup.
_default_ballot_crypto = None

def get_ballot_crypto() -> BallotCrypto:
    """Get or create the default BallotCrypto instance."""
    global _default_ballot_crypto
    # ── Lazy initialisation — create it the first time it's requested ──────────
    if _default_ballot_crypto is None:
        _default_ballot_crypto = BallotCrypto()
    return _default_ballot_crypto
