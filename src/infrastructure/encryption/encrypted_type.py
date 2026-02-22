"""SQLAlchemy custom type for transparent field encryption."""

from sqlalchemy import String, TypeDecorator


class EncryptedString(TypeDecorator):
    impl = String
    cache_ok = True

    def __init__(self, length=None, **kwargs):
        super().__init__(length=length or 512, **kwargs)
        self._encryptor = None

    @property
    def encryptor(self):
        if self._encryptor is None:
            from src.infrastructure.encryption.field_encryption import FieldEncryptor

            self._encryptor = FieldEncryptor()
        return self._encryptor

    def process_bind_param(self, value, dialect):
        if value is not None:
            return self.encryptor.encrypt(str(value))
        return value

    def process_result_value(self, value, dialect):
        if value is not None:
            return self.encryptor.decrypt(value)
        return value
