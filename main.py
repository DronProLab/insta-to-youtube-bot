import os
import json
import yt_dlp
import traceback
import schedule
import threading
import time
import telebot
from flask import Flask, request
from telebot.types import ReplyKeyboardMarkup, KeyboardButton
from auth import get_authenticated_service
from googleapiclient.http import MediaFileUpload

TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
bot = telebot.TeleBot(TOKEN)
app = Flask(__name__)
SAVE_DIR = "downloads"
os.makedirs(SAVE_DIR, exist_ok=True)

CHANNELS_FILE = "channels.json"
POPULAR_FILE = "popular_videos.json"
UPLOADED_FILE = "uploaded_videos.json"

# === Клавиатура ===
keyboard = ReplyKeyboardMarkup(resize_keyboard=True)
keyboard.add(
    KeyboardButton("📄 Список каналов"),
    KeyboardButton("🛠 Обновить Reels сейчас"),
    KeyboardButton("📤 Загрузить 1 видео сейчас")
)

def load_json(file):
    if not os.path.exists(file):
        return []
    with open(file, "r") as f:
        return json.load(f)

def save_json(file, data):
    with open(file, "w") as f:
        json.dump(data, f, indent=4)

def generate_title_and_description(raw_description):
    default_description = "Reels video from Instagram #shorts"
    if raw_description:
        clean_description = ' '.join(word for word in raw_description.strip().split() if not word.startswith("#"))
        title_part = " ".join(clean_description.split()[:7])
        title = f"Like and subscribe – {title_part}".strip()
        return title, raw_description
    return "Like and subscribe", default_description

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

def upload_to_youtube(video_path, raw_description):
    try:
        youtube = get_authenticated_service()
        title, description = generate_title_and_description(raw_description)

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

def parse_popular_reels():
    channels = load_json(CHANNELS_FILE)
    existing = load_json(POPULAR_FILE)
    existing_urls = {item["url"] for item in existing}
    new_videos = []

    for ch in channels:
        try:
            if not ch.endswith("/"):
                ch += "/"
            reels_url = ch + "reels/"
            ydl_opts = {
                "extract_flat": True,
                "quiet": True,
                "skip_download": True,
                "force_generic_extractor": True,
            }
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                result = ydl.extract_info(reels_url, download=False)
                for entry in result.get("entries", []):
                    url = entry.get("url")
                    views = entry.get("view_count", 0)
                    if url and views and views > 100000 and url not in existing_urls:
                        new_videos.append({"url": url, "views": views})
                        existing.append({"url": url, "views": views})
                        existing_urls.add(url)
        except Exception as e:
            print(f"Ошибка при парсинге {ch}: {e}")

    if new_videos:
        save_json(POPULAR_FILE, existing)
        print(f"✅ Добавлено новых Reels: {len(new_videos)}")

def upload_one_from_popular():
    uploaded = set(load_json(UPLOADED_FILE))
    popular = load_json(POPULAR_FILE)

    for entry in popular:
        url = entry["url"]
        if url in uploaded:
            continue
        try:
            path, desc = download_instagram_video(url)
            if path:
                video_id = upload_to_youtube(path, desc)
                if video_id:
                    uploaded.add(url)
                    save_json(UPLOADED_FILE, list(uploaded))
                    if os.path.exists(path):
                        os.remove(path)
                    print(f"✅ Загружено: https://youtu.be/{video_id}")
        except Exception as e:
            print(f"Ошибка при загрузке: {e}")
        break

@bot.message_handler(commands=["start"])
def welcome(msg):
    bot.send_message(msg.chat.id, "Привет! Добавь Instagram-канал: /add_channel <url>", reply_markup=keyboard)

@bot.message_handler(commands=["add_channel"])
def add_channel(message):
    parts = message.text.split()
    if len(parts) != 2:
        bot.reply_to(message, "⚠ Используй: /add_channel <ссылка>")
        return
    url = parts[1].strip()
    channels = load_json(CHANNELS_FILE)
    if url in channels:
        bot.reply_to(message, "✅ Канал уже в списке.")
        return
    channels.append(url)
    save_json(CHANNELS_FILE, channels)
    bot.reply_to(message, "✅ Канал добавлен!")

@bot.message_handler(func=lambda m: True)
def handle_buttons(message):
    text = message.text.strip()
    chat_id = message.chat.id

    if text == "📄 Список каналов":
        channels = load_json(CHANNELS_FILE)
        if not channels:
            bot.send_message(chat_id, "📭 Список каналов пуст.", reply_markup=keyboard)
        else:
            msg = "\n".join([f"{i+1}. {c}" for i, c in enumerate(channels)])
            bot.send_message(chat_id, "📺 Каналы:\n" + msg, reply_markup=keyboard)

    elif text == "🛠 Обновить Reels сейчас":
        parse_popular_reels()
        bot.send_message(chat_id, "🔄 Reels обновлены!", reply_markup=keyboard)

    elif text == "📤 Загрузить 1 видео сейчас":
        upload_one_from_popular()
        bot.send_message(chat_id, "📤 Загрузка завершена (если было доступное видео).", reply_markup=keyboard)

    elif "instagram.com" in text:
        try:
            bot.send_message(chat_id, "📥 Скачиваю видео...", reply_markup=keyboard)
            video_path, description = download_instagram_video(text)
            bot.send_message(chat_id, "🚀 Загружаю на YouTube...", reply_markup=keyboard)
            youtube_id = upload_to_youtube(video_path, description)
            bot.send_message(chat_id, f"✅ Загружено! https://youtube.com/watch?v={youtube_id}", reply_markup=keyboard)
            if os.path.exists(video_path):
                os.remove(video_path)
        except Exception as e:
            bot.send_message(chat_id, f"❌ Ошибка:\n{str(e)}", reply_markup=keyboard)
    else:
        bot.send_message(chat_id, "❓ Неизвестная команда.", reply_markup=keyboard)

@app.route('/', methods=['GET'])
def index():
    return "Bot is running!", 200

@app.route(f'/{TOKEN}', methods=['POST'])
def webhook():
    json_string = request.get_data().decode('utf-8')
    update = telebot.types.Update.de_json(json_string)
    bot.process_new_updates([update])
    return '', 200

def run_schedule():
    schedule.every().day.at("03:00").do(parse_popular_reels)
    schedule.every().hour.do(upload_one_from_popular)
    while True:
        schedule.run_pending()
        time.sleep(60)

if __name__ == "__main__":
    bot.remove_webhook()
    bot.set_webhook(url=f"https://insta-to-youtube-bot.onrender.com/{TOKEN}")
    threading.Thread(target=run_schedule, daemon=True).start()
    app.run(host="0.0.0.0", port=10000)
