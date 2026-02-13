"""Simple notifier stubs. Replace with real senders (SMTP, Twilio, webhooks).
"""
import logging
import os
from typing import List, Optional

logger = logging.getLogger(__name__)


def notify_stub(subject: str, body: str, recipients: List[str]):
    logger.info("Notify stub: %s to %s", subject, recipients)
    # In real code, send an email/SMS/webhook here.
    return True


# Twilio SMS helper
def send_sms_twilio(body: str, to: Optional[str] = None) -> str:
    """Send an SMS via Twilio. Returns message SID on success.

    Environment variables required:
      TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN, TWILIO_FROM
    The `to` arg can be provided or read from TEST_TO env var.
    """
    try:
        from twilio.rest import Client
    except Exception as e:
        raise RuntimeError("twilio package not available; install twilio") from e

    sid = os.getenv("TWILIO_ACCOUNT_SID")
    token = os.getenv("TWILIO_AUTH_TOKEN")
    from_num = os.getenv("TWILIO_FROM")
    to = to or os.getenv("TEST_TO")
    if not (sid and token and from_num and to):
        raise RuntimeError("Missing Twilio environment variables (TWILIO_ACCOUNT_SID/TWILIO_AUTH_TOKEN/TWILIO_FROM/TEST_TO)")

    client = Client(sid, token)
    msg = client.messages.create(body=body, from_=from_num, to=to)
    logger.info("Sent Twilio SMS %s -> %s (sid=%s)", from_num, to, getattr(msg, 'sid', None))
    return getattr(msg, "sid", "")


# Email-to-SMS gateway helper (carrier-dependent)
def send_sms_via_email_gateway(number: str, carrier_domain: str, body: str) -> bool:
    """Send an SMS by emailing a carrier gateway address (e.g., 1234567890@vtext.com).

    Requires SMTP env vars: SMTP_HOST, SMTP_PORT, SMTP_USER, SMTP_PASS
    """
    import smtplib
    from email.message import EmailMessage

    smtp_host = os.getenv("SMTP_HOST")
    smtp_port = int(os.getenv("SMTP_PORT", "587"))
    smtp_user = os.getenv("SMTP_USER")
    smtp_pass = os.getenv("SMTP_PASS")

    if not (smtp_host and smtp_user and smtp_pass):
        raise RuntimeError("Missing SMTP environment variables (SMTP_HOST/SMTP_USER/SMTP_PASS)")

    to_addr = f"{number}@{carrier_domain}"
    msg = EmailMessage()
    msg.set_content(body)
    msg["Subject"] = ""
    msg["From"] = smtp_user
    msg["To"] = to_addr

    logger.info("Sending email-to-sms to %s via %s", number, carrier_domain)
    with smtplib.SMTP(smtp_host, smtp_port) as s:
        s.starttls()
        s.login(smtp_user, smtp_pass)
        s.send_message(msg)
    return True


def notify_sms(body: str, to: Optional[str] = None, method: Optional[str] = None, **kwargs):
    """Unified SMS notifier. method selects 'twilio' or 'email_gateway'.

    If method is None, picks based on NOTIFIER_BACKEND env var.
    """
    method = method or os.getenv("NOTIFIER_BACKEND", "twilio")
    if method == "twilio":
        return send_sms_twilio(body, to=to)
    elif method == "email_gateway":
        carrier_domain = kwargs.get("carrier_domain")
        if not carrier_domain:
            raise ValueError("carrier_domain required for email_gateway method")
        return send_sms_via_email_gateway(to or os.getenv("TEST_SMS_NUMBER"), carrier_domain, body)
    else:
        raise ValueError(f"Unknown notifier method: {method}")

