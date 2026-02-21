"""Tests for PII scrubbing filter."""

import logging

import pytest

from src.infrastructure.logging.pii_filter import PIIFilter


class TestPIIFilter:
    """Tests for PIIFilter."""

    def setup_method(self):
        self.filter = PIIFilter()
        self.logger = logging.getLogger("test_pii")
        self.logger.addFilter(self.filter)

    def test_email_redaction(self):
        """Test email addresses are redacted."""
        record = logging.LogRecord("test", logging.INFO, "", 0, "User email is test@example.com", None, None)
        self.filter.filter(record)
        assert "[EMAIL_REDACTED]" in record.msg
        assert "test@example.com" not in record.msg

    def test_phone_redaction(self):
        """Test phone numbers are redacted."""
        record = logging.LogRecord("test", logging.INFO, "", 0, "Phone: 555-123-4567", None, None)
        self.filter.filter(record)
        assert "[PHONE_REDACTED]" in record.msg
        assert "555-123-4567" not in record.msg

    def test_ssn_redaction(self):
        """Test SSN patterns are redacted."""
        record = logging.LogRecord("test", logging.INFO, "", 0, "SSN: 123-45-6789", None, None)
        self.filter.filter(record)
        assert "[SSN_REDACTED]" in record.msg
        assert "123-45-6789" not in record.msg

    def test_credit_card_redaction(self):
        """Test credit card numbers are redacted."""
        record = logging.LogRecord("test", logging.INFO, "", 0, "Card: 4111111111111111", None, None)
        self.filter.filter(record)
        assert "[CARD_REDACTED]" in record.msg
        assert "4111111111111111" not in record.msg

    def test_no_pii_unchanged(self):
        """Test messages without PII are unchanged."""
        record = logging.LogRecord("test", logging.INFO, "", 0, "Normal log message with no PII", None, None)
        self.filter.filter(record)
        assert record.msg == "Normal log message with no PII"

    def test_filter_returns_true(self):
        """Test filter always returns True (don't suppress records)."""
        record = logging.LogRecord("test", logging.INFO, "", 0, "test@example.com", None, None)
        result = self.filter.filter(record)
        assert result is True

    def test_args_dict_scrubbing(self):
        """Test PII in dict args is scrubbed."""
        record = logging.LogRecord("test", logging.INFO, "", 0, "Data: %s", None, None)
        record.args = {"email": "user@domain.com", "name": "John"}
        self.filter.filter(record)
        assert record.args["email"] == "[EMAIL_REDACTED]"
        assert record.args["name"] == "John"

    def test_args_tuple_scrubbing(self):
        """Test PII in tuple args is scrubbed."""
        record = logging.LogRecord("test", logging.INFO, "", 0, "Data: %s %s", None, None)
        record.args = ("user@domain.com", "normal text")
        self.filter.filter(record)
        assert record.args[0] == "[EMAIL_REDACTED]"
        assert record.args[1] == "normal text"
