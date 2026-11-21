import os
import requests
import json

from dotenv import load_dotenv

_repo_dir = os.path.dirname(os.path.abspath(__file__))
load_dotenv(os.path.join(_repo_dir, ".env"), override=False)

import telebot
from telebot.async_telebot import AsyncTeleBot

# Asosiy sozlamalar (Render Environment Variables dan olinadi)
bot_api = os.environ["SPOT_SEEK_BOT_API"].strip()
database_channel = os.environ["MUSIC_DATABASE_ID"].strip()
log_channel_id = os.environ["LOG_CHANNEL_ID"].strip()

bot = telebot.TeleBot(bot_api)
async_bot = AsyncTeleBot(bot_api, parse_mode="Markdown", disable_web_page_preview=True)

bot_name = os.environ.get("BOT_NAME", "Spot Seek Music Bot")
bot_username = os.environ.get("BOT_USERNAME", "@SpotSeekBot")

last_queries = {}
last_chat_searches = {}

welcome_message = f"""Salom! 👋🎵

Istalgan qo'shiq yoki albom nomini yozib yuboring, masalan:
`Adele - Someone Like You`

Yoki Spotify havolasini (linkini) tashlang 👇
♪ Qo'shiq: https://open.spotify.com/track/734dz1YaFITwawPpM25fSt
🎵 Albom: https://open.spotify.com/album/0Lg1uZvI312TPqxNWShFXL
🎶 Pleylist: https://open.spotify.com/playlist/3ceLS7hutXrwz03g0c11gW
"""

info_message = """Ushbu bot orqali Spotify'dagi istalgan qo'shiq, albom va pleylistlarni yuqori sifatli (320kbps MP3) formatda yuklab olishingiz mumkin."""

privacy_message = """• Bot foydalanuvchilarning shaxsiy ma'lumotlarini yig'maydi."""

deezer_link_message = "Bu Deezer havolasi. Iltimos, Spotify qo'shiq/albom/pleylist havolasini yuboring."
soundcloud_link_message = "Bu SoundCloud havolasi. Iltimos, Spotify havolasini yuboring."
youtube_link_message = "Bu YouTube havolasi. Iltimos, Spotify havolasini yuboring yoki qo'shiq nomini yozing."
instagram_link_message = "Bu Instagram havolasi. Iltimos, Spotify havolasini yuboring yoki qo'shiq nomini yozing."
spotify_episode_link_message = "Podkast epizodlarini yuklab bo'lmaydi. Qo'shiq yoki albom havolasini yuboring."
spotify_artist_link_message = "Ijrochi (artist) profili havolasini emas, qo'shiq yoki albom havolasini yuboring."
spotify_user_link_message = "Foydalanuvchi profili havolasini emas, pleylist yoki qo'shiq havolasini yuboring."

successfull_end_message = "✅ Yuklab olindi!"
starpal_promotion_msg = ""

sth_to_download_message = """⏳ Sizda hozir yuklanayotgan qo'shiq bor, tugashini kuting (30 soniya)."""

wrong_link_message = """❌ Noto'g'ri havola! Qo'shiq nomini yozing yoki to'g'ri Spotify havolasini yuboring."""

directory = "./output/"
simultaneous_downloads = 1
queue_handler_sleep_timer = 5

album_cache_ttl_seconds = 90 * 24 * 3600
playlist_cache_ttl_seconds = 7 * 24 * 3600
search_cache_ttl_seconds = 30 * 24 * 3600

queue_log_flush_tracks = 50
queue_log_flush_seconds = 900
received_links_folder_path = "./received_links"

spotify_shortened_link_pattern = r'https?:\/\/spotify\.link\/[A-Za-z0-9]+'
spotify_track_link_pattern = r'https?:\/\/open\.spotify\.com\/(intl-[a-zA-Z]{2}\/)?track\/[a-zA-Z0-9]+'
spotify_album_link_pattern = r'https?:\/\/open\.spotify\.com\/(intl-[a-zA-Z]{2}\/)?album\/[a-zA-Z0-9]+'
spotify_playlist_link_pattern = r'https?:\/\/open\.spotify\.com\/(intl-[a-zA-Z]{2}\/)?playlist\/[a-zA-Z0-9]+'
spotify_correct_link_pattern = spotify_track_link_pattern + "|" + spotify_album_link_pattern + "|" + spotify_playlist_link_pattern + "|" + spotify_shortened_link_pattern
deezer_link_pattern = r'https?:\/\/(?:www\.)?deezer\.com\/(?:\w{2}\/)?(?:\w+\/)?(?:track|album|artist|playlist)\/\d+'
soundcloud_link_pattern = r"(?:https?://)?(?:www\.)?soundcloud\.com/([a-zA-Z0-9-_]+)/([a-zA-Z0-9-_]+)"
youtube_link_pattern = r"(?:(?:https?:)?//)?(?:www\.)?(?:(?:youtube\.com/(?:watch\?.*v=|embed/|v/)|youtu.be/))([\w-]{11})"
instagram_link_pattern = r'(?:https?://www\.)?instagram\.com\S*?/(p|reel)/([a-zA-Z0-9_-]{11})/?'
spotify_episode_link_pattern = r'https?:\/\/open\.spotify\.com\/(intl-[a-zA-Z]{2}\/)?episode\/[a-zA-Z0-9]+'
spotify_artist_link_pattern = r'https?:\/\/open\.spotify\.com\/(intl-[a-zA-Z]{2}\/)?artist\/[a-zA-Z0-9]+'
spotify_user_link_pattern = r'https?:\/\/open\.spotify\.com\/(intl-[a-zA-Z]{2}\/)?user\/[a-zA-Z0-9]+'

log_bot_url = "https://api.telegram.org/bot" + bot_api + "/"

# Render.com uchun WARP va proxychains o'chirilgan
warp_mode = False
warp_proxies = {}
warp_session = requests.Session()
proxychains4_config_file = ""
socks_proxies = []

private_router_url = ""
private_router_token = ""
promote_channel_username = os.environ.get("PROMOTE_CHANNEL", "")
