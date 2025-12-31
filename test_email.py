import os
import smtplib
from email.mime.text import MIMEText
from dotenv import load_dotenv

load_dotenv()

GMAIL_USER = os.getenv("GMAIL_USER")
GMAIL_APP_PASSWORD = os.getenv("GMAIL_APP_PASSWORD")
RECIPIENT_EMAIL = os.getenv("RECIPIENT_EMAIL", "packyas@gmail.com")

def test_email():
    if not GMAIL_USER or not GMAIL_APP_PASSWORD:
        print("Error: GMAIL_USER or GMAIL_APP_PASSWORD not set in .env")
        return

    msg = MIMEText("This is a test email from your Deepfake News Crawler.")
    msg['Subject'] = "Test Email - Deepfake News Crawler"
    msg['From'] = GMAIL_USER
    msg['To'] = RECIPIENT_EMAIL

    try:
        server = smtplib.SMTP_SSL('smtp.gmail.com', 465)
        server.login(GMAIL_USER, GMAIL_APP_PASSWORD)
        server.send_message(msg)
        server.quit()
        print(f"Success! Test email sent to {RECIPIENT_EMAIL}")
    except Exception as e:
        print(f"Failed to send email: {e}")

if __name__ == "__main__":
    test_email()
