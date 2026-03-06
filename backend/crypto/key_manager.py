"""
SecureVote RSA Key Manager
==========================
Handles RSA-2048 key pair generation, storage, and loading.
Used to encrypt/decrypt AES session keys for ballot protection.

Security Notes:
- Private key should NEVER be exposed or transmitted
- Keys are stored in PEM format
- Uses OAEP padding (optimal asymmetric encryption padding)
"""

import os
from pathlib import Path
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import rsa, padding
from cryptography.hazmat.backends import default_backend
from dotenv import load_dotenv

load_dotenv()


class KeyManager:
    """
    Manages RSA key pair for SecureVote.

    RSA is used to encrypt AES session keys, not ballot data directly.
    This hybrid approach combines RSA security with AES performance.
    """

    RSA_KEY_SIZE = 2048
    PUBLIC_EXPONENT = 65537

    def __init__(self, keys_dir: str = None, passphrase: str = None):
        """
        Initialize KeyManager with a directory for key storage.

        Args:
            keys_dir: Directory path to store/load keys.
                     Defaults to 'keys/' in backend directory.
            passphrase: Optional passphrase for private key encryption.
                       Defaults to RSA_KEY_PASSPHRASE env var if set.
        """
        if keys_dir is None:
            # Default to backend/keys/ directory
            backend_dir = Path(__file__).parent.parent
            keys_dir = backend_dir / 'keys'

        self.keys_dir = Path(keys_dir)
        self.keys_dir.mkdir(parents=True, exist_ok=True)

        self.private_key_path = self.keys_dir / 'private_key.pem'
        self.public_key_path = self.keys_dir / 'public_key.pem'

        # Resolve passphrase: explicit param > env var > None
        if passphrase is not None:
            self._passphrase = passphrase.encode('utf-8') if passphrase else None
        else:
            env_passphrase = os.getenv('RSA_KEY_PASSPHRASE')
            self._passphrase = env_passphrase.encode('utf-8') if env_passphrase else None

        self._private_key = None
        self._public_key = None

    def generate_keys(self, overwrite: bool = False) -> bool:
        """
        Generate a new RSA key pair.

        Args:
            overwrite: If True, overwrites existing keys. Default False.

        Returns:
            True if keys were generated, False if keys exist and overwrite=False.

        Raises:
            RuntimeError: If key generation fails.
        """
        if self.keys_exist() and not overwrite:
            return False

        try:
            # Generate private key
            private_key = rsa.generate_private_key(
                public_exponent=self.PUBLIC_EXPONENT,
                key_size=self.RSA_KEY_SIZE,
                backend=default_backend()
            )

            # Extract public key
            public_key = private_key.public_key()

            # Serialize and save private key
            if self._passphrase:
                encryption_algo = serialization.BestAvailableEncryption(self._passphrase)
            else:
                encryption_algo = serialization.NoEncryption()

            private_pem = private_key.private_bytes(
                encoding=serialization.Encoding.PEM,
                format=serialization.PrivateFormat.PKCS8,
                encryption_algorithm=encryption_algo
            )

            # Serialize and save public key
            public_pem = public_key.public_bytes(
                encoding=serialization.Encoding.PEM,
                format=serialization.PublicFormat.SubjectPublicKeyInfo
            )

            # Write keys to files
            self.private_key_path.write_bytes(private_pem)
            self.public_key_path.write_bytes(public_pem)

            # Set restrictive permissions on private key (Unix only)
            if os.name != 'nt':  # Not Windows
                os.chmod(self.private_key_path, 0o600)

            # Cache the keys
            self._private_key = private_key
            self._public_key = public_key

            return True

        except Exception as e:
            raise RuntimeError(f"Failed to generate RSA keys: {e}")

    def keys_exist(self) -> bool:
        """Check if both key files exist."""
        return self.private_key_path.exists() and self.public_key_path.exists()

    def load_private_key(self):
        """
        Load the private key from file.

        Returns:
            RSA private key object.

        Raises:
            FileNotFoundError: If private key file doesn't exist.
        """
        if self._private_key is not None:
            return self._private_key

        if not self.private_key_path.exists():
            raise FileNotFoundError(
                f"Private key not found at {self.private_key_path}. "
                "Run generate_keys() first."
            )

        private_pem = self.private_key_path.read_bytes()
        self._private_key = serialization.load_pem_private_key(
            private_pem,
            password=self._passphrase,
            backend=default_backend()
        )
        return self._private_key

    def load_public_key(self):
        """
        Load the public key from file.

        Returns:
            RSA public key object.

        Raises:
            FileNotFoundError: If public key file doesn't exist.
        """
        if self._public_key is not None:
            return self._public_key

        if not self.public_key_path.exists():
            raise FileNotFoundError(
                f"Public key not found at {self.public_key_path}. "
                "Run generate_keys() first."
            )

        public_pem = self.public_key_path.read_bytes()
        self._public_key = serialization.load_pem_public_key(
            public_pem,
            backend=default_backend()
        )
        return self._public_key

    def encrypt_aes_key(self, aes_key: bytes) -> bytes:
        """
        Encrypt an AES key using RSA public key.

        Uses OAEP padding with SHA-256 for security.

        Args:
            aes_key: The AES key bytes to encrypt (typically 32 bytes for AES-256).

        Returns:
            Encrypted AES key as bytes.
        """
        public_key = self.load_public_key()

        encrypted_key = public_key.encrypt(
            aes_key,
            padding.OAEP(
                mgf=padding.MGF1(algorithm=hashes.SHA256()),
                algorithm=hashes.SHA256(),
                label=None
            )
        )
        return encrypted_key

    def decrypt_aes_key(self, encrypted_aes_key: bytes) -> bytes:
        """
        Decrypt an AES key using RSA private key.

        Args:
            encrypted_aes_key: The encrypted AES key bytes.

        Returns:
            Decrypted AES key as bytes.
        """
        private_key = self.load_private_key()

        decrypted_key = private_key.decrypt(
            encrypted_aes_key,
            padding.OAEP(
                mgf=padding.MGF1(algorithm=hashes.SHA256()),
                algorithm=hashes.SHA256(),
                label=None
            )
        )
        return decrypted_key

    def get_public_key_pem(self) -> str:
        """
        Get the public key in PEM format (for distribution/verification).

        Returns:
            Public key as PEM string.
        """
        public_key = self.load_public_key()
        pem_bytes = public_key.public_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PublicFormat.SubjectPublicKeyInfo
        )
        return pem_bytes.decode('utf-8')


# Module-level singleton for convenience
_default_key_manager = None

def get_key_manager() -> KeyManager:
    """Get or create the default KeyManager instance."""
    global _default_key_manager
    if _default_key_manager is None:
        _default_key_manager = KeyManager()
    return _default_key_manager
