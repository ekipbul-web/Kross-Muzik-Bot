import os
import asyncio
from flask import Flask
from threading import Thread
import discord
from discord.ext import commands
import yt_dlp
import ffdl  # Render sunucusuna FFmpeg'i otomatik indiren kütüphane

# --- 0. RENDER İÇİN FFMPEG OTOMATİK KURULUMU ---
try:
    print("🔄 Sunucuda FFmpeg kontrol ediliyor / kuruluyor...")
    ffdl.ffdl()
    print("✅ FFmpeg başarıyla hazırlandı!")
except Exception as e:
    print(f"⚠️ FFmpeg kurulum uyarısı: {e}")

# --- 1. RENDER İÇİN WEB SUNUCU AYARI (Port Hatasını Önler) ---
app = Flask('')

@app.route('/')
def home():
    return "Bot Aktif!"

def run_web_server():
    # Render'ın dinamik portunu yakalar, yoksa varsayılan 8080'i kullanır
    port = int(os.environ.get("PORT", 8080))
    app.run(host='0.0.0.0', port=port)

def keep_alive():
    t = Thread(target=run_web_server)
    t.daemon = True
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
    'source_address': '0.0.0.0',
    # YouTube engellerini aşmak için eklenen kararlılık ayarları
    'nocheckcertificate': True,
    'ignoreerrors': False,
    'logtostderr': False,
    'extract_flat': False,
}

FFMPEG_OPTIONS = {
    # Şarkıların yarıda kesilmesini önlemek için bağlantı koptuğunda otomatik yeniden bağlanma ayarları
    'before_options': '-reconnect 1 -reconnect_streamed 1 -reconnect_delay_max 5',
    # -vn: Videoyu yok sayarak sadece sesi çeker, sunucu RAM'ini tüketmez ve botu hızlandırır
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

    # Arama işleme ve YouTube'dan veri çekme adımı
    loop = asyncio.get_event_loop()
    try:
        data = await loop.run_in_executor(None, lambda: ytdl.extract_info(search, download=False))
    except Exception as e:
        return await ctx.send(f"❌ Şarkı bulunamadı veya yüklenemedi: {e}")

    # yt-dlp arama sonuçlarının formatını doğrular
    if 'entries' in data:
        if len(data['entries']) > 0:
            main_data = data['entries'][0]
        else:
            return await ctx.send("❌ Hiçbir sonuç bulunamadı.")
    else:
        main_data = data
        
    song_url = main_data['url']
    title = main_data.get('title', 'Bilinmeyen Şarkı')
    
    # Eğer o esnada zaten bir şarkı çalıyorsa onu kapatır
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
    # Flask web sunucusunu arka planda ayağa kaldırır (Render 10 dakika sınırı ve Port hatası için)
    keep_alive()
    
    # Render Environment Variables (Ortam Değişkenleri) üzerinden Discord tokenini çeker
    TOKEN = os.environ.get("DISCORD_TOKEN")
    if not TOKEN:
        print("HATA: DISCORD_TOKEN çevre değişkeni bulunamadı! Lütfen Render panelinden Environment sekmesine ekleyin.")
    else:
        bot.run(TOKEN)
