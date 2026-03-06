"""
SecureVote AES-256-GCM Cipher
=============================
Provides authenticated encryption for ballot data.

Why AES-256-GCM?
- AES-256: Military-grade 256-bit encryption
- GCM Mode: Provides both confidentiality AND authenticity
- Authentication: Detects any tampering with ciphertext
- Performance: Hardware-accelerated on modern CPUs

Security Notes:
- Never reuse (key, nonce) pairs
- Each encryption generates a unique random nonce
- Authentication tag prevents ciphertext modification
"""

import os
import json
import base64
from typing import Tuple, Union
from cryptography.hazmat.primitives.ciphers.aead import AESGCM


class AESCipher:
    """
    AES-256-GCM cipher for encrypting ballot data.

    Each encryption:
    1. Generates a new random 96-bit nonce
    2. Encrypts plaintext with authentication
    3. Returns nonce + ciphertext (for storage)
    """

    KEY_SIZE = 32  # 256 bits
    NONCE_SIZE = 12  # 96 bits (recommended for GCM)

    def __init__(self, key: bytes = None):
        """
        Initialize AES cipher.

        Args:
            key: 32-byte AES key. If None, generates a new random key.
        """
        if key is None:
            key = self.generate_key()
        elif len(key) != self.KEY_SIZE:
            raise ValueError(f"AES key must be {self.KEY_SIZE} bytes (got {len(key)})")

        self._key = key
        self._cipher = AESGCM(key)

    @classmethod
    def generate_key(cls) -> bytes:
        """
        Generate a cryptographically secure random AES-256 key.

        Returns:
            32-byte random key.
        """
        return os.urandom(cls.KEY_SIZE)

    @property
    def key(self) -> bytes:
        """Get the AES key (for RSA encryption)."""
        return self._key

    def encrypt(self, plaintext: Union[str, bytes, dict],
                associated_data: bytes = None) -> bytes:
        """
        Encrypt data using AES-256-GCM.

        Args:
            plaintext: Data to encrypt (str, bytes, or dict).
                      Dicts are JSON-serialized automatically.
            associated_data: Optional additional authenticated data (AAD).
                            This data is authenticated but NOT encrypted.
                            Useful for metadata like election_id.

        Returns:
            Combined nonce + ciphertext bytes.
            Format: [12-byte nonce][ciphertext + 16-byte auth tag]
        """
        # Convert plaintext to bytes
        if isinstance(plaintext, dict):
            plaintext = json.dumps(plaintext, sort_keys=True, default=str)
        if isinstance(plaintext, str):
            plaintext = plaintext.encode('utf-8')

        # Generate unique nonce for this encryption
        nonce = os.urandom(self.NONCE_SIZE)

        # Encrypt with authentication
        ciphertext = self._cipher.encrypt(nonce, plaintext, associated_data)

        # Return nonce prepended to ciphertext
        return nonce + ciphertext

    def decrypt(self, encrypted_data: bytes,
                associated_data: bytes = None) -> bytes:
        """
        Decrypt AES-256-GCM encrypted data.

        Args:
            encrypted_data: Combined nonce + ciphertext from encrypt().
            associated_data: Must match the AAD used during encryption.

        Returns:
            Decrypted plaintext bytes.

        Raises:
            cryptography.exceptions.InvalidTag: If authentication fails
                (data was tampered with).
        """
        if len(encrypted_data) < self.NONCE_SIZE + 16:  # 16 = auth tag size
            raise ValueError("Encrypted data too short")

        # Extract nonce and ciphertext
        nonce = encrypted_data[:self.NONCE_SIZE]
        ciphertext = encrypted_data[self.NONCE_SIZE:]

        # Decrypt and verify authentication tag
        plaintext = self._cipher.decrypt(nonce, ciphertext, associated_data)
        return plaintext

    def decrypt_to_string(self, encrypted_data: bytes,
                          associated_data: bytes = None) -> str:
        """Decrypt and return as UTF-8 string."""
        return self.decrypt(encrypted_data, associated_data).decode('utf-8')

    def decrypt_to_dict(self, encrypted_data: bytes,
                        associated_data: bytes = None) -> dict:
        """Decrypt and parse as JSON dict."""
        plaintext = self.decrypt_to_string(encrypted_data, associated_data)
        return json.loads(plaintext)


def encrypt_bytes_to_base64(cipher: AESCipher, plaintext: Union[str, bytes, dict],
                            associated_data: bytes = None) -> str:
    """
    Convenience function: Encrypt and return base64-encoded string.
    Useful for storing in MongoDB or transmitting via JSON.
    """
    encrypted = cipher.encrypt(plaintext, associated_data)
    return base64.b64encode(encrypted).decode('ascii')


def decrypt_base64_to_bytes(cipher: AESCipher, b64_data: str,
                            associated_data: bytes = None) -> bytes:
    """
    Convenience function: Decode base64 and decrypt.
    """
    encrypted = base64.b64decode(b64_data)
    return cipher.decrypt(encrypted, associated_data)


def decrypt_base64_to_dict(cipher: AESCipher, b64_data: str,
                           associated_data: bytes = None) -> dict:
    """
    Convenience function: Decode base64, decrypt, and parse JSON.
    """
    encrypted = base64.b64decode(b64_data)
    return cipher.decrypt_to_dict(encrypted, associated_data)
