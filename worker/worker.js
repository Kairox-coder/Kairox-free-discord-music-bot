export default {
  async fetch() {
    const data = {
      total_plays: 18342,
      top_users: [
        { name: "KEX", plays: 124 },
        { name: "Alex", plays: 97 }
      ],
      invite_url: "https://discord.com/oauth2/authorize?client_id=BOT_ID&scope=bot"
    };
    return new Response(JSON.stringify(data), {
      headers: { "Content-Type": "application/json", "Cache-Control": "public, max-age=60" }
    });
  }
};
