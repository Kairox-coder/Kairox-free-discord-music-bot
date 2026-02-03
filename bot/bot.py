import os
import asyncio
from datetime import datetime, timedelta

import discord
from discord.ext import commands
import yt_dlp
import aiohttp
import gspread
from google.oauth2.service_account import Credentials
import pytz

from web import keep_alive

# ================= ENV =================
TOKEN = os.getenv("TOKEN")
SHEET_ID = os.getenv("SHEET_ID")
GUILD_LOG_WEBHOOK = os.getenv("GUILD_LOG_WEBHOOK")
VOICE_IDLE_SECONDS = int(os.getenv("VOICE_IDLE_SECONDS", "120"))
TZ = os.getenv("TZ", "UTC")

# Path to Render Secret File
GOOGLE_CREDS_PATH = os.getenv(
    "GOOGLE_APPLICATION_CREDENTIALS",
    "credentials.json"
)

# ================= DISCORD =================
intents = discord.Intents.default()
intents.voice_states = True
bot = commands.Bot(command_prefix="!", intents=intents)

# ================= GOOGLE SHEETS =================
SCOPES = ["https://www.googleapis.com/auth/spreadsheets"]
creds = Credentials.from_service_account_file(
    GOOGLE_CREDS_PATH, scopes=SCOPES
)
gc = gspread.authorize(creds)
sheet = gc.open_by_key(SHEET_ID)

def get_or_create_ws(title, headers):
    try:
        ws = sheet.worksheet(title)
    except gspread.exceptions.WorksheetNotFound:
        ws = sheet.add_worksheet(
            title=title,
            rows=1000,
            cols=len(headers)
        )
        ws.append_row(headers)
    return ws

# worksheets
users_ws = get_or_create_ws(
    "users", ["user_id", "display_name", "plays"]
)
meta_ws = get_or_create_ws(
    "meta", ["key", "value"]
)

def increment_user(user: discord.User):
    rows = users_ws.get_all_records()
    for i, r in enumerate(rows, start=2):
        if str(r["user_id"]) == str(user.id):
            users_ws.update_cell(i, 3, int(r["plays"]) + 1)
            return
    users_ws.append_row([str(user.id), user.name, 1])

def increment_total():
    rows = meta_ws.get_all_records()
    for i, r in enumerate(rows, start=2):
        if r["key"] == "total_plays":
            meta_ws.update_cell(i, 2, int(r["value"]) + 1)
            return
    meta_ws.append_row(["total_plays", 1])

# ================= MUSIC =================
ytdlp_opts = {
    "format": "bestaudio/best",
    "quiet": True,
    "default_search": "scsearch",  # SoundCloud ONLY
    "noplaylist": True,
}

ffmpeg_opts = {
    "options": "-vn -reconnect 1 -reconnect_streamed 1 -reconnect_delay_max 5"
}

queues = {}      # guild_id -> [(url, title, user)]
idle_tasks = {}  # guild_id -> asyncio.Task

# ================= LOGGING =================
async def send_guild_log(message: str):
    if not GUILD_LOG_WEBHOOK:
        return
    try:
        async with aiohttp.ClientSession() as session:
            await session.post(
                GUILD_LOG_WEBHOOK,
                json={"content": message},
                timeout=5
            )
    except:
        pass

# ================= IDLE DISCONNECT =================
async def start_idle_timer(guild: discord.Guild):
    if guild.id in idle_tasks:
        idle_tasks[guild.id].cancel()

    async def timer():
        await asyncio.sleep(VOICE_IDLE_SECONDS)
        vc = guild.voice_client
        if vc and not vc.is_playing():
            await vc.disconnect()

    idle_tasks[guild.id] = asyncio.create_task(timer())

# ================= YTDL =================
class YTDL:
    @staticmethod
    async def fetch(query: str):
        loop = asyncio.get_event_loop()
        with yt_dlp.YoutubeDL(ytdlp_opts) as ydl:
            data = await loop.run_in_executor(
                None,
                lambda: ydl.extract_info(query, download=False)
            )
            if "entries" in data:
                data = data["entries"][0]
            return data["url"], data.get("title", "Unknown")

# ================= PLAYBACK =================
async def play_next(guild: discord.Guild):
    vc = guild.voice_client
    q = queues.get(guild.id, [])

    if not vc or not q:
        await start_idle_timer(guild)
        return

    url, title, user = q.pop(0)

    try:
        increment_user(user)
        increment_total()
    except:
        pass

    source = discord.FFmpegPCMAudio(url, **ffmpeg_opts)

    def after(_):
        asyncio.run_coroutine_threadsafe(
            play_next(guild),
            bot.loop
        )

    vc.play(source, after=after)

# ================= COMMANDS =================
@bot.tree.command(name="play", description="Play a SoundCloud track")
async def play(interaction: discord.Interaction, query: str):
    if not interaction.user.voice:
        await interaction.response.send_message(
            "Join a voice channel first.",
            ephemeral=True
        )
        return

    await interaction.response.defer(ephemeral=True)

    vc = interaction.guild.voice_client
    if not vc:
        vc = await interaction.user.voice.channel.connect()

    url, title = await YTDL.fetch(query)
    queues.setdefault(interaction.guild.id, []).append(
        (url, title, interaction.user)
    )

    if not vc.is_playing():
        await play_next(interaction.guild)

    await interaction.followup.send(
        f"▶️ Added: **{title}**",
        ephemeral=True
    )

@bot.tree.command(name="stop", description="Stop playback and clear queue")
async def stop(interaction: discord.Interaction):
    queues[interaction.guild.id] = []
    vc = interaction.guild.voice_client
    if vc:
        await vc.disconnect()
    await interaction.response.send_message(
        "⏹️ Stopped.",
        ephemeral=True
    )

# ================= DAILY RESTART 03:00 =================
async def daily_restart():
    tz = pytz.timezone(TZ)
    while True:
        now = datetime.now(tz)
        target = now.replace(hour=3, minute=0, second=0, microsecond=0)
        if now >= target:
            target += timedelta(days=1)
        await asyncio.sleep((target - now).total_seconds())
        os._exit(0)

# ================= EVENTS =================
@bot.event
async def on_guild_join(guild):
    await send_guild_log(
        f"🟢 Joined **{guild.name}** ({guild.member_count} members)"
    )

@bot.event
async def on_guild_remove(guild):
    await send_guild_log(
        f"🔴 Left **{guild.name}**"
    )

@bot.event
async def on_ready():
    keep_alive()
    bot.loop.create_task(daily_restart())
    await bot.tree.sync()
    print("🎵 SoundCloud music bot online")

# ================= START =================
bot.run(TOKEN, reconnect=True)
