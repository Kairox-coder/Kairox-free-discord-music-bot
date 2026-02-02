import os, asyncio, discord, yt_dlp, aiohttp, gspread
from discord.ext import commands
from google.oauth2.service_account import Credentials
from web import keep_alive

TOKEN = os.getenv("TOKEN")
SHEET_ID = os.getenv("SHEET_ID")
GUILD_LOG_WEBHOOK = os.getenv("GUILD_LOG_WEBHOOK")
INTRO_TRACK_URL = os.getenv("INTRO_TRACK_URL")  # valfri
VOICE_IDLE_SECONDS = int(os.getenv("VOICE_IDLE_SECONDS", "120"))

intents = discord.Intents.default()
intents.voice_states = True
bot = commands.Bot(command_prefix="!", intents=intents)

# ---- Sheets ----
scopes = ["https://www.googleapis.com/auth/spreadsheets"]
creds = Credentials.from_service_account_file("credentials.json", scopes=scopes)
gc = gspread.authorize(creds)
users_ws = gc.open_by_key(SHEET_ID).worksheet("users")
meta_ws = gc.open_by_key(SHEET_ID).worksheet("meta")

# ---- Music ----
ytdlp_opts = {
    "format": "bestaudio/best",
    "quiet": True,
    "default_search": "scsearch",
    "noplaylist": True,
}
ffmpeg_opts = {"options": "-vn"}

queues = {}
played_intro = set()
idle_tasks = {}

async def send_guild_log(msg):
    if not GUILD_LOG_WEBHOOK: return
    try:
        async with aiohttp.ClientSession() as s:
            await s.post(GUILD_LOG_WEBHOOK, json={"content": msg}, timeout=5)
    except:
        pass

def add_play(user_name):
    rows = users_ws.get_all_records()
    for i, r in enumerate(rows, start=2):
        if r["display_name"] == user_name:
            users_ws.update_cell(i, 2, r["plays"] + 1)
            break
    else:
        users_ws.append_row([user_name, 1])

    # meta
    meta = {r["key"]: r["value"] for r in meta_ws.get_all_records()}
    total = int(meta.get("total_plays", 0)) + 1
    meta_ws.update("B1", total)

async def start_idle_timer(guild):
    gid = guild.id
    if gid in idle_tasks:
        idle_tasks[gid].cancel()

    async def timer():
        await asyncio.sleep(VOICE_IDLE_SECONDS)
        vc = guild.voice_client
        if vc and not vc.is_playing():
            await vc.disconnect()
    idle_tasks[gid] = asyncio.create_task(timer())

class YTDL:
    @staticmethod
    async def fetch(q):
        loop = asyncio.get_event_loop()
        with yt_dlp.YoutubeDL(ytdlp_opts) as ydl:
            data = await loop.run_in_executor(None, lambda: ydl.extract_info(q, download=False))
            if "entries" in data:
                data = data["entries"][0]
            return data["url"], data["title"]

async def play_next(guild):
    q = queues.get(guild.id, [])
    vc = guild.voice_client
    if not q or not vc: return
    url, title, user = q.pop(0)
    add_play(user.name)

    src = discord.FFmpegPCMAudio(url, **ffmpeg_opts)
    vc.play(src, after=lambda e: asyncio.run_coroutine_threadsafe(start_idle_timer(guild), bot.loop))

@bot.tree.command(name="play")
async def play(i: discord.Interaction, query: str):
    if not i.user.voice:
        await i.response.send_message("Join a voice channel first.", ephemeral=True); return
    await i.response.defer(ephemeral=True)

    vc = i.guild.voice_client or await i.user.voice.channel.connect()

    if INTRO_TRACK_URL and i.guild.id not in played_intro:
        intro_url, _ = await YTDL.fetch(INTRO_TRACK_URL)
        vc.play(discord.FFmpegPCMAudio(intro_url, **ffmpeg_opts))
        played_intro.add(i.guild.id)
        while vc.is_playing():
            await asyncio.sleep(1)

    url, title = await YTDL.fetch(query)
    queues.setdefault(i.guild.id, []).append((url, title, i.user))
    if not vc.is_playing():
        await play_next(i.guild)

    await i.followup.send(f"▶️ Added: **{title}**", ephemeral=True)

@bot.tree.command(name="stop")
async def stop(i: discord.Interaction):
    if i.guild.voice_client:
        await i.guild.voice_client.disconnect()
    queues[i.guild.id] = []
    await i.response.send_message("Stopped.", ephemeral=True)

@bot.event
async def on_guild_join(g):
    await send_guild_log(f"🟢 Joined **{g.name}** ({g.member_count} members)")

@bot.event
async def on_guild_remove(g):
    await send_guild_log(f"🔴 Left **{g.name}**")

@bot.event
async def on_ready():
    keep_alive()
    await bot.tree.sync()
    print("Music bot online")

bot.run(TOKEN)
