import os, asyncio, discord, yt_dlp, aiohttp, gspread, pytz
from discord.ext import commands
from google.oauth2.service_account import Credentials
from datetime import datetime, timedelta
from web import keep_alive

# ================= ENV =================
TOKEN = os.getenv("TOKEN")
SHEET_ID = os.getenv("SHEET_ID")
GUILD_LOG_WEBHOOK = os.getenv("GUILD_LOG_WEBHOOK")
VOICE_IDLE_SECONDS = int(os.getenv("VOICE_IDLE_SECONDS", "120"))
TZ = os.getenv("TZ", "Europe/Stockholm")

# ================= DISCORD =================
intents = discord.Intents.default()
intents.voice_states = True
bot = commands.Bot(command_prefix="!", intents=intents)

# ================= GOOGLE SHEETS =================
scopes = ["https://www.googleapis.com/auth/spreadsheets"]
creds = Credentials.from_service_account_file("credentials.json", scopes=scopes)
gc = gspread.authorize(creds)
sheet = gc.open_by_key(SHEET_ID)

def get_or_create_ws(name, headers):
    try:
        ws = sheet.worksheet(name)
    except gspread.WorksheetNotFound:
        ws = sheet.add_worksheet(title=name, rows=1000, cols=len(headers))
        ws.append_row(headers)
    return ws

users_ws = get_or_create_ws("users", ["display_name", "plays"])
meta_ws = get_or_create_ws("meta", ["key", "value"])

# ================= MUSIC =================
ytdlp_opts = {
    "format": "bestaudio/best",
    "quiet": True,
    "default_search": "scsearch",   # 🔒 SoundCloud ONLY
    "noplaylist": True,
}

ffmpeg_opts = {
    "options": "-vn -reconnect 1 -reconnect_streamed 1 -reconnect_delay_max 5"
}

queues = {}
idle_tasks = {}

# ================= LOGGING =================
async def send_guild_log(msg):
    if not GUILD_LOG_WEBHOOK:
        return
    try:
        async with aiohttp.ClientSession() as s:
            await s.post(GUILD_LOG_WEBHOOK, json={"content": msg}, timeout=5)
    except:
        pass

# ================= SHEETS =================
def add_play(user):
    rows = users_ws.get_all_records()
    for i, r in enumerate(rows, start=2):
        if r["display_name"] == user.name:
            users_ws.update_cell(i, 2, int(r["plays"]) + 1)
            break
    else:
        users_ws.append_row([user.name, 1])

    meta = {r["key"]: r["value"] for r in meta_ws.get_all_records()}
    total = int(meta.get("total_plays", 0)) + 1
    meta_ws.update("B1", total)

# ================= IDLE LEAVE =================
async def start_idle_timer(guild):
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
    async def fetch(q):
        loop = asyncio.get_event_loop()
        with yt_dlp.YoutubeDL(ytdlp_opts) as ydl:
            data = await loop.run_in_executor(
                None, lambda: ydl.extract_info(q, download=False)
            )
            if "entries" in data:
                data = data["entries"][0]
            return data["url"], data.get("title", "Unknown")

# ================= PLAYBACK =================
async def play_next(guild):
    vc = guild.voice_client
    q = queues.get(guild.id, [])

    if not vc or not q:
        await start_idle_timer(guild)
        return

    url, title, user = q.pop(0)
    try:
        add_play(user)
    except:
        pass

    src = discord.FFmpegPCMAudio(url, **ffmpeg_opts)

    def after(_):
        asyncio.run_coroutine_threadsafe(
            play_next(guild), bot.loop
        )

    vc.play(src, after=after)

# ================= COMMANDS =================
@bot.tree.command(name="play", description="Play SoundCloud track")
async def play(i: discord.Interaction, query: str):
    if not i.user.voice:
        await i.response.send_message(
            "Join a voice channel first.", ephemeral=True
        )
        return

    await i.response.defer(ephemeral=True)

    vc = i.guild.voice_client or await i.user.voice.channel.connect()
    url, title = await YTDL.fetch(query)

    queues.setdefault(i.guild.id, []).append((url, title, i.user))

    if not vc.is_playing():
        await play_next(i.guild)

    await i.followup.send(f"▶️ Added: **{title}**", ephemeral=True)

@bot.tree.command(name="stop", description="Stop music")
async def stop(i: discord.Interaction):
    queues[i.guild.id] = []
    if i.guild.voice_client:
        await i.guild.voice_client.disconnect()
    await i.response.send_message("⏹️ Stopped.", ephemeral=True)

# ================= EVENTS =================
@bot.event
async def on_guild_join(g):
    await send_guild_log(f"🟢 Joined **{g.name}** ({g.member_count})")

@bot.event
async def on_guild_remove(g):
    await send_guild_log(f"🔴 Left **{g.name}**")

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
    keep_alive()
    bot.loop.create_task(daily_restart())
    await bot.tree.sync()
    print("🎵 Music bot ONLINE")

# ================= START =================
bot.run(TOKEN)
