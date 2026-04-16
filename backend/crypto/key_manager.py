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

# os gives us access to environment variables and file system operations
import os
# Path makes it easy to work with file and directory paths in a cross-platform way
from pathlib import Path
# hashes gives us SHA-256 for use inside the padding scheme
# serialization lets us convert key objects to/from bytes that can be saved in files
from cryptography.hazmat.primitives import hashes, serialization
# rsa lets us generate RSA key pairs; padding defines how the data is padded before encryption
from cryptography.hazmat.primitives.asymmetric import rsa, padding
# default_backend is the underlying cryptography engine used to perform the actual operations
from cryptography.hazmat.backends import default_backend
# load_dotenv reads a .env file and puts its values into the environment
from dotenv import load_dotenv

# Load any environment variables from the .env file into the process at startup
load_dotenv()


class KeyManager:
    """
    Manages RSA key pair for SecureVote.

    RSA is used to encrypt AES session keys, not ballot data directly.
    This hybrid approach combines RSA security with AES performance.
    """

    # RSA key size in bits — 2048 is the current industry-standard minimum for security
    RSA_KEY_SIZE = 2048
    # 65537 is the standard public exponent used in RSA — it is fast and cryptographically safe
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
        # If no keys directory was provided by the caller, we choose a sensible default
        if keys_dir is None:
            # __file__ is this file (key_manager.py); .parent.parent walks up to the backend/ folder
            backend_dir = Path(__file__).parent.parent
            # Store keys in a subfolder called 'keys' inside the backend directory
            keys_dir = backend_dir / 'keys'

        # Store the keys directory as a proper Path object for easy path manipulation
        self.keys_dir = Path(keys_dir)
        # Create the directory if it does not already exist; parents=True creates any missing parent folders
        self.keys_dir.mkdir(parents=True, exist_ok=True)

        # Build the full file paths for where each key file will live on disk
        self.private_key_path = self.keys_dir / 'private_key.pem'  # Private key file path
        self.public_key_path = self.keys_dir / 'public_key.pem'    # Public key file path

        # Resolve which passphrase to use: explicit argument takes priority over env var
        # Passphrase is used to password-protect the private key file on disk
        if passphrase is not None:
            # If a passphrase string was passed in, encode it to bytes (cryptography library needs bytes)
            self._passphrase = passphrase.encode('utf-8') if passphrase else None
        else:
            # Fall back to reading the passphrase from the RSA_KEY_PASSPHRASE environment variable
            env_passphrase = os.getenv('RSA_KEY_PASSPHRASE')
            # Encode to bytes if the variable is set; otherwise leave as None (no passphrase)
            self._passphrase = env_passphrase.encode('utf-8') if env_passphrase else None

        # These will cache the loaded key objects so we don't re-read the files every time
        self._private_key = None  # Will hold the in-memory private key object once loaded
        self._public_key = None   # Will hold the in-memory public key object once loaded

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
        # Safety check: if keys already exist and overwrite was not requested, do nothing
        if self.keys_exist() and not overwrite:
            return False  # Return False to signal that no new keys were created

        try:
            # Ask the cryptography library to generate a brand-new RSA private key
            # The public exponent and key size are set by our class constants above
            private_key = rsa.generate_private_key(
                public_exponent=self.PUBLIC_EXPONENT,  # Standard exponent 65537
                key_size=self.RSA_KEY_SIZE,            # 2048-bit key for security
                backend=default_backend()              # Use the system's crypto backend
            )

            # The public key is mathematically derived from the private key
            # It is safe to share publicly — it can only encrypt, not decrypt
            public_key = private_key.public_key()

            # Decide how to protect the private key when saving it to disk
            if self._passphrase:
                # If a passphrase is set, encrypt the private key file with it
                encryption_algo = serialization.BestAvailableEncryption(self._passphrase)
            else:
                # If no passphrase is set, save the private key without any extra encryption
                encryption_algo = serialization.NoEncryption()

            # Convert the private key object into PEM bytes (a text-based format beginning with -----BEGIN...)
            # PKCS8 is the standard format for storing private keys
            private_pem = private_key.private_bytes(
                encoding=serialization.Encoding.PEM,           # Output as PEM text format
                format=serialization.PrivateFormat.PKCS8,      # Use PKCS8 standard structure
                encryption_algorithm=encryption_algo           # Apply passphrase protection if set
            )

            # Convert the public key object into PEM bytes using SubjectPublicKeyInfo format
            # This is the standard X.509 format for distributing public keys
            public_pem = public_key.public_bytes(
                encoding=serialization.Encoding.PEM,                        # Output as PEM text format
                format=serialization.PublicFormat.SubjectPublicKeyInfo      # Standard public key structure
            )

            # Write the private key bytes to the private key file on disk
            self.private_key_path.write_bytes(private_pem)
            # Write the public key bytes to the public key file on disk
            self.public_key_path.write_bytes(public_pem)

            # On Unix/Linux/Mac systems, restrict the private key file so only the owner can read it
            # os.name != 'nt' means "not Windows" — Windows uses a different permission system
            if os.name != 'nt':
                # 0o600 in octal = owner read+write only; no group or world access
                os.chmod(self.private_key_path, 0o600)

            # Cache the newly generated key objects in memory to avoid unnecessary file reads later
            self._private_key = private_key  # Store private key object in memory
            self._public_key = public_key    # Store public key object in memory

            # Return True to signal that keys were successfully generated and saved
            return True

        except Exception as e:
            # If anything goes wrong during generation, wrap the error in a clear message
            raise RuntimeError(f"Failed to generate RSA keys: {e}")

    def keys_exist(self) -> bool:
        """Check if both key files exist."""
        # Both files must exist on disk for the system to be considered ready
        return self.private_key_path.exists() and self.public_key_path.exists()

    def load_private_key(self):
        """
        Load the private key from file.

        Returns:
            RSA private key object.

        Raises:
            FileNotFoundError: If private key file doesn't exist.
        """
        # If we already loaded the key into memory previously, return the cached version
        # This avoids reading the file from disk on every call
        if self._private_key is not None:
            return self._private_key

        # If the private key file does not exist on disk, raise an informative error
        if not self.private_key_path.exists():
            raise FileNotFoundError(
                f"Private key not found at {self.private_key_path}. "
                "Run generate_keys() first."
            )

        # Read the raw bytes of the PEM file from disk
        private_pem = self.private_key_path.read_bytes()
        # Parse the PEM bytes back into a usable private key object
        # We pass the passphrase so the library can decrypt the file if it was protected
        self._private_key = serialization.load_pem_private_key(
            private_pem,                     # The raw PEM bytes read from disk
            password=self._passphrase,       # Passphrase to decrypt the key file (None if unprotected)
            backend=default_backend()        # Cryptography backend to use
        )
        # Return the loaded private key object to the caller
        return self._private_key

    def load_public_key(self):
        """
        Load the public key from file.

        Returns:
            RSA public key object.

        Raises:
            FileNotFoundError: If public key file doesn't exist.
        """
        # If the public key is already in memory, return it directly without re-reading the file
        if self._public_key is not None:
            return self._public_key

        # If the public key file is missing, raise an informative error
        if not self.public_key_path.exists():
            raise FileNotFoundError(
                f"Public key not found at {self.public_key_path}. "
                "Run generate_keys() first."
            )

        # Read the raw PEM bytes from the public key file on disk
        public_pem = self.public_key_path.read_bytes()
        # Parse the PEM bytes into a usable public key object
        # Public keys don't need a passphrase because they are not secret
        self._public_key = serialization.load_pem_public_key(
            public_pem,               # The raw PEM bytes read from disk
            backend=default_backend() # Cryptography backend to use
        )
        # Return the loaded public key object to the caller
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
        # Load (or retrieve from cache) the RSA public key
        public_key = self.load_public_key()

        # Encrypt the raw AES key bytes using the RSA public key
        # OAEP (Optimal Asymmetric Encryption Padding) is the secure modern padding scheme for RSA
        encrypted_key = public_key.encrypt(
            aes_key,            # The 32-byte AES session key we want to protect
            padding.OAEP(
                # MGF1 (Mask Generation Function 1) uses SHA-256 to generate the padding mask
                mgf=padding.MGF1(algorithm=hashes.SHA256()),
                # SHA-256 is also used as the main hash for the OAEP scheme itself
                algorithm=hashes.SHA256(),
                # label is optional metadata — we don't use it here so it is set to None
                label=None
            )
        )
        # Return the RSA-encrypted AES key — this is what gets stored alongside the ballot
        return encrypted_key

    def decrypt_aes_key(self, encrypted_aes_key: bytes) -> bytes:
        """
        Decrypt an AES key using RSA private key.

        Args:
            encrypted_aes_key: The encrypted AES key bytes.

        Returns:
            Decrypted AES key as bytes.
        """
        # Load (or retrieve from cache) the RSA private key — only the server holds this
        private_key = self.load_private_key()

        # Decrypt the encrypted AES key using the RSA private key
        # We must use exactly the same OAEP padding settings that were used during encryption
        decrypted_key = private_key.decrypt(
            encrypted_aes_key,  # The RSA-encrypted AES key we want to recover
            padding.OAEP(
                # MGF1 with SHA-256 must match what was used to encrypt
                mgf=padding.MGF1(algorithm=hashes.SHA256()),
                # SHA-256 hash algorithm must also match
                algorithm=hashes.SHA256(),
                # No label was used during encryption, so None here too
                label=None
            )
        )
        # Return the original 32-byte AES key, now recovered and ready for ballot decryption
        return decrypted_key

    def get_public_key_pem(self) -> str:
        """
        Get the public key in PEM format (for distribution/verification).

        Returns:
            Public key as PEM string.
        """
        # Load the public key object (from cache or file)
        public_key = self.load_public_key()
        # Serialize the key object back into PEM-format bytes
        pem_bytes = public_key.public_bytes(
            encoding=serialization.Encoding.PEM,                       # Output as PEM text format
            format=serialization.PublicFormat.SubjectPublicKeyInfo     # Standard X.509 structure
        )
        # Decode the bytes to a plain Python string so it can be returned in JSON or printed
        return pem_bytes.decode('utf-8')


# Module-level singleton — one shared KeyManager instance for the whole application
# Starts as None; gets created the first time get_key_manager() is called
_default_key_manager = None

def get_key_manager() -> KeyManager:
    """Get or create the default KeyManager instance."""
    # global tells Python we are modifying the module-level variable, not creating a local one
    global _default_key_manager
    # Only create the KeyManager if one does not already exist (singleton pattern)
    if _default_key_manager is None:
        # Instantiate with default settings — keys directory and passphrase come from env vars
        _default_key_manager = KeyManager()
    # Return the single shared instance (already created or just created above)
    return _default_key_manager
