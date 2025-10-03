import discord
from discord.ext import commands
import os
from keep_alive import keep_alive  # file keep_alive.py bạn tạo riêng

# Gọi webserver giữ bot sống
keep_alive()

# Lấy token từ biến môi trường trên Render
TOKEN = os.getenv("DISCORD_TOKEN")

# Tạo bot
intents = discord.Intents.default()
intents.message_content = True  # để bot đọc được tin nhắn
bot = commands.Bot(command_prefix="!", intents=intents)

# Khi bot login thành công
@bot.event
async def on_ready():
    print(f"✅ Bot {bot.user} is online and connected to Discord!")

# Command test
@bot.command()
async def ping(ctx):
    await ctx.send("Pong! 🏓")

# Chạy bot
if TOKEN is None:
    print("❌ ERROR: DISCORD_TOKEN not found in environment variables")
else:
    bot.run(TOKEN)
