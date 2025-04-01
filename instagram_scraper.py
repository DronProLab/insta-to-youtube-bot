import instaloader
from storage import get_channels, add_video

def extract_high_view_videos(min_views=100000):
    L = instaloader.Instaloader()
    L.login('your_username', 'your_password')  # или используй без авторизации, если хватает доступа

    channels = get_channels()
    new_videos = []

    for url in channels:
        try:
            username = url.split("/")[-2]
            profile = instaloader.Profile.from_username(L.context, username)
            print(f"🔍 Проверка: {username}")

            for post in profile.get_posts():
                if post.is_video and post.video_view_count >= min_views:
                    video_url = f"https://www.instagram.com/p/{post.shortcode}/"
                    if add_video(video_url):
                        new_videos.append(video_url)

        except Exception as e:
            print(f"⚠️ Ошибка при обработке {url}: {e}")

    return new_videos
