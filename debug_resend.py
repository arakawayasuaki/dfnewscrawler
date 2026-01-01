import os
import resend
from dotenv import load_dotenv
import json
import markdown

load_dotenv()

LOGO_URL = "https://www.g1tec.jp/images/logo_yoko.jpg"

def generate_email_html(summary_text):
    html_body = markdown.markdown(summary_text)
    full_html = f"""
<!DOCTYPE html PUBLIC "-//W3C//DTD XHTML 1.0 Transitional//EN" "http://www.w3.org/TR/xhtml1/DTD/xhtml1-transitional.dtd">
<html xmlns="http://www.w3.org/1999/xhtml">
<head>
    <meta http-equiv="Content-Type" content="text/html; charset=UTF-8" />
</head>
<body style="margin: 0; padding: 0; background-color: #f4f7f6; font-family: sans-serif;">
    <table border="0" cellpadding="0" cellspacing="0" width="100%">
        <tr>
            <td align="center" bgcolor="#0f172a" style="padding: 20px; color: #ffffff;">
                <img src="{LOGO_URL}" alt="G1 Technology" width="200" />
                <h1>Deepfake News Intelligence (Debug)</h1>
            </td>
        </tr>
        <tr>
            <td style="padding: 30px; background-color: #ffffff;">
                {html_body}
            </td>
        </tr>
    </table>
</body>
</html>
"""
    return full_html

def debug_resend():
    api_key = os.getenv("RESEND_API_KEY")
    sender = os.getenv("SENDER_EMAIL")
    recipient = os.getenv("RECIPIENT_EMAIL")

    if not api_key:
        print("❌ Error: RESEND_API_KEY is not set.")
        return

    # Fingerprint check (safe way to verify secrets)
    def fingerprint(s):
        if not s: return "None"
        return f"{s[0]}...{s[-1]} (len={len(s)})"

    print(f"--- Resend Diagnostics ---")
    print(f"Secrets Fingerprints:")
    print(f" - API Key:   {fingerprint(api_key)}")
    print(f" - Sender:    {fingerprint(sender)}")
    print(f" - Recipient: {fingerprint(recipient)}")
    print("-" * 20)

    resend.api_key = api_key

    # Test Send
    print("\n[3] Attempting Realistic Report Send...")
    mock_body = "### GHA Environment Debug\nThis is a test email sent from GitHub Actions to verify delivery."
    
    params = {
        "from": sender,
        "to": [recipient],
        "subject": "【DEBUG GHA】Delivery Test: " + fingerprint(sender),
        "text": mock_body,
        "html": generate_email_html(mock_body)
    }

    try:
        response = resend.Emails.send(params)
        print(f" ✅ Resend Accepted the email!")
        print(f" Response Metadata: {json.dumps(response, indent=2)}")
    except Exception as e:
        print(f" ❌ Send failure: {e}")

if __name__ == "__main__":
    debug_resend()
