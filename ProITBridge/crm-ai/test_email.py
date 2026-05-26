"""Run this to test if Gmail SMTP is working: python test_email.py"""
import smtplib, ssl
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from dotenv import load_dotenv
import os

load_dotenv(override=True)

user     = os.getenv("SMTP_USER", "niveditakothuri0506@gmail.com")
password = os.getenv("SMTP_PASSWORD", "")
to       = "arunchabra03@gmail.com"

print(f"Testing SMTP...")
print(f"From : {user}")
print(f"To   : {to}")
print(f"Pass : {password[:4]}...{password[-4:] if len(password)>8 else '???'}")
print()

msg = MIMEMultipart("alternative")
msg["Subject"] = "PowerPlex Test Email"
msg["From"]    = user
msg["To"]      = to
msg.attach(MIMEText("This is a test email from PowerPlex CRM. If you receive this, SMTP is working!", "plain"))

try:
    ctx = ssl.create_default_context()
    with smtplib.SMTP_SSL("smtp.gmail.com", 465, context=ctx) as s:
        s.login(user, password)
        s.sendmail(user, [to], msg.as_string())
    print("SUCCESS — email sent to", to)
except smtplib.SMTPAuthenticationError:
    print("FAILED — Authentication error. App password is wrong or expired.")
    print("Go to: https://myaccount.google.com/apppasswords")
    print("Generate a new password and update SMTP_PASSWORD in .env")
except Exception as e:
    print(f"FAILED — {e}")
