import os
import telebot
import yt_dlp
import traceback
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload
from auth import get_authenticated_service

TOKEN = os.getenv("TELEGRAM_TOKEN")
bot = telebot.TeleBot(TOKEN)

SAVE_DIR = "downloads"
os.makedirs(SAVE_DIR, exist_ok=True)

def download_instagram_video(url):
    try:
        ydl_opts = {
            'outtmpl': f'{SAVE_DIR}/%(upload_date)s_%(id)s.%(ext)s',
            'format': 'mp4',
            'quiet': True,
        }
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=True)
            filename = ydl.prepare_filename(info)
            description = info.get("description", "")
        return filename, description
    except Exception as e:
        raise Exception(f"Ошибка при скачивании: {e}")

def upload_to_youtube(video_path, description):
    try:
        youtube = get_authenticated_service()
        body = {
            'snippet': {
                'title': os.path.basename(video_path).replace("_", " "),
                'description': description,
                'tags': ['Instagram', 'shorts'],
                'categoryId': '22'
            },
            'status': {
                'privacyStatus': 'public'
            }
        }

        media = MediaFileUpload(video_path, mimetype='video/mp4', resumable=True)
        request = youtube.videos().insert(part='snippet,status', body=body, media_body=media)
        response = request.execute()
        return response.get("id")
    except Exception as e:
        raise Exception(f"Ошибка при загрузке: {e}")

@bot.message_handler(commands=["start"])
def welcome(msg):
    bot.send_message(msg.chat.id, "Привет! Отправь ссылку на Instagram-видео для загрузки на YouTube.")

@bot.message_handler(func=lambda m: m.text and "instagram.com" in m.text)
def handle_instagram(msg):
    chat_id = msg.chat.id
    url = msg.text.strip()
    try:
        bot.send_message(chat_id, "📥 Скачиваю видео...")
        video_path, description = download_instagram_video(url)

        bot.send_message(chat_id, "🚀 Загружаю на YouTube...")
        youtube_id = upload_to_youtube(video_path, description)

        bot.send_message(chat_id, f"✅ Загружено! https://youtube.com/watch?v={youtube_id}")

        if os.path.exists(video_path):
            os.remove(video_path)
    except Exception as e:
        error_text = traceback.format_exc()
        bot.send_message(chat_id, f"❌ Ошибка:\n{str(e)}")

bot.polling(none_stop=True)
