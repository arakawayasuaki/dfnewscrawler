import os
import io
import json
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from dotenv import load_dotenv

load_dotenv()

SCOPES = ['https://www.googleapis.com/auth/drive.readonly']

def check_file_visibility():
    creds = None
    if os.path.exists('token.json'):
        creds = Credentials.from_authorized_user_file('token.json', SCOPES)
    
    if not creds or not creds.valid:
        print("Error: No valid token.json found. Please run the crawler or test script first.")
        return

    try:
        service = build('drive', 'v3', credentials=creds)
        
        # List the last few files in the target folder
        folder_id = os.getenv("GDRIVE_FOLDER_ID")
        query = f"'{folder_id}' in parents and trashed = false"
        
        results = service.files().list(
            q=query, fields="files(id, name, mimeType, owners, webViewLink)", pageSize=10
        ).execute()
        
        files = results.get('files', [])
        
        if not files:
            print(f"No files found in folder: {folder_id}")
        else:
            print(f"Found {len(files)} files in folder:")
            for file in files:
                owner_email = file.get('owners', [{}])[0].get('emailAddress', 'Unknown')
                print(f"- Name: {file['name']}")
                print(f"  ID: {file['id']}")
                print(f"  MimeType: {file['mimeType']}")
                print(f"  Owner: {owner_email}")
                print(f"  Link: {file['webViewLink']}")
                print("-" * 20)

    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    check_file_visibility()
