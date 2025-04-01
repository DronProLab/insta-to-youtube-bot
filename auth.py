from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request
from googleapiclient.discovery import build
import os
import json

SCOPES = ["https://www.googleapis.com/auth/youtube.upload"]

def get_authenticated_service():
    creds = None

    if os.path.exists("token.json"):
        with open("token.json", "r") as token:
            creds_data = json.load(token)
            from google.oauth2.credentials import Credentials
            creds = Credentials.from_authorized_user_info(creds_data, SCOPES)

    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            flow = InstalledAppFlow.from_client_secrets_file("credentials.json", SCOPES)
            creds = flow.run_local_server(port=0)

        with open("token.json", "w") as token:
            token.write(creds.to_json())

    return build("youtube", "v3", credentials=creds)
