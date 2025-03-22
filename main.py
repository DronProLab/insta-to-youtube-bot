import os
import sys
import telebot
import yt_dlp
import schedule
import time
import logging
import threading
import json
import re
import requests
from datetime import datetime, timedelta
from telebot.types import ReplyKeyboardMarkup, KeyboardButton
from auth import authenticate_youtube
from googleapiclient.http import MediaFileUpload
from dotenv import load_dotenv

# Загрузка .env и сброс polling-конфликтов
load_dotenv()

def reset_polling_conflicts():
    token = os.getenv("TELEGRAM_BOT_TOKEN")
    url = f"https://api.telegram.org/bot{token}/deleteWebhook"
    try:
        response = requests.get(url)
        if response.status_code == 200:
            print("🔁 Webhook удалён — polling разблокирован")
        else:
            print(f"⚠ Не удалось удалить Webhook: {response.text}")
    except Exception as e:
        print(f"❌ Ошибка при удалении Webhook: {e}")

reset_polling_conflicts()

# Переменные
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
ADMIN_ID = int(os.getenv("ADMIN_ID", 0))

bot = telebot.TeleBot(TELEGRAM_BOT_TOKEN)

MAX_QUEUE_SIZE = 50
DAILY_UPLOAD_LIMIT = 10
QUEUE_FILE = "queue.json"
video_queue = []

logging.basicConfig(filename="logs.txt", level=logging.ERROR, format="%(asctime)s - %(levelname)s - %(message)s")

def save_queue():
    try:
        with open(QUEUE_FILE, "w") as f:
            json.dump(video_queue, f, indent=4)
    except Exception as e:
        logging.error(f"Ошибка сохранения очереди: {e}")

def load_queue():
    global video_queue
    try:
        if os.path.exists(QUEUE_FILE):
            with open(QUEUE_FILE, "r") as f:
                video_queue = json.load(f)
    except Exception as e:
        logging.error(f"Ошибка загрузки очереди: {e}")

load_queue()

keyboard = ReplyKeyboardMarkup(resize_keyboard=True)
keyboard.add(KeyboardButton("🔄 Проверить статус"), KeyboardButton("🚀 Загрузить сейчас"))

youtube = authenticate_youtube()

def download_instagram_video(url):
    save_path = "downloads"
    if not os.path.exists(save_path):
        os.makedirs(save_path)

    options = {
        "outtmpl": f"{save_path}/%(title)s.%(ext)s",
        "quiet": True,
        "format": "bestvideo[ext=mp4]+bestaudio[ext=m4a]/best[ext=mp4]/best[ext=webm]",
        "merge_output_format": "mp4",
    }

    try:
        with yt_dlp.YoutubeDL(options) as ydl:
            info = ydl.extract_info(url, download=True)
            video_path = ydl.prepare_filename(info)
            description = info.get("description", "")
        return video_path, description
    except Exception as e:
        logging.error(f"Ошибка скачивания видео: {e}")
        return None, None

def upload_to_youtube(video_path, title, description):
    try:
        request = youtube.videos().insert(
            part="snippet,status",
            body={
                "snippet": {
                    "title": title,
                    "description": description,
                    "tags": ["shorts", "инстаграм", "short"],
                    "categoryId": "22",
                },
                "status": {"privacyStatus": "public"},
            },
            media_body=MediaFileUpload(video_path, chunksize=-1, resumable=True)
        )
        response = request.execute()
        return response["id"]
    except Exception as e:
        logging.error(f"Ошибка загрузки видео: {e}")
        return None

def process_queue():
    if video_queue:
        chat_id, video_path, description = video_queue.pop(0)
        save_queue()
        title = os.path.basename(video_path).replace(".mp4", "")
        try:
            video_id = upload_to_youtube(video_path, title, description)
            if video_id:
                bot.send_message(chat_id, f"🎥 Видео загружено: https://www.youtube.com/watch?v={video_id}")
                if os.path.exists(video_path):
                    os.remove(video_path)
        except Exception as e:
            logging.error(f"Ошибка загрузки видео: {e}")
            bot.send_message(chat_id, f"❌ Ошибка загрузки: {e}")

@bot.message_handler(content_types=["text"])
def handle_message(message):
    text = message.text.strip()
    instagram_pattern = r"(https?:\/\/)?(www\.)?(instagram\.com\/\S+)"
    match = re.search(instagram_pattern, text)

    if match:
        if len(video_queue) >= MAX_QUEUE_SIZE:
            bot.send_message(message.chat.id, "⚠ Очередь заполнена!", reply_markup=keyboard)
            return

        bot.send_message(message.chat.id, "📥 Скачиваю видео...", reply_markup=keyboard)
        video_path, description = download_instagram_video(match.group(0))

        if video_path:
            video_queue.append((message.chat.id, video_path, description))
            save_queue()
            bot.send_message(message.chat.id, "✅ Видео добавлено в очередь!", reply_markup=keyboard)
        else:
            bot.send_message(message.chat.id, "❌ Ошибка скачивания видео.", reply_markup=keyboard)

    elif text == "🔄 Проверить статус":
        now = datetime.now()
        next_upload_time = datetime.combine(now.date(), datetime.strptime("10:00", "%H:%M").time())
        if now > next_upload_time:
            next_upload_time += timedelta(days=1)
        time_remaining = next_upload_time - now
        hours, remainder = divmod(time_remaining.seconds, 3600)
        minutes, _ = divmod(remainder, 60)

        if not video_queue:
            bot.send_message(message.chat.id, f"🎬 Очередь пуста.\n⏳ До загрузки: {hours} ч {minutes} мин", reply_markup=keyboard)
        else:
            queue_info = f"📌 В очереди {len(video_queue)} видео (загрузится {min(len(video_queue), DAILY_UPLOAD_LIMIT)}):\n"
            for idx, (_, video_path, _) in enumerate(video_queue[:10], 1):
                queue_info += f"{idx}. {os.path.basename(video_path)}\n"
            queue_info += f"\n⏳ До загрузки: {hours} ч {minutes} мин"
            bot.send_message(message.chat.id, queue_info, reply_markup=keyboard)

    elif text == "🚀 Загрузить сейчас":
        if not video_queue:
            bot.send_message(message.chat.id, "⚠ Очередь пуста.", reply_markup=keyboard)
        else:
            bot.send_message(message.chat.id, "🚀 Начинаю загрузку всех видео...", reply_markup=keyboard)
            while video_queue:
                process_queue()
                time.sleep(5)
            bot.send_message(message.chat.id, "✅ Все видео загружены!", reply_markup=keyboard)

def scheduled_upload():
    videos_to_upload = min(len(video_queue), DAILY_UPLOAD_LIMIT)
    for _ in range(videos_to_upload):
        process_queue()

schedule.every().day.at("10:00").do(scheduled_upload)

def run_schedule():
    while True:
        schedule.run_pending()
        time.sleep(60)

try:
    threading.Thread(target=run_schedule, daemon=True).start()
    bot.polling(none_stop=True)
except Exception as e:
    logging.error(f"Ошибка в боте: {e}")
    bot.send_message(ADMIN_ID, f"❌ Бот упал: {e}")
    os.execv(sys.executable, ['python'] + sys.argv)
