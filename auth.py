import json
import requests
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build

# 🔹 Обнови CLIENT_ID и CLIENT_SECRET
CLIENT_ID = "308564230559-f05itdcom329pku28e9lsnjndq1aj8sp.apps.googleusercontent.com"
CLIENT_SECRET = "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"  # Найди его в Google Cloud Console
REFRESH_TOKEN = "1//04pz9c3WluUlBCgYIARAAGAQSNwF-L9IrSoxjq5T7OvA8S76txF92oOWDatCSs5xwROzIfp__drCfXdnCsacmJlHBgXpx88gN2_c"

SCOPES = ["https://www.googleapis.com/auth/youtube.upload"]

def authenticate_youtube():
    creds = Credentials.from_authorized_user_info({
        "token": "",
        "refresh_token": REFRESH_TOKEN,
        "token_uri": "https://oauth2.googleapis.com/token",
        "client_id": CLIENT_ID,
        "client_secret": CLIENT_SECRET,
        "scopes": SCOPES
    })

    creds.refresh(Request())  # ✅ Автообновление токена
    return build("youtube", "v3", credentials=creds)

# Проверяем авторизацию
youtube = authenticate_youtube()
print("✅ Авторизация успешна!")
