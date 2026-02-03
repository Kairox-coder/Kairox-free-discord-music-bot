import os
import asyncio
from datetime import datetime, timedelta
import pytz
import discord
from discord.ext import commands
import yt_dlp
import aiohttp
import gspread
from google.oauth2.service_account import Credentials
from web import keep_alive

# ================= ENV =================
TOKEN = os.getenv("TOKEN")
SHEET_ID = os.getenv("SHEET_ID")
GUILD_LOG_WEBHOOK = os.getenv("GUILD_LOG_WEBHOOK")
VOICE_IDLE_SECONDS = int(os.getenv("VOICE_IDLE_SECONDS", "120"))
TZ = os.getenv("TZ", "Europe/Stockholm")
GOOGLE_CREDS_FILE = "/etc/secrets/credentials.json"

# ================= DISCORD =================
intents = discord.Intents.default()
intents.voice_states = True
intents.guilds = True
bot = commands.Bot(command_prefix="!", intents=intents)

# ================= GOOGLE SHEETS =================
scopes = ["https://www.googleapis.com/auth/spreadsheets"]
creds = Credentials.from_service_account_file(GOOGLE_CREDS_FILE, scopes=scopes)
gc = gspread.authorize(creds)
sheet = gc.open_by_key(SHEET_ID)

def get_or_create_ws(title, headers):
    try:
        ws = sheet.worksheet(title)
    except gspread.exceptions.WorksheetNotFound:
        ws = sheet.add_worksheet(title=title, rows=1000, cols=len(headers))
        ws.append_row(headers)
    return ws

users_ws = get_or_create_ws("users", ["display_name", "plays"])
meta_ws = get_or_create_ws("meta", ["key", "value"])

def increment_total():
    rows = meta_ws.get_all_records()
    for i, r in enumerate(rows, start=2):
        if r["key"] == "total_plays":
            meta_ws.update_cell(i, 2, int(r["value"]) + 1)
            return
    meta_ws.append_row(["total_plays", 1])

def add_play(user):
    rows = users_ws.get_all_records()
    for i, r in enumerate(rows, start=2):
        if r["display_name"] == user.name:
            users_ws.update_cell(i, 2, int(r["plays"]) + 1)
            increment_total()
            return
    users_ws.append_row([user.name, 1])
    increment_total()

# ================= MUSIC =================
ytdlp_opts = {
    "format": "bestaudio/best",
    "quiet": True,
    "default_search": "scsearch",
    "noplaylist": True,
}
ffmpeg_opts = {
    "options": "-vn -reconnect 1 -reconnect_streamed 1 -reconnect_delay_max 5"
}

queues = {}
idle_tasks = {}

class YTDL:
    @staticmethod
    async def fetch(query):
        loop = asyncio.get_event_loop()
        with yt_dlp.YoutubeDL(ytdlp_opts) as ydl:
            data = await loop.run_in_executor(
                None, lambda: ydl.extract_info(query, download=False)
            )
            if "entries" in data:
                data = data["entries"][0]
            return data["url"], data.get("title", "Unknown")

async def idle_timer(guild):
    await asyncio.sleep(VOICE_IDLE_SECONDS)
    vc = guild.voice_client
    if vc and not vc.is_playing():
        await vc.disconnect()

async def play_next(guild):
    vc = guild.voice_client
    q = queues.get(guild.id, [])
    if not vc or not q:
        return

    url, title, user = q.pop(0)
    try:
        add_play(user)
    except:
        pass

    src = discord.FFmpegPCMAudio(url, **ffmpeg_opts)

    def after(_):
        asyncio.run_coroutine_threadsafe(play_next(guild), bot.loop)

    vc.play(src, after=after)

# ================= COMMANDS =================
@bot.tree.command(name="play")
async def play(i: discord.Interaction, query: str):
    if not i.user.voice:
        await i.response.send_message("Join a voice channel first.", ephemeral=True)
        return

    await i.response.defer(ephemeral=True)

    vc = i.guild.voice_client or await i.user.voice.channel.connect()
    url, title = await YTDL.fetch(query)

    queues.setdefault(i.guild.id, []).append((url, title, i.user))
    if not vc.is_playing():
        await play_next(i.guild)

    await i.followup.send(f"▶️ Added: **{title}**", ephemeral=True)

@bot.tree.command(name="stop")
async def stop(i: discord.Interaction):
    queues[i.guild.id] = []
    if i.guild.voice_client:
        await i.guild.voice_client.disconnect()
    await i.response.send_message("⏹️ Stopped.", ephemeral=True)

# ================= LOGGING =================
async def log(msg):
    if not GUILD_LOG_WEBHOOK:
        return
    async with aiohttp.ClientSession() as s:
        await s.post(GUILD_LOG_WEBHOOK, json={"content": msg})

@bot.event
async def on_guild_join(g):
    await log(f"🟢 Joined **{g.name}** ({g.member_count})")

@bot.event
async def on_guild_remove(g):
    await log(f"🔴 Left **{g.name}**")

# ================= DAILY RESTART =================
async def daily_restart():
    tz = pytz.timezone(TZ)
    while True:
        now = datetime.now(tz)
        target = now.replace(hour=3, minute=0, second=0, microsecond=0)
        if now >= target:
            target += timedelta(days=1)
        await asyncio.sleep((target - now).total_seconds())
        os._exit(0)

@bot.event
async def on_ready():
    bot.loop.create_task(daily_restart())
    await bot.tree.sync()
    print("🎵 Music bot ONLINE")

# ================= START =================
keep_alive()
bot.run(TOKEN)
