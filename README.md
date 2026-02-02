# 📊 Discord Music Bot + Public Dashboard (100% Free Stack)
Detta projekt består av:
🎵 Discord-bot (SoundCloud-only) – hostas på Render
📄 Google Sheets – privat databas för statistik
🔐 Cloudflare Worker – säkert publikt API
🌍 Cloudflare Pages – publik dashboard (mittnamn.pages.dev)
Allt körs på gratisplaner, är säkert, och redo att länkas i Discord-bio.
🧩 ÖVERSIKT – HUR ALLT HÄNGER IHOP
Kopiera kod

Discord Bot (Render)
   │
   ├─ skriver statistik → Google Sheets (privat)
   │
Cloudflare Worker (API)
   │
   ├─ läser aggregerad data från Sheets
   │
Cloudflare Pages (Dashboard)
   └─ visar leaderboard & statistik publikt
❗ Inga tokens eller nycklar finns i frontend.
# 1️⃣ SKAPA DISCORD-BOT
Gå till https://discord.com/developers/applications
New Application
Bot → Add Bot
Kopiera Bot Token (sparas till Render ENV)
Slå på:
✅ Message Content Intent
✅ Voice State Intent
# 2️⃣ GOOGLE SHEETS (DATABAS)
Skapa Sheet
Skapa ett nytt Google Sheet
Döp flikar:
stats
users
Exempelstruktur – stats
user_id
username
plays
123
Alex
42
# 3️⃣ GOOGLE CLOUD – SERVICE ACCOUNT
Gå till https://console.cloud.google.com
Skapa nytt projekt
Enable:
Google Sheets API
Create Service Account
Skapa JSON key → ladda ner (credentials.json)
Dela Google Sheet med:
Kopiera kod

service-account@project.iam.gserviceaccount.com
⚠️ credentials.json ska ALDRIG ligga i frontend
# 4️⃣ HOSTA DISCORD-BOT PÅ RENDER
Skapa service
https://render.com → New Web Service
Koppla GitHub-repo
Start command:
Kopiera kod
Bash
python bot.py
Environment Variables (Render)
Kopiera kod

TOKEN=DISCORD_BOT_TOKEN
SHEET_ID=xxxxxxxxxxxx
INTRO_TRACK_URL=https://soundcloud.com/your-intro
VOICE_IDLE_SECONDS=120
GUILD_LOG_WEBHOOK=https://discord.com/api/webhooks/...
PORT=10000
credentials.json
Upload som Secret File
Mount till /opt/render/project/src/credentials.json
# 5️⃣ CLOUDFLARE WORKER (API)
Skapa Worker
Kopiera kod
Bash
npm install -g wrangler
wrangler login
wrangler create dashboard-api
Worker:
Läser endast aggregerad data
Returnerar:
Kopiera kod
Json
{
  "top_users": [...],
  "total_plays": 1234
}
⚠️ Inga Discord-ID eller tokens skickas vidare.
# 6️⃣ CLOUDFLARE PAGES (DASHBOARD)
Skapa Pages-projekt
Koppla frontend-mapp
Sidan är helt statisk
Frontend hämtar data:
Kopiera kod
Js
fetch("https://api.mittnamn.workers.dev")
Dashboard innehåller:
🏆 Top users (/play)
📈 Totala plays
🤖 Bot-invite-knapp
# 7️⃣ SÄKERHET – GARANTIER
Sak
Status
Tokens i frontend
❌ Aldrig
Sheets publikt
❌ Nej
Dashboard write access
❌ Read-only
HTTPS
✅ Alltid
Gratisplan
✅ 100%
# 8️⃣ HUR MAN UPPDATERAR
Vill ändra
Var
Bot token
Render ENV
Intro-ljud
Render ENV
Dashboard design
Pages
Statistik
Sheets
# 9️⃣ KLART 🎉
Nu har du:
Säker Discord-musikbot
Publik leaderboard
Globalt snabb dashboard
Bio-säker länk
Inga betalkrav
