# bot.py
# Yêu cầu: Python 3.8+, discord.py 2.x
# pip install -U "discord.py" "python-dotenv"

import discord
from discord.ext import commands
import json
import asyncio
import os
import random
import traceback
from datetime import datetime, timedelta
from dotenv import load_dotenv

# Load token từ file .env
load_dotenv()
TOKEN = os.getenv("DISCORD_TOKEN")

INTENTS = discord.Intents.default()
INTENTS.members = True
INTENTS.message_content = True

BOT_PREFIX = "!"
DATA_FILE = "bot_data.json"
OWNER_ID = 123456789012345678  # Thay bằng ID của bạn

bot = commands.Bot(command_prefix=BOT_PREFIX, intents=INTENTS, help_command=commands.DefaultHelpCommand(no_category="Commands"))

# --- Dữ liệu lưu trữ ---
default_data = {
    "xp": {},
    "hourly": {},
    "quiz": {}
}

def load_data():
    if not os.path.exists(DATA_FILE):
        with open(DATA_FILE, "w") as f:
            json.dump(default_data, f)
    with open(DATA_FILE, "r") as f:
        return json.load(f)

def save_data(data):
    with open(DATA_FILE, "w") as f:
        json.dump(data, f, indent=2)

data = load_data()

# --- XP ---
def get_xp(user_id):
    return data["xp"].get(str(user_id), 0)

def add_xp(user_id, amount):
    uid = str(user_id)
    data["xp"][uid] = data["xp"].get(uid, 0) + int(amount)
    save_data(data)

# --- Hourly ---
def can_claim_hourly(user_id, cooldown_hours=1):
    uid = str(user_id)
    last = data["hourly"].get(uid)
    if not last:
        return True, None
    last_dt = datetime.fromisoformat(last)
    diff = datetime.utcnow() - last_dt
    remaining = timedelta(hours=cooldown_hours) - diff
    return remaining <= timedelta(0), remaining if remaining > timedelta(0) else None

def set_hourly_claim(user_id):
    data["hourly"][str(user_id)] = datetime.utcnow().isoformat()
    save_data(data)

# --- Quiz sample ---
QUIZ_QUESTIONS = [
    {"q": "Thủ đô của Pháp là gì?", "a": "paris"},
    {"q": "2+2 bằng mấy?", "a": "4"},
    {"q": "Ngôn ngữ lập trình có logo con rùa là gì?", "a": "logo"},
    {"q": "Môn thể thao sử dụng 'bow' và 'arrow' là gì?", "a": "archery"}
]

# --- Events ---
@bot.event
async def on_ready():
    print(f"✅ Bot is ready. Logged in as {bot.user} (ID: {bot.user.id})")

# --- Commands ---
@bot.command()
async def ping(ctx):
    await ctx.send(f"Pong! {round(bot.latency*1000)}ms")

@bot.command()
async def xp(ctx, member: discord.Member = None):
    member = member or ctx.author
    await ctx.send(f"{member.display_name} có **{get_xp(member.id)} XP**.")

@bot.command(aliases=["hourly", "claim"])
async def hr(ctx):
    user_id = ctx.author.id
    ok, remaining = can_claim_hourly(user_id, cooldown_hours=1)
    if not ok:
        mins = int(remaining.total_seconds() // 60)
        secs = int(remaining.total_seconds() % 60)
        await ctx.send(f"⏳ Hãy đợi {mins} phút {secs} giây nữa.")
        return
    reward = random.randint(10, 50)
    add_xp(user_id, reward)
    set_hourly_claim(user_id)
    await ctx.send(f"{ctx.author.mention} nhận được **{reward} XP** 🎉")

# --- Quiz ---
@bot.group(invoke_without_command=True)
async def quiz(ctx):
    await ctx.send_help(ctx.command)

@quiz.command()
async def start(ctx):
    gid = str(ctx.guild.id)
    if data["quiz"].get(gid, {}).get("active"):
        await ctx.send("🚨 Quiz đã chạy!")
        return
    q = random.choice(QUIZ_QUESTIONS)
    session = {"question": q["q"], "answer": q["a"].lower(), "host": ctx.author.id, "points": {}, "active": True}
    data["quiz"][gid] = session
    save_data(data)
    await ctx.send(f"🎲 Câu hỏi: **{q['q']}**\nTrả lời bằng `!quiz answer <câu>`")

@quiz.command()
async def answer(ctx, *, ans: str):
    gid = str(ctx.guild.id)
    session = data["quiz"].get(gid)
    if not session or not session.get("active"):
        await ctx.send("❌ Không có quiz.")
        return
    if ans.strip().lower() == session["answer"]:
        uid = str(ctx.author.id)
        session["points"][uid] = session["points"].get(uid, 0) + 1
        add_xp(ctx.author.id, 20)
        save_data(data)
        await ctx.send(f"✅ Chính xác {ctx.author.mention}! +1 điểm, +20 XP")
    else:
        await ctx.send("❌ Sai rồi!")

@quiz.command()
async def end(ctx):
    gid = str(ctx.guild.id)
    session = data["quiz"].get(gid)
    if not session or not session.get("active"):
        await ctx.send("❌ Không có quiz.")
        return
    session["active"] = False
    points = session.get("points", {})
    if not points:
        await ctx.send("Quiz kết thúc — không ai ghi điểm.")
    else:
        sorted_pts = sorted(((int(uid), pts) for uid, pts in points.items()), key=lambda x: x[1], reverse=True)
        embed = discord.Embed(title="🏆 Kết quả Quiz", color=discord.Color.green())
        for i, (uid, pts) in enumerate(sorted_pts, start=1):
            member = ctx.guild.get_member(uid)
            name = member.display_name if member else f"User ID {uid}"
            embed.add_field(name=f"#{i} — {name}", value=f"{pts} điểm", inline=False)
        await ctx.send(embed=embed)
    save_data(data)

# --- Owner only ---
def is_owner():
    async def predicate(ctx):
        return ctx.author.id == OWNER_ID
    return commands.check(predicate)

@bot.command()
@is_owner()
async def shutdown(ctx):
    await ctx.send("👋 Tắt bot...")
    await bot.close()

# Run bot
if __name__ == "__main__":
    if not TOKEN:
        print("❌ Chưa có token trong .env (DISCORD_TOKEN)")
    else:
        bot.run(TOKEN)
