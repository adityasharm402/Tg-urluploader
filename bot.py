import os
import re
import asyncio
import subprocess
import threading
from flask import Flask
from pyrogram import Client, filters
from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton

API_ID = int(os.getenv("API_ID"))
API_HASH = os.getenv("API_HASH")
BOT_TOKEN = os.getenv("BOT_TOKEN")

DOWNLOAD_DIR = "downloads"
os.makedirs(DOWNLOAD_DIR, exist_ok=True)

app = Flask(__name__)

bot = Client(
    "url-uploader",
    api_id=API_ID,
    api_hash=API_HASH,
    bot_token=BOT_TOKEN
)

user_data = {}

@app.route("/")
def home():
    return "Bot running 🚀"

# ─── START ────────────────────────────────────────────────
@bot.on_message(filters.command("start"))
async def start(_, m):
    await m.reply(
        "👋 **Welcome!**\n\n"
        "📥 Send me a video URL (m3u8/mpd/direct)\n"
        "🎞 I’ll download it like **1DM Browser**\n\n"
        "✅ Quality selection\n"
        "✅ File rename\n"
        "✅ Progress bar",
        quote=True
    )

# ─── URL RECEIVED ─────────────────────────────────────────
@bot.on_message(filters.text & ~filters.command)
async def url_handler(_, m):
    user_data[m.from_user.id] = {"url": m.text}

    kb = InlineKeyboardMarkup([
        [
            InlineKeyboardButton("1080p", callback_data="q_1080"),
            InlineKeyboardButton("720p", callback_data="q_720")
        ],
        [
            InlineKeyboardButton("480p", callback_data="q_480"),
            InlineKeyboardButton("Best", callback_data="q_best")
        ]
    ])

    await m.reply("🎞 Select quality:", reply_markup=kb)

# ─── QUALITY SELECT ───────────────────────────────────────
@bot.on_callback_query(filters.regex("^q_"))
async def quality_select(_, c):
    q = c.data.split("_")[1]
    user_data[c.from_user.id]["quality"] = q
    await c.message.edit_text("✏️ Send file name (without .mp4):")

# ─── FILE NAME ────────────────────────────────────────────
@bot.on_message(filters.text & ~filters.command)
async def filename_handler(_, m):
    uid = m.from_user.id
    if uid not in user_data or "quality" not in user_data[uid]:
        return

    user_data[uid]["name"] = re.sub(r"[^\w\s-]", "", m.text)
    await m.reply("⏳ Download started...")
    await download_and_upload(m)

# ─── DOWNLOAD + UPLOAD ────────────────────────────────────
async def download_and_upload(m):
    uid = m.from_user.id
    data = user_data[uid]

    url = data["url"]
    quality = data["quality"]
    name = data["name"]
    out = f"{DOWNLOAD_DIR}/{uid}.mp4"

    scale = {
        "1080": "scale=1920:1080",
        "720": "scale=1280:720",
        "480": "scale=854:480",
        "best": None
    }[quality]

    cmd = ["ffmpeg", "-y", "-i", url]
    if scale:
        cmd += ["-vf", scale]
    cmd += ["-c:a", "copy", out]

    status = await m.reply("📥 Downloading: 0%")

    process = subprocess.Popen(
        cmd,
        stderr=subprocess.PIPE,
        text=True
    )

    duration = None

    while True:
        line = process.stderr.readline()
        if not line:
            break

        if "Duration" in line:
            t = line.split("Duration:")[1].split(",")[0]
            h, m_, s = t.split(":")
            duration = int(h)*3600 + int(m_)*60 + int(float(s))

        if "time=" in line and duration:
            cur = line.split("time=")[1].split(" ")[0]
            h, m_, s = cur.split(":")
            sec = int(h)*3600 + int(m_)*60 + int(float(s))
            percent = min(int(sec * 100 / duration), 100)
            await status.edit_text(f"📥 Downloading: {percent}%")

    process.wait()

    await status.edit_text("📤 Uploading: 0%")

    async def progress(cur, total):
        percent = int(cur * 100 / total)
        await status.edit_text(f"📤 Uploading: {percent}%")

    await m.reply_video(
        out,
        file_name=f"{name}.mp4",
        progress=progress
    )

    os.remove(out)
    user_data.pop(uid, None)

# ─── RUN ─────────────────────────────────────────────────
def run_bot():
    bot.run()

if __name__ == "__main__":
    threading.Thread(target=run_bot).start()
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 10000)))
