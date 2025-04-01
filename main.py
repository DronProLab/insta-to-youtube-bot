import os
import telebot
import yt_dlp
import traceback
from flask import Flask, request
from auth import get_authenticated_service
from googleapiclient.http import MediaFileUpload

TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
bot = telebot.TeleBot(TOKEN)
app = Flask(__name__)

SAVE_DIR = "downloads"
os.makedirs(SAVE_DIR, exist_ok=True)

# ===== Скачивание видео =====
def download_instagram_video(url):
    try:
        ydl_opts = {
            'outtmpl': f'{SAVE_DIR}/%(title).50s.%(ext)s',
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

# ===== Загрузка на YouTube =====
def upload_to_youtube(video_path, description):
    try:
        youtube = get_authenticated_service()

        # ✅ Формируем красивое название
        if description:
            # Удаляем хештеги и берём первые 7 слов
            clean_description = ' '.join(word for word in description.strip().split() if not word.startswith("#"))
            title_part = " ".join(clean_description.split()[:7])
            title = f"Like and subscribe {title_part}".strip()
        else:
            title = "Like and subscribe      #sexy #wooman #baby #girl #nasty #young #sweaty #ass"

        body = {
            'snippet': {
                'title': title,
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

# ===== Обработка команд =====
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

# ===== Flask Webhook =====
@app.route('/', methods=['GET'])
def index():
    return "Bot is running!", 200

@app.route(f'/{TOKEN}', methods=['POST'])
def webhook():
    json_string = request.get_data().decode('utf-8')
    update = telebot.types.Update.de_json(json_string)
    bot.process_new_updates([update])
    return '', 200

# ===== Установка Webhook =====
if __name__ == "__main__":
    # Укажи свой домен от Render:
    WEBHOOK_URL = f"https://insta-to-youtube-bot.onrender.com/{TOKEN}"
    bot.remove_webhook()
    bot.set_webhook(url=WEBHOOK_URL)
    app.run(host="0.0.0.0", port=10000)
