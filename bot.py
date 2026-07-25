import os
import asyncio
from flask import Flask
from threading import Thread
import discord
from discord.ext import commands
import yt_dlp
import ffdl  # Sunucuya FFmpeg'i otomatik indiren kütüphane

# --- 0. RENDER İÇİN FFMPEG OTOMATİK KURULUMU ---
try:
    print("🔄 FFmpeg kontrol ediliyor / indiriliyor...")
    ffdl.ffdl()
    print("✅ FFmpeg başarıyla hazırlandı!")
except Exception as e:
    print(f"⚠️ FFmpeg kurulum uyarısı (Zaten yüklü olabilir): {e}")

# --- 1. RENDER İÇİN WEB SUNUCU AYARI (Port Hatasını Önler) ---
app = Flask('')

@app.route('/')
def home():
    return "Bot Aktif!"

def run_web_server():
    # Render PORT'u otomatik atar, bulamazsa 8080 kullanır
    port = int(os.environ.get("PORT", 8080))
    app.run(host='0.0.0.0', port=port)

def keep_alive():
    t = Thread(target=run_web_server)
    t.start()

# --- 2. DISCORD VE YT-DLP AYARLARI ---
intents = discord.Intents.default()
intents.message_content = True
bot = commands.Bot(command_prefix="!", intents=intents)

YTDL_OPTIONS = {
    'format': 'bestaudio/best',
    'noplaylist': True,
    'quiet': True,
    'no_warnings': True,
    'default_search': 'auto',
    'source_address': '0.0.0.0'
}

FFMPEG_OPTIONS = {
    'before_options': '-reconnect 1 -reconnect_streamed 1 -reconnect_delay_max 5',
    'options': '-vn',
}

ytdl = yt_dlp.YoutubeDL(YTDL_OPTIONS)

# --- 3. BOT OLAYLARI VE KOMUTLARI ---
@bot.event
async def on_ready():
    print(f"🤖 Bot başarıyla giriş yaptı: {bot.user.name}")

@bot.command(name="play", help="Şarkı çalar. Kullanım: !play şarkı_adı veya youtube_linki")
async def play(ctx, *, search: str):
    if not ctx.author.voice:
        return await ctx.send("❌ Önce bir ses kanalına girmelisin!")
    
    channel = ctx.author.voice.channel
    voice_client = ctx.voice_client
    
    if not voice_client:
        voice_client = await channel.connect()
    elif voice_client.channel != channel:
        await voice_client.move_to(channel)
        
    await ctx.send(f"🔍 **'{search}'** aranıyor...")

    # Arama veya link işleme
    loop = asyncio.get_event_loop()
    try:
        data = await loop.run_in_executor(None, lambda: ytdl.extract_info(search, download=False))
    except Exception as e:
        return await ctx.send(f"❌ Şarkı bulunamadı veya yüklenemedi: {e}")

    # Eğer arama sonucu liste geldiyse ilk videoyu al
    if 'entries' in data:
        data = data['entries'][0]
        
    song_url = data['url']
    title = data.get('title', 'Bilinmeyen Şarkı')
    
    # Eğer şu an bir şey çalıyorsa durdur
    if voice_client.is_playing():
        voice_client.stop()
        
    player = discord.FFmpegPCMAudio(song_url, **FFMPEG_OPTIONS)
    voice_client.play(player)
    
    await ctx.send(f"🎶 Şimdi oynatılıyor: **{title}**")

@bot.command(name="stop", help="Şarkıyı durdurur ve kanaldan çıkar")
async def stop(ctx):
    voice_client = ctx.voice_client
    if voice_client and voice_client.is_connected():
        await voice_client.disconnect()
        await ctx.send("👋 Kanaldan ayrıldım.")
    else:
        await ctx.send("❌ Zaten bir ses kanalında değilim.")

# --- 4. BOTU BAŞLATMA ---
if __name__ == "__main__":
    # Web sunucusunu arka planda başlat
    keep_alive()
    
    # Discord Token'ı Çek ve Başlat
    TOKEN = os.environ.get("DISCORD_TOKEN")
    if not TOKEN:
        print("HATA: DISCORD_TOKEN çevre değişkeni bulunamadı!")
    else:
        bot.run(TOKEN)
