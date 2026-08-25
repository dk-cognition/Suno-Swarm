"""Out-of-band notification delivery seams."""
import logging
from datetime import datetime

log = logging.getLogger("swarm.notifications")


def _deliver(email: str, subject: str, body: str) -> None:
    log.info("email delivery attempt recipient=%s subject=%s", email, subject)


def send_password_reset_email(email: str, reset_token: str, expires_at: datetime) -> None:
    """Hand the token only to this transport; never return it or write it to logs."""
    log.info("password reset email recipient=%s expires_at=%s", email, expires_at)
    _deliver(
        email,
        "Password reset request",
        f"Use this password reset token before {expires_at}: {reset_token}",
    )
