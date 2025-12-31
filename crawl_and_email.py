import os
import datetime
import json
import requests
import random
import markdown
from bs4 import BeautifulSoup
from duckduckgo_search import DDGS
import google.generativeai as genai
import resend
from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseUpload
from google.oauth2 import service_account
import io
from dotenv import load_dotenv

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

# Site list from workflow
TARGET_SITES = [
    "gizmodo.com",
    "cyberscoop.com",
    "gigazine.net",
    "soumu.go.jp",
    "digital.go.jp",
    "cas.go.jp" # 内閣府
]

def search_news():
    print("Searching for news...")
    results = []
    
    with DDGS() as ddgs:
        # General search for latest (both English and Japanese)
        queries = [
            "ディープフェイク ニュース 自民党",
            "ディープフェイク 最新 対策",
            "deepfake news latest 2025",
            "AI 偽動画 被害"
        ]
        
        for q in queries:
            try:
                print(f"Searching for: {q}")
                # DDGS text search supports 'timelimit' (d: day, w: week, m: month)
                ddgs_results = ddgs.text(q, max_results=15, timelimit="w")
                for r in ddgs_results:
                    url = r['href']
                    if url not in results:
                        results.append(url)
            except Exception as e:
                print(f"Error in general search for '{q}': {e}")
                
        # Site specific search
        for site in TARGET_SITES:
            is_japenese_site = site in ["gigazine.net", "soumu.go.jp", "digital.go.jp", "cas.go.jp"]
            query_word = "ディープフェイク" if is_japenese_site else "deepfake"
            site_query = f"site:{site} {query_word}"
            try:
                ddgs_results = ddgs.text(site_query, max_results=5, timelimit="w")
                for r in ddgs_results:
                    url = r['href']
                    # Clean up: ignore relative paths and non-http links
                    if url.startswith("http") and url not in results:
                        results.append(url)
            except Exception as e:
                print(f"Error searching {site}: {e}")
    print(f"Total unique URLs found: {len(results)}")
    return list(set(results))

def fetch_content(url):
    try:
        response = requests.get(url, timeout=10)
        soup = BeautifulSoup(response.text, 'html.parser')
        # Simple heuristic to get main text
        for script in soup(["script", "style"]):
            script.decompose()
        text = soup.get_text(separator=' ', strip=True)
        return text[:5000] # Limit size for LLM
    except Exception as e:
        print(f"Error fetching {url}: {e}")
        return None

def summarize_with_gemini(urls):
    if not GEMINI_API_KEY:
        return "Gemini API Key is not set."
    
    genai.configure(api_key=GEMINI_API_KEY)
    model = genai.GenerativeModel('models/gemini-2.0-flash')
    
    # Shuffle URLs to get diverse results if many
    shuffled_urls = list(urls)
    random.shuffle(shuffled_urls)
    
    # Gather some content to summarize
    content_samples = []
    for url in shuffled_urls[:20]: # Increase limit to 20
        txt = fetch_content(url)
        if txt:
            content_samples.append(f"Source: {url}\nContent: {txt[:1000]}")
            
    if not content_samples:
        return None

    today = datetime.date.today().strftime('%Y年%m月%d日')
    prompt = f"""
    今日は {today} です。
    以下のディープフェイクに関する最新ニュース（過去1-2日以内）の情報を要約し、日本語で詳細なレポートを作成してください。
    
    【重要指示】
    - 発見されたニュースをできるだけ多く（最大15件程度）個別にリストアップしてください。
    - 各記事について以下の構成で作成してください：
        1. タイトル（日本語）
        2. 要約（日本語で2-3文程度）
        3. 出典と日付（判明する場合）
        4. URL
    
    記事情報：
    {chr(10).join(content_samples)}
    """
    
    try:
        response = model.generate_content(prompt)
        return response.text
    except Exception as e:
        print(f"Error with Gemini: {e}")
        return None

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

def upload_to_gdrive(filename, content):
    """
    Upload a file to a specific Google Drive folder using a service account.
    """
    folder_id = os.getenv("GDRIVE_FOLDER_ID")
    service_account_info = os.getenv("GOOGLE_SERVICE_ACCOUNT_INFO")
    
    if not folder_id or not service_account_info:
        print("Skipping Google Drive upload: GDRIVE_FOLDER_ID or GOOGLE_SERVICE_ACCOUNT_INFO not set.")
        return None

    try:
        # Load credentials from environment variable
        info = json.loads(service_account_info)
        creds = service_account.Credentials.from_service_account_info(
            info, scopes=['https://www.googleapis.com/auth/drive.file']
        )
        service = build('drive', 'v3', credentials=creds)

        file_metadata = {
            'name': filename,
            'parents': [folder_id]
        }
        
        # Create an in-memory file for upload
        fh = io.BytesIO(content.encode('utf-8'))
        media = MediaIoBaseUpload(fh, mimetype='text/markdown', resumable=True)
        
        file = service.files().create(body=file_metadata, media_body=media, fields='id').execute()
        print(f"File uploaded to Google Drive. File ID: {file.get('id')}")
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
    print("Starting Deepfake News Crawler...")
    urls = search_news()
    
    subject = f"【Deepfake最新ニュース】{datetime.datetime.now().strftime('%Y/%m/%d')}"
    
    if not urls:
        print("No new articles found.")
        summary = "本日（過去1-2日）の新しいディープフェイク関連ニュースは見つかりませんでした。"
        send_email(subject, summary)
        return
        
    summary = summarize_with_gemini(urls)
    
    if not summary or "Error with Gemini" in summary:
        print("Summarization failed or hit quota, providing URL list as fallback.")
        summary = "## 発見されたニュースURL（要約取得制限中）\n\n"
        summary += "Geminiでの要約生成が制限されています。以下に発見されたニュースのURL（上位15件）を記載します：\n\n"
        for url in urls[:15]:
            summary += f"- {url}\n"
        summary += "\n※Gemini APIの無料枠制限（Quota）に達した可能性があります。詳細な要約が必要な場合は、しばらく時間をおいてから再実行するか、直接ソースをご確認ください。"

    # Save to file
    with open(OUTPUT_FILE, "w") as f:
        f.write(f"# Deepfake News Report - {datetime.datetime.now().strftime('%Y-%m-%d')}\n\n")
        f.write(summary)
    
    # Upload to Google Drive
    today_str = datetime.datetime.now().strftime('%Y-%m-%d')
    gdrive_filename = f"deepfake_news_{today_str}.md"
    upload_to_gdrive(gdrive_filename, summary)
        
    # Send email
    if send_email(subject, summary):
        update_history(summary)
    
if __name__ == "__main__":
    main()
