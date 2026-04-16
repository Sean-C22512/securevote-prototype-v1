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

# os is used to generate cryptographically secure random bytes for the key and nonce
import os
# json is used to convert Python dictionaries to strings before encryption
import json
# base64 is used to encode binary encrypted data as safe text (for JSON/MongoDB storage)
import base64
# Tuple and Union allow us to type-hint return values and parameters more precisely
from typing import Tuple, Union
# AESGCM is the AES-256-GCM authenticated encryption algorithm from the cryptography library
from cryptography.hazmat.primitives.ciphers.aead import AESGCM


class AESCipher:
    """
    AES-256-GCM cipher for encrypting ballot data.

    Each encryption:
    1. Generates a new random 96-bit nonce
    2. Encrypts plaintext with authentication
    3. Returns nonce + ciphertext (for storage)
    """

    # AES-256 requires a 32-byte (256-bit) key — this constant enforces that requirement
    KEY_SIZE = 32  # 256 bits
    # GCM mode works best with a 12-byte (96-bit) nonce — this is the NIST recommendation
    NONCE_SIZE = 12  # 96 bits (recommended for GCM)

    def __init__(self, key: bytes = None):
        """
        Initialize AES cipher.

        Args:
            key: 32-byte AES key. If None, generates a new random key.
        """
        # If no key was provided, generate a fresh random one
        if key is None:
            key = self.generate_key()
        # If a key was provided, make sure it is exactly the right length (32 bytes)
        elif len(key) != self.KEY_SIZE:
            # Raise an error immediately rather than silently using a wrong-length key
            raise ValueError(f"AES key must be {self.KEY_SIZE} bytes (got {len(key)})")

        # Store the key privately — the underscore prefix signals it should not be accessed directly
        self._key = key
        # Create the AESGCM cipher object that will handle all actual encrypt/decrypt operations
        self._cipher = AESGCM(key)

    @classmethod
    def generate_key(cls) -> bytes:
        """
        Generate a cryptographically secure random AES-256 key.

        Returns:
            32-byte random key.
        """
        # os.urandom uses the operating system's cryptographically secure random number generator
        # This is safe for generating encryption keys — do not use random.randbytes() for this
        return os.urandom(cls.KEY_SIZE)  # Returns 32 random bytes suitable for AES-256

    @property
    def key(self) -> bytes:
        """Get the AES key (for RSA encryption)."""
        # Property decorator makes this look like an attribute (cipher.key) rather than a method call
        # Used when we need to hand the raw key to the KeyManager for RSA encryption
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
        # If the caller passed a dictionary (e.g., a ballot), convert it to a JSON string first
        # sort_keys=True ensures the same dict always produces the same JSON string (deterministic)
        # default=str converts any non-serialisable types (like ObjectId) to their string representation
        if isinstance(plaintext, dict):
            plaintext = json.dumps(plaintext, sort_keys=True, default=str)
        # If the plaintext is a plain string, encode it to UTF-8 bytes for the cipher
        if isinstance(plaintext, str):
            plaintext = plaintext.encode('utf-8')

        # Generate a fresh random nonce for every single encryption operation
        # CRITICAL: reusing a (key, nonce) pair completely breaks GCM security
        nonce = os.urandom(self.NONCE_SIZE)  # 12 random bytes, unique for this encryption

        # Perform the actual AES-GCM encryption
        # The cipher automatically appends a 16-byte authentication tag to the end of the ciphertext
        # associated_data (if provided) is mixed into the tag but does NOT get encrypted
        ciphertext = self._cipher.encrypt(nonce, plaintext, associated_data)

        # Prepend the nonce to the ciphertext so the receiver knows what nonce was used
        # The format stored/transmitted is: [12-byte nonce][encrypted bytes + 16-byte auth tag]
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
        # Sanity check: the data must be at least nonce (12 bytes) + auth tag (16 bytes) long
        # If it is shorter than this, it cannot possibly be valid encrypted data
        if len(encrypted_data) < self.NONCE_SIZE + 16:  # 16 = auth tag size
            raise ValueError("Encrypted data too short")

        # The first 12 bytes are the nonce that was prepended during encryption
        nonce = encrypted_data[:self.NONCE_SIZE]
        # Everything after the nonce is the actual ciphertext (including the 16-byte auth tag at the end)
        ciphertext = encrypted_data[self.NONCE_SIZE:]

        # Decrypt and simultaneously verify the authentication tag
        # If anything in the ciphertext or associated_data has been tampered with, this raises InvalidTag
        plaintext = self._cipher.decrypt(nonce, ciphertext, associated_data)
        # Return the original raw bytes of the plaintext
        return plaintext

    def decrypt_to_string(self, encrypted_data: bytes,
                          associated_data: bytes = None) -> str:
        """Decrypt and return as UTF-8 string."""
        # Decrypt to bytes first, then decode those bytes to a Python string using UTF-8
        return self.decrypt(encrypted_data, associated_data).decode('utf-8')

    def decrypt_to_dict(self, encrypted_data: bytes,
                        associated_data: bytes = None) -> dict:
        """Decrypt and parse as JSON dict."""
        # First decrypt the bytes to a UTF-8 string (which should be valid JSON)
        plaintext = self.decrypt_to_string(encrypted_data, associated_data)
        # Parse the JSON string back into a Python dictionary and return it
        return json.loads(plaintext)


def encrypt_bytes_to_base64(cipher: AESCipher, plaintext: Union[str, bytes, dict],
                            associated_data: bytes = None) -> str:
    """
    Convenience function: Encrypt and return base64-encoded string.
    Useful for storing in MongoDB or transmitting via JSON.
    """
    # Use the cipher object to encrypt the plaintext into raw bytes (nonce + ciphertext)
    encrypted = cipher.encrypt(plaintext, associated_data)
    # Base64-encode the raw bytes so they can be safely stored as a text string in JSON or MongoDB
    # .decode('ascii') converts the base64 bytes to a regular Python string
    return base64.b64encode(encrypted).decode('ascii')


def decrypt_base64_to_bytes(cipher: AESCipher, b64_data: str,
                            associated_data: bytes = None) -> bytes:
    """
    Convenience function: Decode base64 and decrypt.
    """
    # First reverse the base64 encoding to get back the raw encrypted bytes
    encrypted = base64.b64decode(b64_data)
    # Decrypt the raw bytes and return the plaintext as bytes
    return cipher.decrypt(encrypted, associated_data)


def decrypt_base64_to_dict(cipher: AESCipher, b64_data: str,
                           associated_data: bytes = None) -> dict:
    """
    Convenience function: Decode base64, decrypt, and parse JSON.
    """
    # First reverse the base64 encoding to get the raw encrypted bytes
    encrypted = base64.b64decode(b64_data)
    # Decrypt the bytes and parse the result as a JSON dictionary in one step
    return cipher.decrypt_to_dict(encrypted, associated_data)
