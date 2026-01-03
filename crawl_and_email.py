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
RECIPIENT_EMAIL = os.getenv("RECIPIENT_EMAIL", "packyas@gmail.com")
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
    Google検索を使用して、最新のディープフェイク（Deepfake）に関するニュースや動向（過去24時間〜48時間以内）を網羅的に調査し、日本語で詳細なレポートを作成してください。

    {additional_instr}

    【レポートの構成 - 厳格守付】
    1. **主要ニュースのまとめ (10件〜15件程度)**
       - 各項目には以下の内容を必ず含めてください：
         - 番号付きの見出し：記事のタイトル（※必ず日本語に翻訳すること）
         - 内容の要約：具体的かつ客観的に3〜4文程度で記述（※必ず日本語で記述すること）
         - 出典：必ず `出典: [メディア名・サイト名](URL)` の Markdown 形式で記述（※URLは絶対に省略せず、メディア名も日本語にすること）
    
    2. **その他の注目見出し (可能な限り多数)**
       - 上記に含められなかったニュースやブログ、技術レポート等を、タイトルと出典リンクの形式でリストアップしてください。
       - 形式：`* [記事タイトル（要日本語翻訳）](URL) - メディア名`

    【最重要項目：必ず守ってください】
    - **完全日本語化**: 検索結果が英語、中国語、その他の言語であっても、出力はタイトルから要約、メディア名に至るまで全て流暢な日本語で行ってください。
    - **リンクの網羅**: 出典には必ず `[テキスト](URL)` 形式のMarkdownリンクを含めてください。URLの付いていない情報は不要です。
    - **挨拶の禁止**: 「承知いたしました」「検索しました」「レポートを作成します」などの冒頭の挨拶、および末尾の結びの言葉は一切出力しないでください。レポートのタイトルから直接始めてください。
    - **情報の鮮度**: 今日・昨日、または直近2日間の情報を最優先してください。
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
        return response.text
    except Exception as e:
        print(f"Error with Gemini Search: {e}")
        return f"レポート生成中にエラーが発生しました: {e}"

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
        
    try:
        html_content = generate_email_html(body)
        print(f"DEBUG: Attempting to send multi-part email to {RECIPIENT_EMAIL} with subject: {subject}")
        params = {
            "from": SENDER_EMAIL,
            "to": RECIPIENT_EMAIL,
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
