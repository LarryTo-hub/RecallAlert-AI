"""Simple notifier stubs. Replace with real senders (SMTP, Twilio, webhooks).
"""
import logging

logger = logging.getLogger(__name__)


def notify_stub(subject: str, body: str, recipients: list):
    logger.info("Notify stub: %s to %s", subject, recipients)
    # In real code, send an email/SMS/webhook here.
    return True
