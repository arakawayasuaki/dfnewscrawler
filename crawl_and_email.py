import os
import datetime
from datetime import timezone, timedelta
import json
import markdown
from google import genai
from google.genai import types
import resend
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseUpload
import io
from dotenv import load_dotenv

# Define JST (Japan Standard Time)
JST = timezone(timedelta(hours=9))

# Load environment variables
load_dotenv()

# Configuration
RESEND_API_KEY = os.getenv("RESEND_API_KEY")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
# Recipient(s) (SECURITY):
# - Do NOT hardcode recipient email addresses in source code.
# - Set RECIPIENT_EMAIL via environment variables/secrets.
# - You can provide a single address, multiple addresses separated by commas/semicolons/whitespace,
#   or a JSON array string (e.g. '["a@example.com","b@example.com"]').

def parse_recipient_emails(value):
    if value is None:
        return []
    raw = str(value).strip()
    if not raw:
        return []

    # JSON array support
    if raw.startswith("["):
        try:
            parsed = json.loads(raw)
            if isinstance(parsed, list):
                items = [str(x).strip() for x in parsed]
            else:
                items = [raw]
        except Exception:
            items = [raw]
    else:
        # Split on common separators
        for sep in [";", "\n", "\t", " "]:
            raw = raw.replace(sep, ",")
        items = [x.strip() for x in raw.split(",")]

    # Deduplicate while preserving order
    seen = set()
    out = []
    for x in items:
        if not x:
            continue
        if x in seen:
            continue
        seen.add(x)
        out.append(x)
    return out

RECIPIENT_EMAILS = parse_recipient_emails(os.getenv("RECIPIENT_EMAIL"))
# Resend default from address if domain not verified
SENDER_EMAIL = os.getenv("SENDER_EMAIL", "onboarding@resend.dev")

resend.api_key = RESEND_API_KEY

HISTORY_FILE = "fetched_history.json"
OUTPUT_FILE = "latest_deepfake_news.md"

def generate_report_with_gemini_search():
    """
    Generate a news report using Gemini's native Google Search grounding via google.genai SDK.
    """
    if not GEMINI_API_KEY:
        return "Gemini API Key is not set."
    
    # Configure client
    client = genai.Client(api_key=GEMINI_API_KEY)
    
    # Use JST for the date in the prompt
    jst_now = datetime.datetime.now(JST)
    today = jst_now.strftime('%Y年%m月%d日')
    custom_prompt = os.getenv("CUSTOM_PROMPT", "")
    
    # Create additional instruction block if user provided one
    additional_instr = f"\n【追加の個別指示】\n{custom_prompt}\n" if custom_prompt else ""

    prompt = f"""
    今日は {today} です。
    最新のディープフェイク（Deepfake）に関するニュースや動静（直近24〜48時間以内）を調査し、日本語で網羅的なレポートを作成してください。

    {additional_instr}

    【重要：情報の正確性と接地（Grounding）】
    - **必ず実際の検索結果に基づいた情報を出力してください。** 架空のニュースや、根拠のない推測を含めてはいけません。
    - **ダミーURLの禁止**: `example.com` や `google.com` などのプレースホルダーURLは**絶対に使用しないでください**。見つかった「実際のURL」のみを使用してください。
    - **URLの重複について**: 可能な限り異なるソースを使用することが望ましいですが、適切なソースが限られている場合は、情報の正確性を優先し、同じ信頼できるソースを引用しても構いません。**「形式のために嘘のURLを捏造すること」は最大の禁忌です。**

    【レポートの出力ルール】
    1. **挨拶・前置きの完全禁止**: 「はい」「承知いたしました」等は一切不要です。必ず `## 主要ニュースのまとめ` から開始してください。
    2. **構造の安定化**: 各ニュース項目の間には、**必ず2行の空行**を入れてください。

    【レポートの構成形式】
    ## 主要ニュースのまとめ (10〜15件程度)
    
    ### 1. [記事のタイトル（日本語翻訳）](取得した実際のURL)
    - **内容**: 具体的かつ客観的に3〜4文程度で記述（日本語）。
    - **出典**: [メディア名・サイト名（日本語）](取得した実際のURL)


    ### 2. [次の記事のタイトル（日本語翻訳）](取得した実際のURL)
    - **内容**: ...
    - **出典**: ...


    （実際の検索結果に基づき、10〜15件程度を同様の形式で継続）


    ## その他の注目見出し
    * [記事タイトル（要日本語翻訳）](実際のURL) - メディア名
    * (可能な限り多数、必ず実際のリンクを含めること)

    【検索と収集の指針】
    - **グローバル優先**: 英語等の多言語検索を行い、海外の主要ソースを50%以上含めてください。
    - **鮮度の徹底**: 「今起きていること」を優先し、一般的な解説や古いニュースは除外してください。
    """
    
    try:
        print("Executing Gemini Search (Grounding via google.genai)...")
        # Configure search tool
        config = types.GenerateContentConfig(
            tools=[types.Tool(google_search=types.GoogleSearch())]
        )
        
        response = client.models.generate_content(
            model='gemini-2.0-flash',
            contents=prompt,
            config=config
        )
        summary = response.text
        
        # Post-processing: Remove Gemini conversational filler and redundant titles
        clean_summary = clean_gemini_output(summary)
        return clean_summary
    except Exception as e:
        print(f"Error with Gemini Search: {e}")
        return f"レポート生成中にエラーが発生しました: {e}"

def clean_gemini_output(text):
    """
    Programmatically strip common AI conversational filler and redundant headers.
    """
    # Patterns to remove from the beginning of the text
    forbidden_start_patterns = [
        "はい、承知いたしました",
        "承知いたしました",
        "はい、2026",
        "レポートを作成します",
        "最新のディープフェイク",
        "以下に、2026",
        "申し訳ございません",
        "Google検索を使用して",
        "承知しました"
    ]
    
    lines = text.strip().split('\n')
    while lines and any(p in lines[0] for p in forbidden_start_patterns):
        lines.pop(0)
    
    # Rejoin and remove leading empty lines/whitespace
    cleaned_content = '\n'.join(lines).strip()
    
    # Ensure it doesn't accidentally remove actual content
    if not cleaned_content:
        return text.strip()
        
    return cleaned_content

# G1 Technology Official Logo URL
LOGO_URL = "https://www.g1tec.jp/images/logo_yoko.jpg"

def generate_email_html(summary_text):
    """
    Generate a high-compatibility HTML email template using tables and inline CSS.
    Optimized for bypassing spam filters and rendering in all clients.
    Using G1 Technology corporate colors: Navy (#0f172a) and Brand Green (#2fa59a).
    """
    html_body = markdown.markdown(summary_text)
    
    # Using a table-based layout for maximum compatibility
    full_html = f"""
<!DOCTYPE html PUBLIC "-//W3C//DTD XHTML 1.0 Transitional//EN" "http://www.w3.org/TR/xhtml1/DTD/xhtml1-transitional.dtd">
<html xmlns="http://www.w3.org/1999/xhtml">
<head>
    <meta http-equiv="Content-Type" content="text/html; charset=UTF-8" />
    <title>Deepfake News Intelligence</title>
    <meta name="viewport" content="width=device-width, initial-scale=1.0"/>
</head>
<body style="margin: 0; padding: 0; background-color: #f4f7f6; font-family: 'Helvetica Neue', Helvetica, Arial, sans-serif;">
    <table border="0" cellpadding="0" cellspacing="0" width="100%">
        <tr>
            <td style="padding: 20px 0 30px 0;">
                <table align="center" border="0" cellpadding="0" cellspacing="0" width="600" style="border: 1px solid #cccccc; border-radius: 8px; overflow: hidden; background-color: #ffffff; box-shadow: 0 4px 12px rgba(0,0,0,0.05);">
                    <!-- Header -->
                    <tr>
                        <td align="center" bgcolor="#0f172a" style="padding: 40px 0 30px 0; color: #ffffff; font-size: 28px; font-weight: bold; font-family: Arial, sans-serif;">
                            <img src="{LOGO_URL}" alt="G1 Technology" width="200" style="display: block; margin-bottom: 20px;" />
                            <h1 style="margin: 0; font-size: 22px; letter-spacing: 1px; color: #ffffff;">Deepfake News Intelligence</h1>
                        </td>
                    </tr>
                    <!-- Content -->
                    <tr>
                        <td style="padding: 40px 30px 40px 30px; color: #333333; font-family: Arial, sans-serif; font-size: 16px; line-height: 1.6;">
                            <div style="color: #333333;">
                                {html_body.replace('<a ', '<a style="color: #2fa59a; text-decoration: none; font-weight: bold;" ')}
                            </div>
                        </td>
                    </tr>
                    <!-- Footer Signature -->
                    <tr>
                        <td bgcolor="#f9f9f9" style="padding: 30px 30px 30px 30px; border-top: 1px solid #eeeeee;">
                            <table border="0" cellpadding="0" cellspacing="0" width="100%">
                                <tr>
                                    <td style="color: #666666; font-family: Arial, sans-serif; font-size: 14px; line-height: 1.6;">
                                        <b style="color: #2fa59a; font-size: 16px;">G1 Technology Inc.</b><br/>
                                        Advanced AI Security & Research Team<br/>
                                        <a href="https://g1tec.jp/" style="color: #2fa59a; text-decoration: none; font-weight: bold;">g1tec.jp</a><br/>
                                        <span style="font-size: 12px; color: #999999;">Connecting Global Innovation to Japan</span>
                                    </td>
                                </tr>
                            </table>
                        </td>
                    </tr>
                </table>
            </td>
        </tr>
    </table>
</body>
</html>
"""
    return full_html

# If modifying these scopes, delete the file token.json.
SCOPES = ['https://www.googleapis.com/auth/drive.file']

def get_gdrive_service():
    """
    Authenticate and return the Drive service using OAuth2.
    """
    creds = None
    # The file token.json stores the user's access and refresh tokens, and is
    # created automatically when the authorization flow completes for the first time.
    if os.path.exists('token.json'):
        creds = Credentials.from_authorized_user_file('token.json', SCOPES)
    
    # If there are no (valid) credentials available, let the user log in.
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            try:
                creds.refresh(Request())
            except Exception as e:
                print(f"Token refresh failed: {e}")
                return None
        else:
            if not os.path.exists('credentials.json'):
                print("credentials.json not found. Skipping interactive login (likely running in a headless environment).")
                return None
            
            # This part will only run locally or where credentials.json is provided
            try:
                flow = InstalledAppFlow.from_client_secret_file('credentials.json', SCOPES)
                creds = flow.run_local_server(port=0)
            except Exception as e:
                print(f"Error during interactive auth flow: {e}")
                return None
        
        # Save the credentials for the next run
        with open('token.json', 'w') as token:
            token.write(creds.to_json())
    
    return build('drive', 'v3', credentials=creds)

def upload_to_gdrive(filename, content):
    """
    Upload a file to a specific Google Drive folder using OAuth2.
    """
    folder_id = os.getenv("GDRIVE_FOLDER_ID")
    if not folder_id:
        print("Skipping Google Drive upload: GDRIVE_FOLDER_ID not set.")
        return None

    try:
        service = get_gdrive_service()

        file_metadata = {
            'name': filename.replace('.md', ''),
            'parents': [folder_id],
            'mimeType': 'application/vnd.google-apps.document'
        }
        
        # Create an in-memory file for upload
        fh = io.BytesIO(content.encode('utf-8'))
        media = MediaIoBaseUpload(fh, mimetype='text/plain', resumable=True)
        
        file = service.files().create(body=file_metadata, media_body=media, fields='id').execute()
        print(f"File uploaded and converted to Google Doc. File ID: {file.get('id')}")
        return file.get('id')
    except Exception as e:
        print(f"Error uploading to Google Drive: {e}")
        return None

def send_email(subject, body):
    if not RESEND_API_KEY:
        print("RESEND_API_KEY not set.")
        return False
    if not RECIPIENT_EMAILS:
        print("RECIPIENT_EMAIL not set (no recipients configured). Skipping email send.")
        return False
        
    try:
        html_content = generate_email_html(body)
        print(f"DEBUG: Attempting to send multi-part email to {RECIPIENT_EMAILS} with subject: {subject}")
        params = {
            "from": SENDER_EMAIL,
            "to": RECIPIENT_EMAILS,
            "subject": subject,
            "text": body,
            "html": html_content
        }
        email = resend.Emails.send(params)
        print(f"Email sent successfully. ID: {email['id']}")
        return True
    except Exception as e:
        print(f"Failed to send email via Resend: {e}")
        return False

def update_history(summary_text):
    # Very simple history update for illustration
    try:
        with open(HISTORY_FILE, "r") as f:
            history = json.load(f)
    except:
        history = []
        
    history.append({
        "date": datetime.datetime.now().strftime("%Y-%m-%d %H:%M"),
        "summary_snippet": summary_text[:200]
    })
    
    with open(HISTORY_FILE, "w") as f:
        json.dump(history, f, indent=2, ensure_ascii=False)

def main():
    jst_now = datetime.datetime.now(JST)
    print(f"Starting Deepfake News Crawler (Gemini Search Mode) at {jst_now} JST...")
    
    summary = generate_report_with_gemini_search()
    
    if not summary or "エラーが発生しました" in summary:
        print("Crawler execution failed.")
        return

    print("--- GENERATED SUMMARY START ---")
    print(summary)
    print("--- GENERATED SUMMARY END ---")

    subject = f"【Deepfake最新ニュース】{jst_now.strftime('%Y/%m/%d')}"

    # Send email FIRST to ensure delivery
    if send_email(subject, summary):
        update_history(summary)
    
    # Save to local file for record
    with open(OUTPUT_FILE, "w") as f:
        f.write(f"# Deepfake News Report - {jst_now.strftime('%Y-%m-%d')}\n\n")
        f.write(summary)
    
    # Upload to Google Drive (if possible)
    today_str = jst_now.strftime('%Y-%m-%d')
    gdrive_filename = f"deepfake_news_{today_str}.md"
    upload_to_gdrive(gdrive_filename, summary)
        
if __name__ == "__main__":
    main()
