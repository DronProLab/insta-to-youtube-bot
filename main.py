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
