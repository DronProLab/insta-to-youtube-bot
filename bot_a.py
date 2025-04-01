import os
import telebot
from flask import Flask, request

# Telegram токен
TOKEN = os.getenv("TELEGRAM_BOT_A")
bot = telebot.TeleBot(TOKEN)
app = Flask(__name__)

# Файл для хранения каналов
CHANNEL_FILE = "channels.txt"
if not os.path.exists(CHANNEL_FILE):
    with open(CHANNEL_FILE, "w") as f:
        pass

# ===== Обработка команды /start =====
@bot.message_handler(commands=["start"])
def welcome(msg):
    bot.send_message(msg.chat.id, "Привет! Я БОТ А. Отправь мне ссылку на Instagram-канал, и я её запомню.")

# ===== Обработка ссылок =====
@bot.message_handler(func=lambda m: m.text and "instagram.com" in m.text)
def save_channel(msg):
    url = msg.text.strip()
    chat_id = msg.chat.id

    # Проверим, уже есть такая ссылка?
    with open(CHANNEL_FILE, "r") as f:
        channels = [line.strip() for line in f.readlines()]

    if url in channels:
        bot.send_message(chat_id, "❗️Этот канал уже сохранён.")
    else:
        with open(CHANNEL_FILE, "a") as f:
            f.write(url + "\n")
        bot.send_message(chat_id, "✅ Канал сохранён!")

# ===== Webhook =====
@app.route('/', methods=['GET'])
def index():
    return "BOT A is running", 200

@app.route(f'/{TOKEN}', methods=['POST'])
def webhook():
    json_string = request.get_data().decode('utf-8')
    update = telebot.types.Update.de_json(json_string)
    bot.process_new_updates([update])
    return '', 200

# ===== Установка Webhook =====
if __name__ == "__main__":
    WEBHOOK_URL = f"https://bot-a-name.onrender.com/{TOKEN}"  # Замени на свой render-домен
    bot.remove_webhook()
    bot.set_webhook(url=WEBHOOK_URL)
    app.run(host="0.0.0.0", port=10000)
