import os
import discord
from discord.ext import commands
from dotenv import load_dotenv

# Load biến môi trường từ .env
load_dotenv()
TOKEN = os.getenv("DISCORD_TOKEN")

# Tạo bot
intents = discord.Intents.default()
intents.message_content = True  # Cho phép đọc tin nhắn
bot = commands.Bot(command_prefix="!", intents=intents)

# Sự kiện bot online
@bot.event
async def on_ready():
    print(f"✅ Bot đã đăng nhập thành công dưới tên {bot.user}")

# Lệnh test
@bot.command()
async def ping(ctx):
    await ctx.send("Pong!")

# ----------------------
# Flask keep-alive server
# ----------------------
from flask import Flask
import threading

app = Flask('')

@app.route('/')
def home():
    return "Bot is alive!"

def run():
    app.run(host='0.0.0.0', port=8080)

def keep_alive():
    t = threading.Thread(target=run)
    t.start()

# ----------------------
# Chạy bot
# ----------------------
if __name__ == "__main__":
    keep_alive()        # giữ cho bot luôn sống (Render không sleep)
    bot.run(TOKEN)
