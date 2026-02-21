"""Email sending via SMTP (e.g. Gmail). Resend has been removed."""
import asyncio
import logging
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

from config import get_settings

logger = logging.getLogger(__name__)


def _send_via_smtp(to: str, subject: str, body: str, from_addr: str, from_name: str) -> bool:
    """Sync SMTP send (run in thread). Gmail: smtp.gmail.com:587, TLS."""
    s = get_settings()
    # Password already cleaned in config.py
    password = s.smtp_password
    if not s.smtp_user or not password:
        logger.error("SMTP_USER or SMTP_PASSWORD not configured")
        return False
    try:
        msg = MIMEMultipart("alternative")
        msg["Subject"] = subject
        msg["From"] = f"{from_name} <{from_addr}>"
        msg["To"] = to
        
        # HTML version
        html_body = body.replace("\n", "<br>\n")
        msg.attach(MIMEText(html_body, "html", "utf-8"))
        # Plain text version
        msg.attach(MIMEText(body, "plain", "utf-8"))
        
        with smtplib.SMTP(s.smtp_host, s.smtp_port) as server:
            server.starttls()
            server.login(s.smtp_user, password)
            server.sendmail(from_addr, [to], msg.as_string())
        
        return True
    except Exception as e:
        logger.error("SMTP send failed to %s: %s", to, e)
        return False


async def send_email(to: str, subject: str, body: str, from_name: str | None = None) -> bool:
    """Send one email via SMTP (Gmail). Returns True on success."""
    s = get_settings()
    from_name = from_name or s.email_from_name
    # Force use of smtp_user as from_addr for Gmail compatibility
    from_addr = s.smtp_user

    if not from_addr or not s.smtp_password:
        logger.warning("SMTP not configured: set MAIL and APP_PASSWORD in .env")
        return False

    return await asyncio.to_thread(
        _send_via_smtp, to, subject, body, from_addr, from_name
    )
