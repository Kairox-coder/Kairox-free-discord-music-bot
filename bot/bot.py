import os
import asyncio
import discord
from discord.ext import commands
from web import keep_alive

TOKEN = os.getenv("TOKEN")

intents = discord.Intents.default()
intents.voice_states = True

bot = commands.Bot(command_prefix="!", intents=intents)

@bot.event
async def on_ready():
    keep_alive()
    print(f"✅ Logged in as {bot.user}")

bot.run(TOKEN)
