"""
Email Service - Enterprise Email Notification System

Provides HTML email templating, SMTP integration, and notification management
for the Quality Governance Platform.
"""

import logging
import os
import smtplib
from datetime import datetime
from email import encoders
from email.mime.base import MIMEBase
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
# pathlib available if needed
from typing import Any, Dict, List, Optional

# Settings imported if needed: from src.core.config import settings

logger = logging.getLogger(__name__)


class EmailService:
    """Enterprise email notification service with HTML templating."""

    def __init__(self):
        self.smtp_host = os.getenv("SMTP_HOST", "smtp.office365.com")
        self.smtp_port = int(os.getenv("SMTP_PORT", "587"))
        self.smtp_user = os.getenv("SMTP_USER", "")
        self.smtp_password = os.getenv("SMTP_PASSWORD", "")
        self.from_email = os.getenv("FROM_EMAIL", "noreply@qgp.plantexpand.com")
        self.from_name = os.getenv("FROM_NAME", "Quality Governance Platform")
        self.enabled = bool(self.smtp_user and self.smtp_password)

    def _get_base_template(self) -> str:
        """Return the base HTML email template."""
        return """
        <!DOCTYPE html>
        <html lang="en">
        <head>
            <meta charset="UTF-8">
            <meta name="viewport" content="width=device-width, initial-scale=1.0">
            <title>{subject}</title>
            <style>
                body {{
                    font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
                    background-color: #0f172a;
                    margin: 0;
                    padding: 0;
                    color: #e2e8f0;
                }}
                .container {{
                    max-width: 600px;
                    margin: 0 auto;
                    background-color: #1e293b;
                    border-radius: 16px;
                    overflow: hidden;
                    margin-top: 20px;
                    margin-bottom: 20px;
                    box-shadow: 0 25px 50px -12px rgba(0, 0, 0, 0.25);
                }}
                .header {{
                    background: linear-gradient(135deg, #10b981, #14b8a6, #06b6d4);
                    padding: 30px;
                    text-align: center;
                }}
                .header h1 {{
                    margin: 0;
                    color: white;
                    font-size: 24px;
                    font-weight: 700;
                }}
                .header p {{
                    margin: 8px 0 0;
                    color: rgba(255,255,255,0.9);
                    font-size: 14px;
                }}
                .content {{
                    padding: 30px;
                }}
                .content h2 {{
                    color: #f8fafc;
                    font-size: 20px;
                    margin-top: 0;
                }}
                .content p {{
                    color: #94a3b8;
                    line-height: 1.6;
                }}
                .alert-box {{
                    background-color: #334155;
                    border-left: 4px solid {alert_color};
                    padding: 16px;
                    border-radius: 8px;
                    margin: 20px 0;
                }}
                .alert-box.high {{
                    border-color: #ef4444;
                }}
                .alert-box.medium {{
                    border-color: #f59e0b;
                }}
                .alert-box.low {{
                    border-color: #22c55e;
                }}
                .alert-box h3 {{
                    margin: 0 0 8px;
                    color: #f8fafc;
                    font-size: 16px;
                }}
                .alert-box p {{
                    margin: 0;
                    color: #cbd5e1;
                    font-size: 14px;
                }}
                .details-table {{
                    width: 100%;
                    border-collapse: collapse;
                    margin: 20px 0;
                }}
                .details-table th,
                .details-table td {{
                    padding: 12px;
                    text-align: left;
                    border-bottom: 1px solid #334155;
                }}
                .details-table th {{
                    color: #64748b;
                    font-weight: 500;
                    font-size: 12px;
                    text-transform: uppercase;
                }}
                .details-table td {{
                    color: #e2e8f0;
                }}
                .button {{
                    display: inline-block;
                    padding: 14px 28px;
                    background: linear-gradient(135deg, #7c3aed, #8b5cf6);
                    color: white;
                    text-decoration: none;
                    border-radius: 12px;
                    font-weight: 600;
                    margin-top: 20px;
                }}
                .button:hover {{
                    background: linear-gradient(135deg, #6d28d9, #7c3aed);
                }}
                .footer {{
                    padding: 20px 30px;
                    background-color: #0f172a;
                    text-align: center;
                    border-top: 1px solid #334155;
                }}
                .footer p {{
                    color: #64748b;
                    font-size: 12px;
                    margin: 4px 0;
                }}
                .status-badge {{
                    display: inline-block;
                    padding: 4px 12px;
                    border-radius: 20px;
                    font-size: 12px;
                    font-weight: 600;
                }}
                .status-open {{ background-color: #f59e0b20; color: #f59e0b; }}
                .status-closed {{ background-color: #22c55e20; color: #22c55e; }}
                .status-in-progress {{ background-color: #3b82f620; color: #3b82f6; }}
            </style>
        </head>
        <body>
            <div class="container">
                <div class="header">
                    <h1>Quality Governance Platform</h1>
                    <p>Enterprise IMS Notification</p>
                </div>
                <div class="content">
                    {content}
                </div>
                <div class="footer">
                    <p>This is an automated message from QGP</p>
                    <p>© {year} PlantExpand Ltd. All rights reserved.</p>
                </div>
            </div>
        </body>
        </html>
        """

    async def send_email(
        self,
        to: List[str],
        subject: str,
        html_content: str,
        cc: Optional[List[str]] = None,
        bcc: Optional[List[str]] = None,
        attachments: Optional[List[Dict[str, Any]]] = None,
    ) -> bool:
        """
        Send an HTML email.

        Args:
            to: List of recipient email addresses
            subject: Email subject line
            html_content: HTML body content
            cc: Optional CC recipients
            bcc: Optional BCC recipients
            attachments: Optional list of attachments with 'filename' and 'content' keys

        Returns:
            True if email sent successfully, False otherwise
        """
        if not self.enabled:
            logger.warning("Email service not configured. Skipping email send.")
            return False

        try:
            msg = MIMEMultipart("alternative")
            msg["Subject"] = subject
            msg["From"] = f"{self.from_name} <{self.from_email}>"
            msg["To"] = ", ".join(to)

            if cc:
                msg["Cc"] = ", ".join(cc)

            # Attach HTML content
            html_part = MIMEText(html_content, "html")
            msg.attach(html_part)

            # Add attachments if provided
            if attachments:
                for attachment in attachments:
                    part = MIMEBase("application", "octet-stream")
                    part.set_payload(attachment["content"])
                    encoders.encode_base64(part)
                    part.add_header(
                        "Content-Disposition",
                        f'attachment; filename="{attachment["filename"]}"',
                    )
                    msg.attach(part)

            # Calculate all recipients
            all_recipients = to + (cc or []) + (bcc or [])

            # Send email
            with smtplib.SMTP(self.smtp_host, self.smtp_port) as server:
                server.starttls()
                server.login(self.smtp_user, self.smtp_password)
                server.sendmail(self.from_email, all_recipients, msg.as_string())

            logger.info(f"Email sent successfully to {to}")
            return True

        except Exception as e:
            logger.error(f"Failed to send email: {e}")
            return False

    async def send_incident_notification(
        self,
        to: List[str],
        incident_id: str,
        title: str,
        severity: str,
        description: str,
        location: Optional[str] = None,
        reported_by: Optional[str] = None,
        action_url: Optional[str] = None,
    ) -> bool:
        """Send an incident notification email."""
        severity_colors = {
            "critical": "#ef4444",
            "high": "#f97316",
            "medium": "#f59e0b",
            "low": "#22c55e",
        }
        alert_color = severity_colors.get(severity.lower(), "#64748b")

        content = f"""
        <h2>🚨 New Incident Reported</h2>
        <div class="alert-box {severity.lower()}">
            <h3>{title}</h3>
            <p>{description}</p>
        </div>
        <table class="details-table">
            <tr>
                <th>Reference</th>
                <td>{incident_id}</td>
            </tr>
            <tr>
                <th>Severity</th>
                <td><span class="status-badge status-open">{severity.upper()}</span></td>
            </tr>
            {f'<tr><th>Location</th><td>{location}</td></tr>' if location else ''}
            {f'<tr><th>Reported By</th><td>{reported_by}</td></tr>' if reported_by else ''}
            <tr>
                <th>Time</th>
                <td>{datetime.now().strftime('%Y-%m-%d %H:%M')}</td>
            </tr>
        </table>
        {f'<a href="{action_url}" class="button">View Incident →</a>' if action_url else ''}
        """

        html = self._get_base_template().format(
            subject=f"[{severity.upper()}] Incident: {title}",
            content=content,
            alert_color=alert_color,
            year=datetime.now().year,
        )

        return await self.send_email(to=to, subject=f"[{severity.upper()}] Incident: {title}", html_content=html)

    async def send_action_reminder(
        self,
        to: List[str],
        action_id: str,
        title: str,
        due_date: str,
        days_overdue: int = 0,
        assignee: Optional[str] = None,
        action_url: Optional[str] = None,
    ) -> bool:
        """Send an action reminder/overdue notification."""
        is_overdue = days_overdue > 0
        alert_color = "#ef4444" if is_overdue else "#f59e0b"

        status_text = f"{days_overdue} days overdue" if is_overdue else "Due soon"

        content = f"""
        <h2>{'⚠️ Action Overdue' if is_overdue else '🔔 Action Reminder'}</h2>
        <div class="alert-box {'high' if is_overdue else 'medium'}">
            <h3>{title}</h3>
            <p>{status_text}</p>
        </div>
        <table class="details-table">
            <tr>
                <th>Reference</th>
                <td>{action_id}</td>
            </tr>
            <tr>
                <th>Due Date</th>
                <td>{due_date}</td>
            </tr>
            {f'<tr><th>Assigned To</th><td>{assignee}</td></tr>' if assignee else ''}
            <tr>
                <th>Status</th>
                <td><span class="status-badge {'status-open' if is_overdue else 'status-in-progress'}">
                    {status_text}
                </span></td>
            </tr>
        </table>
        {f'<a href="{action_url}" class="button">View Action →</a>' if action_url else ''}
        """

        html = self._get_base_template().format(
            subject=f"{'[OVERDUE]' if is_overdue else '[REMINDER]'} Action: {title}",
            content=content,
            alert_color=alert_color,
            year=datetime.now().year,
        )

        return await self.send_email(
            to=to,
            subject=f"{'[OVERDUE]' if is_overdue else '[REMINDER]'} Action: {title}",
            html_content=html,
        )

    async def send_weekly_digest(
        self,
        to: List[str],
        summary: Dict[str, Any],
    ) -> bool:
        """Send a weekly summary digest email."""
        content = f"""
        <h2>📊 Weekly IMS Summary</h2>
        <p>Here's your weekly summary for the Quality Governance Platform:</p>

        <table class="details-table">
            <tr>
                <th>Metric</th>
                <th>This Week</th>
                <th>Change</th>
            </tr>
            <tr>
                <td>New Incidents</td>
                <td>{summary.get('new_incidents', 0)}</td>
                <td>{summary.get('incidents_change', '0%')}</td>
            </tr>
            <tr>
                <td>Closed Actions</td>
                <td>{summary.get('closed_actions', 0)}</td>
                <td>{summary.get('actions_change', '0%')}</td>
            </tr>
            <tr>
                <td>Open Risks</td>
                <td>{summary.get('open_risks', 0)}</td>
                <td>{summary.get('risks_change', '0%')}</td>
            </tr>
            <tr>
                <td>Compliance Score</td>
                <td>{summary.get('compliance_score', '0%')}</td>
                <td>{summary.get('compliance_change', '0%')}</td>
            </tr>
        </table>

        <div class="alert-box medium">
            <h3>Upcoming This Week</h3>
            <p>{summary.get('upcoming_audits', 0)} audits scheduled</p>
            <p>{summary.get('overdue_actions', 0)} actions overdue</p>
        </div>

        <a href="{summary.get('dashboard_url', '/')}" class="button">View Dashboard →</a>
        """

        html = self._get_base_template().format(
            subject="Weekly IMS Summary",
            content=content,
            alert_color="#7c3aed",
            year=datetime.now().year,
        )

        return await self.send_email(to=to, subject="📊 Weekly IMS Summary", html_content=html)


# Singleton instance
email_service = EmailService()
