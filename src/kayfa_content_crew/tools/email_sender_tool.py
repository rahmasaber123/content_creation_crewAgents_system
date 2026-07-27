from __future__ import annotations

import logging
import os
import smtplib
from email.mime.application import MIMEApplication
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

logger = logging.getLogger(__name__)


def send_email_with_pdf(recipient: str, subject: str, pdf_path: str, body: str = "") -> str:
    """Emails the generated PDF. If ENABLE_EMAIL_SEND is not 'true', only
    prints/logs instead of sending -- safe default for local/dev runs."""
    enabled = os.environ.get("ENABLE_EMAIL_SEND", "false").lower() == "true"
    if not enabled:
        msg = f"[SANDBOX] Would email '{subject}' with attachment {pdf_path} to {recipient}"
        logger.info(msg)
        return msg

    host = os.environ.get("SMTP_HOST")
    port = int(os.environ.get("SMTP_PORT", "587"))
    user = os.environ.get("SMTP_USER")
    password = os.environ.get("SMTP_PASSWORD")
    if not all([host, user, password]):
        logger.error("ENABLE_EMAIL_SEND=true but SMTP_HOST/SMTP_USER/SMTP_PASSWORD not fully set")
        return "Email not sent -- SMTP credentials incomplete."

    try:
        msg = MIMEMultipart()
        msg["From"] = user
        msg["To"] = recipient
        msg["Subject"] = subject
        msg.attach(MIMEText(body or "Please find the attached approved post.", "plain"))

        with open(pdf_path, "rb") as f:
            part = MIMEApplication(f.read(), _subtype="pdf")
            part.add_header("Content-Disposition", "attachment", filename=os.path.basename(pdf_path))
            msg.attach(part)

        with smtplib.SMTP(host, port, timeout=15) as server:
            server.starttls()
            server.login(user, password)
            server.sendmail(user, [recipient], msg.as_string())

        logger.info("Emailed %s to %s", pdf_path, recipient)
        return f"Email sent to {recipient} with attachment {pdf_path}"
    except (OSError, smtplib.SMTPException):
        logger.exception("send_email_with_pdf failed for recipient=%s", recipient)
        return f"Email failed to send to {recipient} -- see logs for details."
