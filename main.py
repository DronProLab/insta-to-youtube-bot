import os
import json
import yt_dlp
import logging
import traceback
import schedule
import threading
import time
import telebot
from flask import Flask, request
from auth import get_authenticated_service
from googleapiclient.http import MediaFileUpload

# === ИНИЦИАЛИЗАЦИЯ ===
TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
bot = telebot.TeleBot(TOKEN)
app = Flask(__name__)
SAVE_DIR = "downloads"
os.makedirs(SAVE_DIR, exist_ok=True)
logging.basicConfig(level=logging.INFO)

# === YOUTUBE API ===
youtube = authenticate_youtube()

# === ФАЙЛЫ ===
QUEUE_FILE = "queue.json"
CHANNELS_FILE = "channels.json"
POPULAR_FILE = "popular_videos.json"
UPLOADED_FILE = "uploaded_videos.json"

# === JSON ===
def load_json(file):
    if not os.path.exists(file):
        return []
    with open(file, "r") as f:
        return json.load(f)

def save_json(file, data):
    with open(file, "w") as f:
        json.dump(data, f, indent=4)

# === ЗАГОЛОВОК/ОПИСАНИЕ ===
def generate_title_and_description(raw_description):
    default_description = "Reels video from Instagram #shorts"
    if raw_description:
        title_part = " ".join(raw_description.strip().split()[:7])
        title = f"Like and subscribe – {title_part}".strip()
        return title, raw_description
    return "Like and subscribe", default_description

# === СКАЧИВАНИЕ ===
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

# === ЗАГРУЗКА ===
def upload_to_youtube(video_path, title, raw_description):
    try:
        title, description = generate_title_and_description(raw_description)
        request = youtube.videos().insert(
            part="snippet,status",
            body={
                "snippet": {
                    "title": title,
                    "description": description,
                    "tags": ["shorts", "instagram", "reels"],
                    "categoryId": "22",
                },
                "status": {"privacyStatus": "public"},
            },
            media_body=MediaFileUpload(video_path, chunksize=-1, resumable=True),
        )
        response = request.execute()
        return response.get("id")
    except Exception as e:
        raise Exception(f"Ошибка при загрузке: {e}")

# === ДОБАВЛЕНИЕ КАНАЛА ===
@bot.message_handler(commands=["add_channel"])
def add_channel(message):
    parts = message.text.split()
    if len(parts) != 2:
        bot.reply_to(message, "⚠ Используй: /add_channel <ссылка>")
        return
    url = parts[1].strip()
    channels = load_json(CHANNELS_FILE)
    if url in channels:
        bot.reply_to(message, "✅ Канал уже есть.")
        return
    channels.append(url)
    save_json(CHANNELS_FILE, channels)
    bot.reply_to(message, "✅ Канал добавлен!")

# === СПИСОК КАНАЛОВ ===
@bot.message_handler(commands=["list_channels"])
def list_channels(message):
    channels = load_json(CHANNELS_FILE)
    if not channels:
        bot.reply_to(message, "📭 Список каналов пуст.")
    else:
        msg = "\n".join([f"{i+1}. {c}" for i, c in enumerate(channels)])
        bot.reply_to(message, "📺 Список каналов:\n" + msg)

# === ПАРСИНГ REELS ===
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
            logging.error(f"Ошибка парсинга {ch}: {e}")
    if new_videos:
        save_json(POPULAR_FILE, existing)
        print(f"✅ Добавлено новых Reels: {len(new_videos)}")

# === ЗАГРУЗКА ОДНОГО ВИДЕО ===
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
                video_id = upload_to_youtube(path, "Reels", desc)
                if video_id:
                    uploaded.add(url)
                    save_json(UPLOADED_FILE, list(uploaded))
                    if os.path.exists(path):
                        os.remove(path)
                    print(f"✅ Загружено: https://youtu.be/{video_id}")
        except Exception as e:
            logging.error(f"Ошибка загрузки: {e}")
        break  # Только одно в час

# === РАСПИСАНИЕ ===
def run_schedule():
    schedule.every().day.at("03:00").do(parse_popular_reels)
    schedule.every().hour.do(upload_one_from_popular)
    while True:
        schedule.run_pending()
        time.sleep(60)

# === СТАРТ ===
@bot.message_handler(commands=["start"])
def start(msg):
    bot.reply_to(msg, "Привет! Добавь Instagram-канал командой /add_channel <url>.")

@app.route("/", methods=["GET"])
def index():
    return "Bot is running!", 200

@app.route(f"/{TOKEN}", methods=["POST"])
def webhook():
    json_string = request.get_data().decode("utf-8")
    update = telebot.types.Update.de_json(json_string)
    bot.process_new_updates([update])
    return "", 200

if __name__ == "__main__":
    bot.remove_webhook()
    bot.set_webhook(url=f"https://insta-to-youtube-bot.onrender.com/{TOKEN}")
    threading.Thread(target=run_schedule, daemon=True).start()
    app.run(host="0.0.0.0", port=10000)
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

# ===== Генератор заголовка и описания =====
def generate_title_and_description(raw_description):
    default_description = (
        "Welcome to our channel, where we celebrate the beauty, elegance, and charm of women from all over the world. "
        "Our videos feature glamorous models, stunning photoshoots, and the latest trends in fashion and lifestyle. "
        "We showcase diverse styles, from runway looks to casual beauty, giving you an inside view into the world of elegance and femininity. "
        "Whether you're here for inspiration or simply love fashion, our content brings you a taste of beauty from across the globe.\n\n"
        "#beauty #elegance #fashion #women #glamour #femininity #stylishwomen #internationalwomen #globalbeauty #models #photoshoots "
        "#femaleempowerment #fashiontrends #gracefulwomen #lifestyle #inspiringwomen #fashionmodels #beautytips #luxury "
        "#fashionphotography #modelife #runwaymodels #classywomen #highfashion #stunningwomen #beautifulmodels #hotass #assgirl "
        "#sexyass #sexy #glamorous #worldbeauty #styleicons #glamorouswomen #beautyinfluencers #modelphotos #beautyinspiration "
        "#fashionshows #femininepower #glamourlife #luxurystyle #runwaylooks #elegantstyle #chicstyle #celebrityfashion "
        "#fashionistas #beautygoals #modelinglife #modelingtips #fashionshoot #classylooks #globalmodels #glamorouslife "
        "#beautifulwomen #elegancegoals #makeuptrends #beautyblogger #fashionblogger #beautyinfluencer #makeupartist "
        "#modelingagency #famousmodels #fashionrunway #beautycontest #stunninglooks #fashionevents #chicfashion #modelfashion "
        "#runwaylooks #beautyshoot #glamourphotography #luxuryfashion #highendfashion #celebritymodels #hotgirls #sexygirls "
        "#fashionweek #catwalk #beautyqueen #sexyoutfits #elegantwomen #femalemodels #modelfashion #fashionlovers #beautystyle "
        "#modelinspiration #luxurylifestyle #classymodels #famousfaces #trendystyle #elegantlooks #styleinspo #styleblogger "
        "#beautyshoots #editorialfashion #couturefashion #makeupinspo #celebritystyle #famousmodels #runwayphotography "
        "#glamourmagazine #couturemodels #beautyshots #glamshoot #celebrityglamour"
    )

    if raw_description:
        clean_description = ' '.join(word for word in raw_description.strip().split() if not word.startswith("#"))
        title_part = " ".join(clean_description.split()[:7])
        title = f"Like and subscribe – {title_part}".strip()
        return title, raw_description
    else:
        title = "Like and subscribe"
        return title, default_description

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

CHANNELS_FILE = "channels.json"

def load_channels():
    if not os.path.exists(CHANNELS_FILE):
        return []
    with open(CHANNELS_FILE, "r") as f:
        return json.load(f)

def save_channels(channels):
    with open(CHANNELS_FILE, "w") as f:
        json.dump(channels, f, indent=4)

# Команда: добавить канал
@bot.message_handler(commands=["add_channel"])
def add_channel(message):
    parts = message.text.split()
    if len(parts) != 2:
        bot.reply_to(message, "⚠ Используй: /add_channel <ссылка>")
        return

    url = parts[1].strip()
    channels = load_channels()

    if url in channels:
        bot.reply_to(message, "✅ Канал уже в списке.")
        return

    channels.append(url)
    save_channels(channels)
    bot.reply_to(message, "✅ Канал добавлен!")

# Команда: список каналов
@bot.message_handler(commands=["list_channels"])
def list_channels(message):
    channels = load_channels()
    if not channels:
        bot.reply_to(message, "📭 Список каналов пуст.")
    else:
        response = "📺 Текущие каналы:\n" + "\n".join(f"{idx+1}. {c}" for idx, c in enumerate(channels))
        bot.reply_to(message, response)

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
    WEBHOOK_URL = f"https://insta-to-youtube-bot.onrender.com/{TOKEN}"
    bot.remove_webhook()
    bot.set_webhook(url=WEBHOOK_URL)
    app.run(host="0.0.0.0", port=10000)
