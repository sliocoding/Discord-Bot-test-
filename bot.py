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
    # bot.py
# Requires: Python 3.8+, discord.py 2.x, python-dotenv, flask (for keep-alive)
# pip install -U "discord.py" python-dotenv flask

import os
import discord
from discord.ext import commands
import json
import asyncio
from datetime import datetime, timedelta
import random
import traceback
from dotenv import load_dotenv

# ---------------------------
# Keep-alive (simple Flask)
# ---------------------------
# If you already have a keep_alive.py or use another approach, you can remove this.
try:
    from flask import Flask
    from threading import Thread

    app = Flask("")

    @app.route("/")
    def home():
        return "Bot is alive!"

    @app.route("/health")
    def health():
        return "OK", 200

    def _run_flask():
        app.run(host="0.0.0.0", port=8080)

    def keep_alive():
        t = Thread(target=_run_flask)
        t.daemon = True
        t.start()
except Exception:
    def keep_alive():
        return
# ---------------------------

load_dotenv()
TOKEN = os.getenv("DISCORD_TOKEN")
OWNER_ID = int(os.getenv("OWNER_ID", "0"))

INTENTS = discord.Intents.default()
INTENTS.members = True
INTENTS.message_content = True

BOT_PREFIX = "!"
DATA_FILE = "bot_data.json"

bot = commands.Bot(command_prefix=BOT_PREFIX, intents=INTENTS,
                   help_command=commands.DefaultHelpCommand(no_category="Commands"))

# ---------------------------
# Data storage (thread-safe save)
# ---------------------------
default_data = {
    "xp": {},         # user_id -> xp (int)
    "eco": {},        # user_id -> { "bal": int, "daily": iso, "hourly": iso, "inv": {item:qty} }
    "quiz": {},       # guild_id -> quiz session
}

# ensure file exists
if not os.path.exists(DATA_FILE):
    with open(DATA_FILE, "w") as f:
        json.dump(default_data, f, indent=2)

# load once at start
with open(DATA_FILE, "r") as f:
    data = json.load(f)

# async-safe save
def _save_sync():
    with open(DATA_FILE, "w") as f:
        json.dump(data, f, indent=2)

async def save_data_async():
    loop = asyncio.get_running_loop()
    await loop.run_in_executor(None, _save_sync)

# ---------------------------
# Helper - economy & xp
# ---------------------------
def _ensure_user_eco(uid: str):
    if uid not in data["eco"]:
        data["eco"][uid] = {"bal": 0, "daily": None, "hourly": None, "inv": {}}

def get_balance(user_id):
    uid = str(user_id)
    _ensure_user_eco(uid)
    return int(data["eco"][uid].get("bal", 0))

async def add_balance(user_id, amount):
    uid = str(user_id)
    _ensure_user_eco(uid)
    data["eco"][uid]["bal"] = int(data["eco"][uid].get("bal", 0)) + int(amount)
    await save_data_async()

def get_xp(user_id):
    return int(data["xp"].get(str(user_id), 0))

async def add_xp_async(user_id, amount):
    uid = str(user_id)
    data["xp"][uid] = int(data["xp"].get(uid, 0)) + int(amount)
    await save_data_async()

# Level system
def get_level(xp: int) -> int:
    return xp // 100

def xp_for_next_level(level: int) -> int:
    return (level + 1) * 100

async def add_xp_and_check_level(user, amount, channel=None):
    uid = user.id
    old_xp = get_xp(uid)
    old_level = get_level(old_xp)
    await add_xp_async(uid, amount)
    new_xp = get_xp(uid)
    new_level = get_level(new_xp)
    if new_level > old_level and channel:
        try:
            await channel.send(f"🎉 {user.mention} đã lên **Level {new_level}**! (XP: {new_xp})")
        except Exception:
            pass
    return new_xp, new_level

# cooldown util
def _get_iso(dt: datetime):
    return dt.isoformat()

def _from_iso(s):
    return datetime.fromisoformat(s) if s else None

# ---------------------------
# Shop items (example)
# ---------------------------
SHOP = {
    "apple": {"price": 20, "desc": "Một quả táo (+0)"},
    "sword": {"price": 500, "desc": "Kiếm gỗ để khoe với bạn bè"},
    "fishing_rod": {"price": 200, "desc": "Cần câu giúp bạn fish tốt hơn"},
}

# ---------------------------
# Mini-games helpers
# ---------------------------
FISH_TABLE = [
    ("Old Boot", 0),
    ("Small Fish", 10),
    ("Big Fish", 30),
    ("Golden Fish", 100),
]

# ---------------------------
# Events
# ---------------------------
@bot.event
async def on_ready():
    print(f"Bot is ready. Logged in as {bot.user} (ID: {bot.user.id})")
    keep_alive()  # start keep-alive server (no-op if Flask missing)
    print("Keep-alive started (if available).")
    print("------")

# simple chat XP (cooldown 60s)
chat_cooldowns = {}  # user_id -> datetime
@bot.event
async def on_message(message):
    if message.author.bot:
        return

    uid = message.author.id
    now = datetime.utcnow()
    last = chat_cooldowns.get(uid)
    if not last or (now - last).total_seconds() >= 60:
        xp_gain = random.randint(5, 15)
        await add_xp_and_check_level(message.author, xp_gain, message.channel)
        chat_cooldowns[uid] = now

    await bot.process_commands(message)

# ---------------------------
# Basic commands & economy
# ---------------------------
@bot.command(name="ping")
async def ping_cmd(ctx):
    latency = round(bot.latency * 1000)
    await ctx.send(f"Pong! 🏓 Độ trễ: {latency}ms")

@bot.command(name="bal", aliases=["balance"])
async def bal_cmd(ctx, member: discord.Member = None):
    member = member or ctx.author
    bal = get_balance(member.id)
    await ctx.send(f"{member.display_name} có **{bal} 💰**.")

# hourly (1 hour)
@bot.command(name="hr", aliases=["hourly", "claim"])
async def hourly_cmd(ctx):
    uid = str(ctx.author.id)
    _ensure_user_eco(uid)
    last = _from_iso(data["eco"][uid].get("hourly"))
    now = datetime.utcnow()
    if last and (now - last) < timedelta(hours=1):
        rem = timedelta(hours=1) - (now - last)
        mins = int(rem.total_seconds() // 60)
        secs = int(rem.total_seconds() % 60)
        await ctx.send(f"Đã claim rồi. Hãy chờ {mins} phút {secs} giây.")
        return
    reward = random.randint(10, 50)
    await add_balance(ctx.author.id, reward)
    data["eco"][uid]["hourly"] = _get_iso(now)
    await save_data_async()
    await add_xp_and_check_level(ctx.author, random.randint(5, 15), ctx.channel)
    await ctx.send(f"{ctx.author.mention} nhận **{reward} 💰** từ hourly!")

# daily (24h)
@bot.command(name="daily")
async def daily_cmd(ctx):
    uid = str(ctx.author.id)
    _ensure_user_eco(uid)
    last = _from_iso(data["eco"][uid].get("daily"))
    now = datetime.utcnow()
    if last and (now - last) < timedelta(hours=24):
        rem = timedelta(hours=24) - (now - last)
        hrs = int(rem.total_seconds() // 3600)
        mins = int((rem.total_seconds() % 3600) // 60)
        await ctx.send(f"Đã nhận daily rồi. Hãy chờ {hrs} giờ {mins} phút.")
        return
    reward = random.randint(100, 500)
    await add_balance(ctx.author.id, reward)
    data["eco"][uid]["daily"] = _get_iso(now)
    await save_data_async()
    await add_xp_and_check_level(ctx.author, random.randint(10, 30), ctx.channel)
    await ctx.send(f"{ctx.author.mention} nhận **{reward} 💰** từ daily!")

# work (cooldown 30m)
work_cooldowns = {}
@bot.command(name="work")
async def work_cmd(ctx):
    uid = str(ctx.author.id)
    now = datetime.utcnow()
    last = work_cooldowns.get(uid)
    if last and (now - last).total_seconds() < 30*60:
        rem = 30*60 - (now - last).total_seconds()
        mins = int(rem // 60); secs = int(rem % 60)
        await ctx.send(f"Hãy đợi {mins} phút {secs} giây để work tiếp.")
        return
    reward = random.randint(50, 150)
    await add_balance(ctx.author.id, reward)
    work_cooldowns[uid] = now
    await add_xp_and_check_level(ctx.author, random.randint(5, 20), ctx.channel)
    await ctx.send(f"{ctx.author.mention} đi làm và nhận **{reward} 💰**!")

# crime (risky)
@bot.command(name="crime")
async def crime_cmd(ctx):
    uid = str(ctx.author.id)
    success = random.random() < 0.45  # 45% success
    if success:
        reward = random.randint(80, 300)
        await add_balance(ctx.author.id, reward)
        await add_xp_and_check_level(ctx.author, random.randint(10, 30), ctx.channel)
        await ctx.send(f"🕶️ {ctx.author.mention} thực hiện thành công và lấy **{reward} 💰**.")
    else:
        loss = random.randint(30, 150)
        bal = get_balance(ctx.author.id)
        new_loss = min(bal, loss)
        await add_balance(ctx.author.id, -new_loss)
        await ctx.send(f"❌ {ctx.author.mention} bị bắt! Mất **{new_loss} 💰**.")

# ---------------------------
# Shop & inventory
# ---------------------------
@bot.command(name="shop")
async def shop_cmd(ctx):
    lines = ["🛒 **Shop**"]
    for key, v in SHOP.items():
        lines.append(f"`{key}` — {v['price']}💰 — {v['desc']}")
    await ctx.send("\n".join(lines))

@bot.command(name="buy")
async def buy_cmd(ctx, item: str, qty: int = 1):
    item = item.lower()
    if item not in SHOP:
        await ctx.send("Không tồn tại item này trong shop.")
        return
    if qty < 1:
        await ctx.send("Số lượng phải lớn hơn 0.")
        return
    price = SHOP[item]["price"] * qty
    bal = get_balance(ctx.author.id)
    if bal < price:
        await ctx.send("Bạn không đủ tiền.")
        return
    await add_balance(ctx.author.id, -price)
    uid = str(ctx.author.id)
    _ensure_user_eco(uid)
    inv = data["eco"][uid].get("inv", {})
    inv[item] = inv.get(item, 0) + qty
    data["eco"][uid]["inv"] = inv
    await save_data_async()
    await ctx.send(f"🛍️ Mua thành công {qty} x {item} (đã trừ {price}💰).")

@bot.command(name="inv", aliases=["inventory"])
async def inv_cmd(ctx, member: discord.Member = None):
    member = member or ctx.author
    uid = str(member.id)
    _ensure_user_eco(uid)
    inv = data["eco"][uid].get("inv", {})
    if not inv:
        await ctx.send(f"{member.display_name} không có item nào.")
        return
    lines = [f"📦 **{member.display_name} Inventory**"]
    for k, v in inv.items():
        lines.append(f"{k}: {v}")
    await ctx.send("\n".join(lines))

# ---------------------------
# Mini-games
# ---------------------------
@bot.command(name="fish")
async def fish_cmd(ctx):
    uid = str(ctx.author.id)
    _ensure_user_eco(uid)
    # chance influenced by fishing_rod
    inv = data["eco"][uid].get("inv", {})
    rod = inv.get("fishing_rod", 0)
    roll = random.random()
    if rod > 0:
        # better odds
        choices = [("Old Boot", 0), ("Small Fish", 20), ("Big Fish", 60), ("Golden Fish", 200)]
    else:
        choices = FISH_TABLE
    item, value = random.choices(choices, weights=[50, 30, 15, 5], k=1)[0]
    if value > 0:
        await add_balance(ctx.author.id, value)
        await add_xp_and_check_level(ctx.author, random.randint(5, 15), ctx.channel)
        await ctx.send(f"🎣 {ctx.author.mention} đã câu được **{item}** và bán được **{value}💰**.")
    else:
        await ctx.send(f"🎣 {ctx.author.mention} câu được **{item}**. Chúc lần sau may mắn!")

@bot.command(name="guess")
async def guess_cmd(ctx, number: int):
    if number < 1 or number > 10:
        await ctx.send("Hãy đoán số trong khoảng 1-10.")
        return
    answer = random.randint(1, 10)
    if number == answer:
        reward = random.randint(15, 40)
        await add_balance(ctx.author.id, reward)
        await add_xp_and_check_level(ctx.author, random.randint(5, 15), ctx.channel)
        await ctx.send(f"🎉 Chính xác {ctx.author.mention}! Số là **{answer}**. Bạn nhận **{reward}💰**.")
    else:
        await ctx.send(f"😢 Sai rồi {ctx.author.mention}. Số đúng: **{answer}**.")

@bot.command(name="coinflip")
async def coinflip_cmd(ctx, choice: str):
    choice = choice.lower()
    if choice not in ("head", "tail", "h", "t"):
        await ctx.send("Dùng `!coinflip head` hoặc `!coinflip tail`.")
        return
    pick = "head" if choice.startswith("h") else "tail"
    result = random.choice(["head", "tail"])
    if pick == result:
        reward = 50
        await add_balance(ctx.author.id, reward)
        await add_xp_and_check_level(ctx.author, random.randint(5, 15), ctx.channel)
        await ctx.send(f"🎯 {ctx.author.mention} thắng! Kết quả: **{result}**. +{reward}💰")
    else:
        loss = 25
        await add_balance(ctx.author.id, -loss)
        await ctx.send(f"😵 {ctx.author.mention} thua! Kết quả: **{result}**. -{loss}💰")

@bot.command(name="slots")
async def slots_cmd(ctx):
    emojis = ["🍒", "🍋", "🔔", "⭐", "7️⃣"]
    res = [random.choice(emojis) for _ in range(3)]
    await ctx.send(" | ".join(res))
    if res[0] == res[1] == res[2]:
        reward = 150
        await add_balance(ctx.author.id, reward)
        await add_xp_and_check_level(ctx.author, random.randint(10, 30), ctx.channel)
        await ctx.send(f"🎉 JACKPOT! Bạn được +{reward}💰")
    else:
        loss = 30
        await add_balance(ctx.author.id, -loss)
        await ctx.send(f"😕 Không trúng. Mất {loss}💰")

# ---------------------------
# Leaderboard
# ---------------------------
@bot.command(name="lb", aliases=["leaderboard"])
async def leaderboard(ctx, top: int = 10):
    eco = data.get("eco", {})
    items = []
    for uid, info in eco.items():
        bal = int(info.get("bal", 0))
        items.append((int(uid), bal))
    if not items:
        await ctx.send("Không có dữ liệu.")
        return
    items.sort(key=lambda x: x[1], reverse=True)
    embed = discord.Embed(title="🏆 Leaderboard (by balance)", color=discord.Color.gold())
    for i, (uid, bal) in enumerate(items[:top], start=1):
        member = ctx.guild.get_member(uid)
        name = member.display_name if member else f"User ID {uid}"
        embed.add_field(name=f"#{i} — {name}", value=f"{bal} 💰", inline=False)
    await ctx.send(embed=embed)

# ---------------------------
# Quiz system (kept from original)
# ---------------------------
QUIZ_QUESTIONS = [
    {"q": "Thủ đô của Pháp là gì?", "a": "paris"},
    {"q": "2+2 bằng mấy?", "a": "4"},
    {"q": "Ngôn ngữ lập trình có logo con rùa là gì?", "a": "logo"},
]

@bot.group(name="quizgroup", invoke_without_command=True)
async def quizroot(ctx):
    await ctx.send_help(ctx.command)

@quizroot.command(name="start")
@commands.cooldown(1, 10, commands.BucketType.guild)
async def quizroot_start(ctx):
    gid = str(ctx.guild.id)
    if data["quiz"].get(gid, {}).get("active"):
        await ctx.send("Đã có quiz đang chạy trên server này.")
        return
    q = random.choice(QUIZ_QUESTIONS)
    session = {
        "question": q["q"],
        "answer": q["a"].lower(),
        "host": ctx.author.id,
        "points": {},
        "active": True
    }
    data["quiz"][gid] = session
    await save_data_async()
    await ctx.send(f"🎲 **Quiz started!**\nCâu hỏi: **{q['q']}**\nTrả lời bằng lệnh `!quizgroup answer <câu trả lời>`")

@quizroot.command(name="answer")
async def quizroot_answer(ctx, *, ans: str):
    gid = str(ctx.guild.id)
    session = data["quiz"].get(gid)
    if not session or not session.get("active"):
        await ctx.send("Không có quiz đang hoạt động.")
        return
    if ans.strip().lower() == session["answer"]:
        uid = str(ctx.author.id)
        session["points"][uid] = session["points"].get(uid, 0) + 1
        await add_xp_and_check_level(ctx.author, 20, ctx.channel)
        await save_data_async()
        await ctx.send(f"✅ Chính xác {ctx.author.mention}! +1 điểm và +20 XP")
    else:
        await ctx.send("Sai rồi — thử lại!")

@quizroot.command(name="end")
async def quizroot_end(ctx):
    gid = str(ctx.guild.id)
    session = data["quiz"].get(gid)
    if not session or not session.get("active"):
        await ctx.send("Không có quiz đang hoạt động.")
        return
    if ctx.author.id != session.get("host") and not ctx.author.guild_permissions.manage_guild:
        await ctx.send("Chỉ host quiz hoặc người quản lý server mới có thể kết thúc quiz.")
        return
    session["active"] = False
    points = session.get("points", {})
    if not points:
        await ctx.send("Quiz kết thúc — không ai ghi điểm.")
    else:
        sorted_pts = sorted(((int(uid), pts) for uid, pts in points.items()), key=lambda x: x[1], reverse=True)
        embed = discord.Embed(title="Quiz Results", color=discord.Color.green())
        for i, (uid, pts) in enumerate(sorted_pts, start=1):
            member = ctx.guild.get_member(uid)
            name = member.display_name if member else f"User ID {uid}"
            embed.add_field(name=f"#{i} — {name}", value=f"{pts} điểm", inline=False)
        await ctx.send(embed=embed)
    data["quiz"][gid] = session
    await save_data_async()

# ---------------------------
# Owner commands (shutdown/eval)
# ---------------------------
def is_owner():
    async def predicate(ctx):
        return ctx.author.id == OWNER_ID
    return commands.check(predicate)

@bot.command(name="shutdown")
@is_owner()
async def shutdown(ctx):
    await ctx.send("Shutting down...")
    await bot.close()

@bot.command(name="eval")
@is_owner()
async def _eval(ctx, *, body: str):
    env = {
        'bot': bot,
        'ctx': ctx,
        'discord': discord,
        'asyncio': asyncio,
        '__import__': __import__
    }
    try:
        code = compile(body, "<eval>", "exec")
        exec(code, env)
        await ctx.send("Eval executed.")
    except Exception as e:
        tb = traceback.format_exc()
        await ctx.send(f"Error:\n```\n{tb}\n```")

# ---------------------------
# Error handlers
# ---------------------------
@bot.event
async def on_command_error(ctx, error):
    if isinstance(error, commands.MissingRequiredArgument):
        await ctx.send("Thiếu tham số cần thiết.")
    elif isinstance(error, commands.CommandOnCooldown):
        await ctx.send(f"Hãy đợi {error.retry_after:.1f}s.")
    else:
        # generic
        await ctx.send(f"Lỗi: {error}")

# ---------------------------
# Run bot (no token hardcoded)
# ---------------------------
if __name__ == "__main__":
    if not TOKEN:
        print("ERROR: DISCORD_TOKEN not set. Put DISCORD_TOKEN in your .env or environment variables.")
    else:
        bot.run(TOKEN)
active_races = {}  # guild_id -> {"horses": [...], "bets": {}, "message_id": int}

HORSES = [
    {"name": "🐴 Ngựa Lửa", "speed": 8, "stamina": 6},
    {"name": "🦄 Unicorn Skibidi", "speed": 7, "stamina": 9},
    {"name": "🐎 Ngựa Chiến", "speed": 6, "stamina": 8},
    {"name": "🦬 Skibidi Trâu", "speed": 5, "stamina": 10}
]

@bot.command(name="race")
async def race(ctx):
    gid = str(ctx.guild.id)
    if gid in active_races:
        await ctx.send("Hiện đang có cuộc đua diễn ra, hãy tham gia!")
        return

    horses = random.sample(HORSES, 3)
    desc = "\n".join([f"{i+1}. {h['name']} (Speed: {h['speed']}, Stamina: {h['stamina']})"
                      for i, h in enumerate(horses)])
    embed = discord.Embed(
        title="🏇 Cuộc đua Skibidi bắt đầu!",
        description=desc,
        color=discord.Color.blue()
    )
    embed.set_footer(text="Dùng lệnh ?bet <số> <coin> để đặt cược (30s).")

    msg = await ctx.send(embed=embed)
    active_races[gid] = {"horses": horses, "bets": {}, "message_id": msg.id}

    # sau 30s nếu không ai bet thì hủy
    await asyncio.sleep(30)
    if gid in active_races and not active_races[gid]["bets"]:
        try:
            m = await ctx.channel.fetch_message(msg.id)
            await m.delete()
        except:
            pass
        del active_races[gid]
        await ctx.send("⏰ Hết giờ, không ai đặt cược. Cuộc đua bị hủy.")

@bot.command(name="bet")
async def bet(ctx, horse_index: int, amount: int):
    gid = str(ctx.guild.id)
    if gid not in active_races:
        await ctx.send("Không có cuộc đua nào đang diễn ra.")
        return

    horses = active_races[gid]["horses"]
    if horse_index < 1 or horse_index > len(horses):
        await ctx.send("Số ngựa không hợp lệ.")
        return

    balance = get_balance(ctx.author.id)
    if amount <= 0 or amount > balance:
        await ctx.send("Bạn không đủ Skibidi Coin để đặt cược.")
        return

    add_balance(ctx.author.id, -amount)  # trừ coin
    active_races[gid]["bets"][ctx.author.id] = {"horse": horse_index-1, "amount": amount}
    await ctx.send(f"{ctx.author.display_name} đã cược {amount} 💰 Skibidi Coin cho {horses[horse_index-1]['name']}!")

@bot.command(name="startrace")
async def startrace(ctx):
    gid = str(ctx.guild.id)
    if gid not in active_races:
        await ctx.send("Không có cuộc đua nào để bắt đầu.")
        return

    horses = active_races[gid]["horses"]
    bets = active_races[gid]["bets"]

    if not bets:
        await ctx.send("Không ai đặt cược, hủy race.")
        del active_races[gid]
        return

    await ctx.send("🚦 Cuộc đua bắt đầu sau 3s...")
    await asyncio.sleep(3)

    # Random winner
    scores = [h["speed"] + random.randint(0, h["stamina"]) for h in horses]
    winner_index = scores.index(max(scores))
    winner = horses[winner_index]

    msg = f"🏁 Kết thúc! {winner['name']} đã chiến thắng!\n"
    winners = []
    for uid, bet in bets.items():
        if bet["horse"] == winner_index:
            payout = bet["amount"] * 2
            add_balance(uid, payout)
            winners.append((uid, payout))

    if winners:
        for uid, payout in winners:
            member = ctx.guild.get_member(uid)
            msg += f"{member.display_name} thắng {payout} 💰 Skibidi Coin!\n"
    else:
        msg += "Không ai thắng cược..."

    await ctx.send(msg)
    del active_races[gid]
def get_balance(user_id):
    return data["coins"].get(str(user_id), 0)

def add_balance(user_id, amount):
    uid = str(user_id)
    data["coins"][uid] = data["coins"].get(uid, 0) + int(amount)
    save_data(data)
