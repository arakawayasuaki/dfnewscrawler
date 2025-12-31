import os
import datetime
import json
import requests
from bs4 import BeautifulSoup
from googlesearch import search
import google.generativeai as genai
import resend
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
    # Get last 2 days
    now = datetime.datetime.now()
    yesterday = now - datetime.timedelta(days=2)
    
    query = "deepfake news"
    # Note: googlesearch-python doesn't support date range directly in the API call easily
    # so we search and then filter or rely on Google's search result ranking for recent items
    results = []
    
    # Specific site search
    for site in TARGET_SITES:
        site_query = f"site:{site} deepfake"
        try:
            for url in search(site_query, num_results=5):
                results.append(url)
        except Exception as e:
            print(f"Error searching {site}: {e}")

    # General search for latest
    try:
        for url in search(query, num_results=10):
            if url not in results:
                results.append(url)
    except Exception as e:
        print(f"Error in general search: {e}")
        
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
    model = genai.GenerativeModel('gemini-1.5-flash')
    
    # Gather some content to summarize
    content_samples = []
    for url in urls[:10]: # Limit to first 10 URLs
        txt = fetch_content(url)
        if txt:
            content_samples.append(f"Source: {url}\nContent: {txt[:1000]}")
            
    prompt = f"""
    以下のディープフェイクに関する最新ニュース（過去1-2日以内）の情報を要約し、日本語でレポートを作成してください。
    各記事について：
    1. タイトル（日本語）
    2. 要約（日本語）
    3. 出典と日付（判明する場合）
    4. URL
    
    また、これまでに取得した内容と重複しないように配慮してください。
    
    記事情報：
    {chr(10).join(content_samples)}
    """
    
    try:
        response = model.generate_content(prompt)
        return response.text
    except Exception as e:
        return f"Error with Gemini: {e}"

def send_email(subject, body):
    if not RESEND_API_KEY:
        print("RESEND_API_KEY not set.")
        return False
        
    try:
        params = {
            "from": SENDER_EMAIL,
            "to": RECIPIENT_EMAIL,
            "subject": subject,
            "text": body,
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
    if not urls:
        print("No new articles found.")
        return
        
    summary = summarize_with_gemini(urls)
    
    # Save to file
    with open(OUTPUT_FILE, "w") as f:
        f.write(f"# Deepfake News Report - {datetime.datetime.now().strftime('%Y-%m-%d')}\n\n")
        f.write(summary)
        
    # Send email
    subject = f"【Deepfake最新ニュース】{datetime.datetime.now().strftime('%Y/%m/%d')}"
    if send_email(subject, summary):
        update_history(summary)
    
if __name__ == "__main__":
    main()
