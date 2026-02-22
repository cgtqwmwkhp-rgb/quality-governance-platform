"""Field-level encryption for PII data using Fernet symmetric encryption."""

import base64
import os
from typing import Optional

class FieldEncryptor:
    """Encrypts/decrypts PII fields using Fernet (AES-128-CBC)."""
    
    def __init__(self, key: Optional[str] = None):
        # Load key from env var FIELD_ENCRYPTION_KEY or parameter
        self._key = key or os.environ.get("FIELD_ENCRYPTION_KEY", "")
        if not self._key:
            # Generate a development key (NOT for production)
            from cryptography.fernet import Fernet
            self._key = Fernet.generate_key().decode()
        self._init_cipher()
    
    def _init_cipher(self):
        from cryptography.fernet import Fernet, MultiFernet
        keys = self._key.split(",")  # Support key rotation via comma-separated keys
        fernets = [Fernet(k.strip().encode() if isinstance(k, str) else k) for k in keys]
        self._cipher = MultiFernet(fernets) if len(fernets) > 1 else fernets[0]
    
    def encrypt(self, plaintext: str) -> str:
        if not plaintext:
            return plaintext
        return self._cipher.encrypt(plaintext.encode()).decode()
    
    def decrypt(self, ciphertext: str) -> str:
        if not ciphertext:
            return ciphertext
        try:
            return self._cipher.decrypt(ciphertext.encode()).decode()
        except Exception:
            return ciphertext  # Return as-is if not encrypted (migration safety)
    
    def rotate(self, ciphertext: str) -> str:
        if not ciphertext:
            return ciphertext
        from cryptography.fernet import MultiFernet
        if isinstance(self._cipher, MultiFernet):
            return self._cipher.rotate(ciphertext.encode()).decode()
        return ciphertext
