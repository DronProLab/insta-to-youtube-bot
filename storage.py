import json
import os

DATA_FILE = "data.json"

# Структура по умолчанию
default_data = {
    "channels": [],
    "videos_found": [],
    "videos_sent": []
}

# ===== Загрузка данных =====
def load_data():
    if not os.path.exists(DATA_FILE):
        with open(DATA_FILE, "w", encoding="utf-8") as f:
            json.dump(default_data, f, indent=4)
        return default_data.copy()

    with open(DATA_FILE, "r", encoding="utf-8") as f:
        return json.load(f)

# ===== Сохранение данных =====
def save_data(data):
    with open(DATA_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=4, ensure_ascii=False)

# ===== Добавить канал =====
def add_channel(channel_url):
    data = load_data()
    if channel_url not in data["channels"]:
        data["channels"].append(channel_url)
        save_data(data)
        return True
    return False

# ===== Получить список каналов =====
def get_channels():
    return load_data()["channels"]

# ===== Добавить новое видео =====
def add_video(video_url):
    data = load_data()
    if video_url not in data["videos_found"]:
        data["videos_found"].append(video_url)
        save_data(data)
        return True
    return False

# ===== Получить неотправленные видео =====
def get_unsent_video():
    data = load_data()
    for video_url in data["videos_found"]:
        if video_url not in data["videos_sent"]:
            return video_url
    return None

# ===== Пометить видео как отправленное =====
def mark_video_as_sent(video_url):
    data = load_data()
    if video_url not in data["videos_sent"]:
        data["videos_sent"].append(video_url)
        save_data(data)
