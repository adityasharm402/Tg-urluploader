import os
import re
import asyncio
import subprocess
import threading
from flask import Flask
from pyrogram import Client, filters
from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton

# ─── ENV ───────────────────────────────────────────────
API_ID = int(os.getenv("API_ID"))
API_HASH = os.getenv("API_HASH")
BOT_TOKEN = os.getenv("BOT_TOKEN")

DOWNLOAD_DIR = "downloads"
os.makedirs(DOWNLOAD_DIR, exist_ok=True)

# ─── FLASK APP (KEEP RENDER ALIVE) ─────────────────────
app = Flask(__name__)

@app.route("/")
def home():
    return "Bot running 🚀"

# ─── PYROGRAM BOT ──────────────────────────────────────
bot = Client(
    "url-uploader",
    api_id=API_ID,
    api_hash=API_HASH,
    bot_token=BOT_TOKEN
)

# ─── USER STATE ────────────────────────────────────────
user_state = {}

# ─── START COMMAND ─────────────────────────────────────
@bot.on_message(filters.command("start"))
async def start(_, m):
    user_state.pop(m.from_user.id, None)
    await m.reply(
        "👋 **Welcome!**\n\n"
        "📥 Send a video URL (m3u8 / mpd / direct)\n"
        "🎞 Like **1DM Browser**\n\n"
        "✅ Quality selector\n"
        "✅ Rename file\n"
        "✅ Progress bar"
    )

# ─── URL HANDLER ───────────────────────────────────────
@bot.on_message(filters.text & ~filters.command)
async def text_handler(_, m):
    uid = m.from_user.id
    text = m.text.strip()

    # Step 1: URL
    if uid not in user_state:
        user_state[uid] = {"url": text}

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
        return

    # Step 3: Filename
    if user_state[uid].get("awaiting_name"):
        name = re.sub(r"[^\w\s-]", "", text)
        user_state[uid]["name"] = name
        user_state[uid]["awaiting_name"] = False
        await m.reply("⏳ Download started...")
        await download_and_upload(m)

# ─── QUALITY CALLBACK ──────────────────────────────────
@bot.on_callback_query(filters.regex("^q_"))
async def quality_handler(_, c):
    uid = c.from_user.id
    quality = c.data.split("_")[1]

    if uid not in user_state:
        await c.answer("Send URL first", show_alert=True)
        return

    user_state[uid]["quality"] = quality
    user_state[uid]["awaiting_name"] = True

    await c.message.edit_text("✏️ Send file name (without .mp4):")

# ─── DOWNLOAD + UPLOAD ─────────────────────────────────
async def download_and_upload(m):
    uid = m.from_user.id
    data = user_state[uid]

    url = data["url"]
    quality = data["quality"]
    name = data["name"]

    output = f"{DOWNLOAD_DIR}/{uid}.mp4"

    scale_map = {
        "1080": "scale=1920:1080",
        "720": "scale=1280:720",
        "480": "scale=854:480",
        "best": None
    }

    cmd = ["ffmpeg", "-y", "-i", url]
    if scale_map[quality]:
        cmd += ["-vf", scale_map[quality]]
    cmd += ["-c:a", "copy", output]

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

        if "Duration" in line and not duration:
            t = line.split("Duration:")[1].split(",")[0]
            h, mi, s = t.split(":")
            duration = int(h) * 3600 + int(mi) * 60 + int(float(s))

        if "time=" in line and duration:
            cur = line.split("time=")[1].split(" ")[0]
            h, mi, s = cur.split(":")
            sec = int(h) * 3600 + int(mi) * 60 + int(float(s))
            percent = min(int(sec * 100 / duration), 100)
            await status.edit_text(f"📥 Downloading: {percent}%")

    process.wait()

    await status.edit_text("📤 Uploading: 0%")

    async def progress(cur, total):
        percent = int(cur * 100 / total)
        await status.edit_text(f"📤 Uploading: {percent}%")

    await m.reply_video(
        output,
        file_name=f"{name}.mp4",
        progress=progress
    )

    if os.path.exists(output):
        os.remove(output)

    user_state.pop(uid, None)

# ─── RUN ───────────────────────────────────────────────
def run_flask():
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 10000)))

if __name__ == "__main__":
    # Flask in background
    threading.Thread(target=run_flask).start()

    # Proper asyncio loop for Pyrogram
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)

    bot.run()
