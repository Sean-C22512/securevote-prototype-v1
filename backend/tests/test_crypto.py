"""
SecureVote Cryptographic Module Tests
=====================================
Unit tests for AES-256-GCM encryption, RSA key management,
and the high-level BallotCrypto API.

Run with: pytest tests/test_crypto.py -v
"""

import pytest
import os
import tempfile
import shutil
from datetime import datetime, timezone

# Import crypto modules
from crypto.key_manager import KeyManager
from crypto.aes_cipher import AESCipher
from crypto.ballot_crypto import BallotCrypto


class TestAESCipher:
    """Tests for AES-256-GCM encryption."""

    def test_key_generation(self):
        """Test that AES keys are generated with correct size."""
        key = AESCipher.generate_key()
        assert len(key) == 32  # 256 bits

    def test_encrypt_decrypt_string(self):
        """Test encryption and decryption of string data."""
        cipher = AESCipher()
        plaintext = "Hello, SecureVote!"

        encrypted = cipher.encrypt(plaintext)
        decrypted = cipher.decrypt_to_string(encrypted)

        assert decrypted == plaintext

    def test_encrypt_decrypt_dict(self):
        """Test encryption and decryption of dictionary data."""
        cipher = AESCipher()
        data = {
            'candidate_id': 1,
            'candidate': 'Candidate A',
            'student_id': '12345'
        }

        encrypted = cipher.encrypt(data)
        decrypted = cipher.decrypt_to_dict(encrypted)

        assert decrypted == data

    def test_encrypt_decrypt_with_aad(self):
        """Test that AAD (Associated Authenticated Data) works correctly."""
        cipher = AESCipher()
        plaintext = "Secret ballot data"
        aad = b"ELECTION-2025-001"

        encrypted = cipher.encrypt(plaintext, associated_data=aad)
        decrypted = cipher.decrypt_to_string(encrypted, associated_data=aad)

        assert decrypted == plaintext

    def test_aad_mismatch_raises_error(self):
        """Test that wrong AAD causes authentication failure."""
        cipher = AESCipher()
        plaintext = "Secret ballot data"
        aad_encrypt = b"ELECTION-2025-001"
        aad_decrypt = b"WRONG-ELECTION-ID"

        encrypted = cipher.encrypt(plaintext, associated_data=aad_encrypt)

        with pytest.raises(Exception):  # InvalidTag from cryptography
            cipher.decrypt(encrypted, associated_data=aad_decrypt)

    def test_unique_nonces(self):
        """Test that each encryption uses a unique nonce."""
        cipher = AESCipher()
        plaintext = "Same message"

        encrypted1 = cipher.encrypt(plaintext)
        encrypted2 = cipher.encrypt(plaintext)

        # First 12 bytes are the nonce - they should be different
        nonce1 = encrypted1[:12]
        nonce2 = encrypted2[:12]

        assert nonce1 != nonce2

    def test_invalid_key_size(self):
        """Test that invalid key sizes are rejected."""
        with pytest.raises(ValueError):
            AESCipher(key=b"too_short")

    def test_tamper_detection(self):
        """Test that tampered ciphertext is detected."""
        cipher = AESCipher()
        plaintext = "Original message"

        encrypted = cipher.encrypt(plaintext)

        # Tamper with the ciphertext (flip a bit in the middle)
        tampered = bytearray(encrypted)
        tampered[20] ^= 0xFF
        tampered = bytes(tampered)

        with pytest.raises(Exception):  # InvalidTag
            cipher.decrypt(tampered)


class TestKeyManager:
    """Tests for RSA key management."""

    @pytest.fixture
    def temp_keys_dir(self):
        """Create a temporary directory for key storage."""
        temp_dir = tempfile.mkdtemp()
        yield temp_dir
        shutil.rmtree(temp_dir)

    def test_key_generation(self, temp_keys_dir):
        """Test RSA key pair generation."""
        km = KeyManager(keys_dir=temp_keys_dir)

        assert not km.keys_exist()
        result = km.generate_keys()
        assert result is True
        assert km.keys_exist()

    def test_key_generation_no_overwrite(self, temp_keys_dir):
        """Test that keys are not overwritten by default."""
        km = KeyManager(keys_dir=temp_keys_dir)
        km.generate_keys()

        # Second generation should return False (keys exist)
        result = km.generate_keys(overwrite=False)
        assert result is False

    def test_key_generation_with_overwrite(self, temp_keys_dir):
        """Test that keys can be overwritten when requested."""
        km = KeyManager(keys_dir=temp_keys_dir)
        km.generate_keys()

        # Get original public key
        original_pem = km.get_public_key_pem()

        # Force regeneration
        km._private_key = None
        km._public_key = None
        result = km.generate_keys(overwrite=True)
        assert result is True

        # New key should be different
        new_pem = km.get_public_key_pem()
        assert original_pem != new_pem

    def test_encrypt_decrypt_aes_key(self, temp_keys_dir):
        """Test RSA encryption/decryption of AES keys."""
        km = KeyManager(keys_dir=temp_keys_dir)
        km.generate_keys()

        # Generate a random AES key
        aes_key = os.urandom(32)

        # Encrypt and decrypt
        encrypted = km.encrypt_aes_key(aes_key)
        decrypted = km.decrypt_aes_key(encrypted)

        assert decrypted == aes_key

    def test_load_keys_from_file(self, temp_keys_dir):
        """Test that keys can be loaded from files."""
        km1 = KeyManager(keys_dir=temp_keys_dir)
        km1.generate_keys()
        original_pem = km1.get_public_key_pem()

        # Create new instance (simulates app restart)
        km2 = KeyManager(keys_dir=temp_keys_dir)
        loaded_pem = km2.get_public_key_pem()

        assert original_pem == loaded_pem

    def test_missing_private_key_raises_error(self, temp_keys_dir):
        """Test that missing private key raises appropriate error."""
        km = KeyManager(keys_dir=temp_keys_dir)

        with pytest.raises(FileNotFoundError):
            km.load_private_key()


class TestBallotCrypto:
    """Tests for high-level ballot encryption API."""

    @pytest.fixture
    def temp_keys_dir(self):
        """Create a temporary directory for key storage."""
        temp_dir = tempfile.mkdtemp()
        yield temp_dir
        shutil.rmtree(temp_dir)

    @pytest.fixture
    def ballot_crypto(self, temp_keys_dir):
        """Create BallotCrypto instance with temp keys."""
        km = KeyManager(keys_dir=temp_keys_dir)
        return BallotCrypto(key_manager=km)

    def test_encrypt_decrypt_ballot(self, ballot_crypto):
        """Test full ballot encryption/decryption cycle."""
        ballot_data = {
            'candidate_id': 1,
            'candidate': 'Candidate A',
            'student_id': '12345'
        }
        election_id = 'ELEC-2025-001'

        # Encrypt
        encrypted = ballot_crypto.encrypt_ballot(ballot_data, election_id)

        assert 'encrypted_ballot' in encrypted
        assert 'encrypted_aes_key' in encrypted
        assert 'current_hash' in encrypted
        assert 'previous_hash' in encrypted
        assert encrypted['election_id'] == election_id

        # Decrypt
        decrypted = ballot_crypto.decrypt_ballot(
            encrypted['encrypted_ballot'],
            encrypted['encrypted_aes_key'],
            election_id
        )

        assert decrypted['candidate_id'] == ballot_data['candidate_id']
        assert decrypted['candidate'] == ballot_data['candidate']
        assert decrypted['student_id'] == ballot_data['student_id']

    def test_datetime_serialization(self, ballot_crypto):
        """Test that datetime objects are handled correctly."""
        ballot_data = {
            'candidate_id': 1,
            'candidate': 'Candidate A',
            'timestamp': datetime.now(timezone.utc)
        }
        election_id = 'ELEC-2025-001'

        encrypted = ballot_crypto.encrypt_ballot(ballot_data, election_id)
        decrypted = ballot_crypto.decrypt_ballot(
            encrypted['encrypted_ballot'],
            encrypted['encrypted_aes_key'],
            election_id
        )

        # Timestamp should be ISO format string
        assert isinstance(decrypted['timestamp'], str)

    def test_hash_chain_genesis(self, ballot_crypto):
        """Test first vote in chain uses GENESIS as previous hash."""
        ballot_data = {'candidate_id': 1, 'candidate': 'Candidate A'}

        encrypted = ballot_crypto.encrypt_ballot(ballot_data, 'ELEC-001')

        assert encrypted['previous_hash'] == 'GENESIS'
        assert len(encrypted['current_hash']) == 64  # SHA-256 hex

    def test_hash_chain_linking(self, ballot_crypto):
        """Test that votes are properly chain-linked."""
        election_id = 'ELEC-2025-001'

        # First vote
        vote1 = ballot_crypto.encrypt_ballot(
            {'candidate_id': 1, 'candidate': 'Candidate A'},
            election_id
        )

        # Second vote linked to first
        vote2 = ballot_crypto.encrypt_ballot(
            {'candidate_id': 2, 'candidate': 'Candidate B'},
            election_id,
            previous_hash=vote1['current_hash']
        )

        # Third vote linked to second
        vote3 = ballot_crypto.encrypt_ballot(
            {'candidate_id': 1, 'candidate': 'Candidate A'},
            election_id,
            previous_hash=vote2['current_hash']
        )

        assert vote1['previous_hash'] == 'GENESIS'
        assert vote2['previous_hash'] == vote1['current_hash']
        assert vote3['previous_hash'] == vote2['current_hash']

    def test_verify_chain_link_valid(self, ballot_crypto):
        """Test verification of a valid chain link."""
        ballot_data = {'candidate_id': 1, 'candidate': 'Candidate A'}
        election_id = 'ELEC-2025-001'

        encrypted = ballot_crypto.encrypt_ballot(ballot_data, election_id)

        is_valid = ballot_crypto.verify_chain_link(
            encrypted['encrypted_ballot'],
            encrypted['encrypted_aes_key'],
            encrypted['election_id'],
            encrypted['previous_hash'],
            encrypted['current_hash']
        )

        assert is_valid is True

    def test_verify_chain_link_tampered(self, ballot_crypto):
        """Test detection of tampered ballot data."""
        ballot_data = {'candidate_id': 1, 'candidate': 'Candidate A'}
        election_id = 'ELEC-2025-001'

        encrypted = ballot_crypto.encrypt_ballot(ballot_data, election_id)

        # Tamper with the encrypted ballot
        tampered_ballot = 'TAMPERED' + encrypted['encrypted_ballot'][8:]

        is_valid = ballot_crypto.verify_chain_link(
            tampered_ballot,
            encrypted['encrypted_aes_key'],
            encrypted['election_id'],
            encrypted['previous_hash'],
            encrypted['current_hash']
        )

        assert is_valid is False

    def test_verify_full_chain_valid(self, ballot_crypto):
        """Test verification of a complete valid chain."""
        election_id = 'ELEC-2025-001'
        votes = []

        # Create chain of 5 votes
        prev_hash = None
        for i in range(5):
            vote = ballot_crypto.encrypt_ballot(
                {'candidate_id': (i % 3) + 1, 'candidate': f'Candidate {chr(65 + i % 3)}'},
                election_id,
                previous_hash=prev_hash
            )
            votes.append(vote)
            prev_hash = vote['current_hash']

        result = ballot_crypto.verify_chain(votes)

        assert result['valid'] is True
        assert result['verified_count'] == 5

    def test_verify_full_chain_broken(self, ballot_crypto):
        """Test detection of a broken chain."""
        election_id = 'ELEC-2025-001'
        votes = []

        # Create chain of 5 votes
        prev_hash = None
        for i in range(5):
            vote = ballot_crypto.encrypt_ballot(
                {'candidate_id': (i % 3) + 1, 'candidate': f'Candidate {chr(65 + i % 3)}'},
                election_id,
                previous_hash=prev_hash
            )
            votes.append(vote)
            prev_hash = vote['current_hash']

        # Break the chain at vote 3 by changing its previous_hash
        votes[2]['previous_hash'] = 'BROKEN_HASH_VALUE'

        result = ballot_crypto.verify_chain(votes)

        assert result['valid'] is False
        assert result['broken_at'] == 2

    def test_wrong_election_id_decryption_fails(self, ballot_crypto):
        """Test that decryption with wrong election_id fails (AAD mismatch)."""
        ballot_data = {'candidate_id': 1, 'candidate': 'Candidate A'}

        encrypted = ballot_crypto.encrypt_ballot(ballot_data, 'ELEC-001')

        with pytest.raises(Exception):  # InvalidTag
            ballot_crypto.decrypt_ballot(
                encrypted['encrypted_ballot'],
                encrypted['encrypted_aes_key'],
                'WRONG-ELECTION-ID'
            )

    def test_empty_chain_is_valid(self, ballot_crypto):
        """Test that an empty chain is considered valid."""
        result = ballot_crypto.verify_chain([])

        assert result['valid'] is True
        assert result['verified_count'] == 0


class TestCryptoIntegration:
    """Integration tests combining all crypto components."""

    @pytest.fixture
    def temp_keys_dir(self):
        """Create a temporary directory for key storage."""
        temp_dir = tempfile.mkdtemp()
        yield temp_dir
        shutil.rmtree(temp_dir)

    def test_full_voting_workflow(self, temp_keys_dir):
        """Simulate a complete voting workflow with multiple ballots."""
        km = KeyManager(keys_dir=temp_keys_dir)
        crypto = BallotCrypto(key_manager=km)

        election_id = 'TUD-SU-ELECTION-2025'
        votes = []
        prev_hash = None

        # Simulate 10 votes
        ballots = [
            {'candidate_id': 1, 'candidate': 'Candidate A', 'student_id': 'C22512871'},
            {'candidate_id': 2, 'candidate': 'Candidate B', 'student_id': 'C22512872'},
            {'candidate_id': 1, 'candidate': 'Candidate A', 'student_id': 'C22512873'},
            {'candidate_id': 3, 'candidate': 'Candidate C', 'student_id': 'C22512874'},
            {'candidate_id': 1, 'candidate': 'Candidate A', 'student_id': 'C22512875'},
            {'candidate_id': 2, 'candidate': 'Candidate B', 'student_id': 'C22512876'},
            {'candidate_id': 2, 'candidate': 'Candidate B', 'student_id': 'C22512877'},
            {'candidate_id': 1, 'candidate': 'Candidate A', 'student_id': 'C22512878'},
            {'candidate_id': 3, 'candidate': 'Candidate C', 'student_id': 'C22512879'},
            {'candidate_id': 1, 'candidate': 'Candidate A', 'student_id': 'C22512880'},
        ]

        for ballot in ballots:
            encrypted = crypto.encrypt_ballot(
                ballot,
                election_id,
                previous_hash=prev_hash
            )
            votes.append(encrypted)
            prev_hash = encrypted['current_hash']

        # Verify entire chain
        chain_result = crypto.verify_chain(votes)
        assert chain_result['valid'] is True
        assert chain_result['verified_count'] == 10

        # Decrypt and tally
        tally = {}
        for vote in votes:
            decrypted = crypto.decrypt_ballot(
                vote['encrypted_ballot'],
                vote['encrypted_aes_key'],
                election_id
            )
            candidate = decrypted['candidate']
            tally[candidate] = tally.get(candidate, 0) + 1

        # Verify expected tally
        assert tally['Candidate A'] == 5
        assert tally['Candidate B'] == 3
        assert tally['Candidate C'] == 2
