"""
email_sender.py — Gmail SMTP email sender for PowerPlex CRM.
Sends real emails to the 2 active customers. All others are display-only.
"""
import smtplib
import os
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from dotenv import load_dotenv

load_dotenv(override=True)

# Only these 2 customer emails will actually receive emails
REAL_CUSTOMER_EMAILS = {
    "arunchabra03@gmail.com",   # Arun Kumar   - CUST001
    "knivedita143@gmail.com",   # Priya Sharma - CUST002
}
ADMIN_EMAIL = "niveditakothuri0506@gmail.com"


def _get_smtp_config():
    return {
        "host"    : os.getenv("SMTP_HOST", "smtp.gmail.com"),
        "port"    : int(os.getenv("SMTP_PORT", "465")),
        "user"    : os.getenv("SMTP_USER", ADMIN_EMAIL),
        "password": os.getenv("SMTP_PASSWORD", ""),
    }


def send_email(to_email: str, subject: str, body: str,
               from_name: str = "PowerPlex CRM") -> dict:
    """
    Send an email via Gmail SMTP.
    Only sends to REAL_CUSTOMER_EMAILS — all others are skipped gracefully.
    Admin always gets a BCC copy.
    """
    cfg = _get_smtp_config()

    if not cfg["password"]:
        return {"success": False, "error": "SMTP_PASSWORD not configured in .env"}

    # Only send to real customers or admin
    if to_email not in REAL_CUSTOMER_EMAILS and to_email != ADMIN_EMAIL:
        print(f"[Email] {to_email} is display-only — skipping send.")
        return {
            "success"  : True,
            "skipped"  : True,
            "message"  : f"{to_email} is a display-only customer — no email sent.",
        }

    try:
        msg = MIMEMultipart("alternative")
        msg["Subject"] = subject
        msg["From"]    = f"{from_name} <{cfg['user']}>"
        msg["To"]      = to_email
        msg["Bcc"]     = ADMIN_EMAIL  # admin always gets a copy

        # Plain text part
        msg.attach(MIMEText(body, "plain"))

        # HTML part — wrap body in nice template
        html_body = f"""
        <html><body style="font-family:Inter,Arial,sans-serif;max-width:600px;margin:0 auto;padding:20px;color:#1e293b;">
          <div style="border-bottom:3px solid #2563eb;padding-bottom:12px;margin-bottom:20px;">
            <h2 style="margin:0;color:#2563eb;font-size:18px;">PowerPlex Service</h2>
          </div>
          <div style="line-height:1.7;white-space:pre-line;">{body}</div>
          <div style="margin-top:30px;padding-top:14px;border-top:1px solid #e2e8f0;font-size:12px;color:#64748b;">
            PowerPlex CRM &nbsp;·&nbsp; Automated Service Notification
          </div>
        </body></html>
        """
        msg.attach(MIMEText(html_body, "html"))

        with smtplib.SMTP_SSL(cfg["host"], cfg["port"]) as server:
            server.login(cfg["user"], cfg["password"])
            server.sendmail(cfg["user"], [to_email, ADMIN_EMAIL], msg.as_string())

        print(f"[Email] Sent to {to_email} — Subject: {subject}")
        return {"success": True, "to": to_email, "subject": subject}

    except Exception as e:
        print(f"[Email] Send failed: {e}")
        return {"success": False, "error": str(e)}
