import sqlite3

def init_db():
    conn = sqlite3.connect("bot_data.db")
    cursor = conn.cursor()

    cursor.execute('''
        CREATE TABLE IF NOT EXISTS channels (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            url TEXT UNIQUE
        )
    ''')

    cursor.execute('''
        CREATE TABLE IF NOT EXISTS videos (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            video_url TEXT UNIQUE,
            views INTEGER,
            channel_url TEXT
        )
    ''')

    cursor.execute('''
        CREATE TABLE IF NOT EXISTS sent_videos (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            video_url TEXT UNIQUE
        )
    ''')

    conn.commit()
    conn.close()
