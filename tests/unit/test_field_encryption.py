"""Tests for PII field encryption."""
import pytest
import os


class TestFieldEncryption:
    def test_encrypt_decrypt_roundtrip(self):
        from cryptography.fernet import Fernet

        key = Fernet.generate_key().decode()
        os.environ["FIELD_ENCRYPTION_KEY"] = key

        from src.infrastructure.encryption.field_encryption import FieldEncryptor

        enc = FieldEncryptor(key=key)

        plaintext = "user@example.com"
        ciphertext = enc.encrypt(plaintext)
        assert ciphertext != plaintext
        assert enc.decrypt(ciphertext) == plaintext

        del os.environ["FIELD_ENCRYPTION_KEY"]

    def test_encrypt_empty_string(self):
        from cryptography.fernet import Fernet

        key = Fernet.generate_key().decode()
        from src.infrastructure.encryption.field_encryption import FieldEncryptor

        enc = FieldEncryptor(key=key)
        assert enc.encrypt("") == ""
        assert enc.decrypt("") == ""

    def test_decrypt_unencrypted_returns_as_is(self):
        from cryptography.fernet import Fernet

        key = Fernet.generate_key().decode()
        from src.infrastructure.encryption.field_encryption import FieldEncryptor

        enc = FieldEncryptor(key=key)
        result = enc.decrypt("not-encrypted-text")
        assert result == "not-encrypted-text"
