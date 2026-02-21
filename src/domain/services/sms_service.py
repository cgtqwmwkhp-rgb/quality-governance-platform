"""
SMS Service - Twilio Integration for Emergency Alerts

Features:
- SMS sending via Twilio
- Delivery status tracking
- Message templates
- Rate limiting
- Failover support
"""

import logging
import os
from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from typing import Dict, List, Optional

logger = logging.getLogger(__name__)


class SMSStatus(str, Enum):
    """SMS delivery status"""

    QUEUED = "queued"
    SENT = "sent"
    DELIVERED = "delivered"
    FAILED = "failed"
    UNDELIVERED = "undelivered"


@dataclass
class SMSResult:
    """Result of SMS send operation"""

    success: bool
    message_sid: Optional[str] = None
    status: SMSStatus = SMSStatus.QUEUED
    error_code: Optional[str] = None
    error_message: Optional[str] = None
    sent_at: datetime = None  # type: ignore[assignment]  # TYPE-IGNORE: MYPY-004 Set in __post_init__

    def __post_init__(self):
        if self.sent_at is None:
            self.sent_at = datetime.utcnow()


class SMSService:
    """
    SMS service using Twilio for delivery.

    Features:
    - Send SMS to any phone number
    - Bulk SMS sending
    - Message templates
    - Delivery status tracking
    """

    def __init__(self):
        self.account_sid = os.getenv("TWILIO_ACCOUNT_SID")
        self.auth_token = os.getenv("TWILIO_AUTH_TOKEN")
        self.from_number = os.getenv("TWILIO_FROM_NUMBER")

        self.client = None
        self.enabled = bool(self.account_sid and self.auth_token)

        if self.enabled:
            try:
                from twilio.rest import Client

                self.client = Client(self.account_sid, self.auth_token)
                logger.info("Twilio SMS service initialized")
            except ImportError:
                logger.warning("Twilio package not installed. SMS disabled.")
                self.enabled = False
            except Exception as e:
                logger.error(f"Failed to initialize Twilio: {e}")
                self.enabled = False
        else:
            logger.warning("Twilio credentials not configured. SMS disabled.")

    async def send_sms(self, to: str, message: str, from_number: Optional[str] = None) -> SMSResult:
        """
        Send an SMS message.

        Args:
            to: Recipient phone number (E.164 format)
            message: Message text (max 1600 chars)
            from_number: Optional sender number override

        Returns:
            SMSResult with status
        """
        if not self.enabled:
            logger.warning(f"SMS disabled. Would send to {to}: {message[:50]}...")
            return SMSResult(
                success=False,
                status=SMSStatus.FAILED,
                error_message="SMS service not configured",
            )

        # Validate phone number format
        normalized = self._normalize_phone_number(to)
        if not normalized:
            return SMSResult(
                success=False,
                status=SMSStatus.FAILED,
                error_message="Invalid phone number format",
            )

        # Truncate message if too long
        if len(message) > 1600:
            message = message[:1597] + "..."

        try:
            sms = self.client.messages.create(body=message, from_=from_number or self.from_number, to=normalized)

            logger.info(f"SMS sent to {normalized}: SID={sms.sid}")

            return SMSResult(
                success=True,
                message_sid=sms.sid,
                status=(SMSStatus(sms.status) if sms.status in SMSStatus.__members__ else SMSStatus.QUEUED),
            )

        except Exception as e:
            logger.error(f"Failed to send SMS to {to}: {e}")

            error_code = getattr(e, "code", None)
            return SMSResult(
                success=False,
                status=SMSStatus.FAILED,
                error_code=str(error_code) if error_code else None,
                error_message=str(e),
            )

    async def send_bulk_sms(self, recipients: List[str], message: str) -> Dict[str, SMSResult]:
        """
        Send the same message to multiple recipients.

        Args:
            recipients: List of phone numbers
            message: Message text

        Returns:
            Dict mapping phone number to result
        """
        results = {}

        for phone in recipients:
            result = await self.send_sms(phone, message)
            results[phone] = result

        return results

    async def send_sos_alert(
        self,
        recipients: List[str],
        reporter_name: str,
        location: str,
        gps_link: Optional[str] = None,
    ) -> Dict[str, SMSResult]:
        """
        Send SOS emergency alert SMS.

        Args:
            recipients: List of phone numbers
            reporter_name: Name of person in emergency
            location: Location description
            gps_link: Optional Google Maps link

        Returns:
            Dict mapping phone number to result
        """
        message = f"""🚨 EMERGENCY SOS ALERT

{reporter_name} needs immediate assistance!

Location: {location}
{f'Map: {gps_link}' if gps_link else ''}

Time: {datetime.utcnow().strftime('%H:%M UTC')}

RESPOND IMMEDIATELY"""

        return await self.send_bulk_sms(recipients, message)

    async def send_riddor_alert(
        self,
        recipients: List[str],
        incident_ref: str,
        incident_type: str,
        location: str,
    ) -> Dict[str, SMSResult]:
        """
        Send RIDDOR reportable incident alert SMS.

        Args:
            recipients: List of phone numbers
            incident_ref: Incident reference number
            incident_type: Type of incident
            location: Location of incident

        Returns:
            Dict mapping phone number to result
        """
        message = f"""⚠️ RIDDOR ALERT

Ref: {incident_ref}
Type: {incident_type}
Location: {location}

HSE reporting required within statutory timeframe.

Login to QGP to submit report."""

        return await self.send_bulk_sms(recipients, message)

    async def send_action_reminder(self, phone: str, action_title: str, due_date: str, action_url: str) -> SMSResult:
        """
        Send action item reminder SMS.

        Args:
            phone: Recipient phone number
            action_title: Title of the action
            due_date: Due date string
            action_url: Link to the action

        Returns:
            SMSResult
        """
        message = f"""⏰ ACTION REMINDER

"{action_title}"

Due: {due_date}

Please complete or update status.

{action_url}"""

        return await self.send_sms(phone, message)

    async def send_verification_code(self, phone: str, code: str) -> SMSResult:
        """
        Send verification code SMS.

        Args:
            phone: Recipient phone number
            code: Verification code

        Returns:
            SMSResult
        """
        message = f"""Your QGP verification code is: {code}

This code expires in 10 minutes.

If you didn't request this, please ignore."""

        return await self.send_sms(phone, message)

    def _normalize_phone_number(self, phone: str) -> Optional[str]:
        """
        Normalize phone number to E.164 format.

        Args:
            phone: Input phone number

        Returns:
            Normalized number or None if invalid
        """
        # Remove all non-digit characters except +
        cleaned = "".join(c for c in phone if c.isdigit() or c == "+")

        # Ensure starts with +
        if not cleaned.startswith("+"):
            # Assume UK if starts with 0
            if cleaned.startswith("0"):
                cleaned = "+44" + cleaned[1:]
            else:
                # Assume US/Canada
                cleaned = "+1" + cleaned

        # Basic validation
        if len(cleaned) < 10 or len(cleaned) > 16:
            return None

        return cleaned

    async def get_message_status(self, message_sid: str) -> Optional[SMSStatus]:
        """
        Get the delivery status of a sent message.

        Args:
            message_sid: Twilio message SID

        Returns:
            SMSStatus or None if not found
        """
        if not self.enabled:
            return None

        try:
            message = self.client.messages(message_sid).fetch()
            return SMSStatus(message.status) if message.status in SMSStatus.__members__ else None
        except Exception as e:
            logger.error(f"Failed to get message status: {e}")
            return None


# Singleton instance
sms_service = SMSService()
