# bot.py
import discord, os, json, random, asyncio, traceback
from discord.ext import commands, tasks
from datetime import datetime, timedelta
from keep_alive import keep_alive
import openai

# ==== CONFIG ====
BOT_PREFIX = "?"
DATA_FILE = "bot_data.json"
OWNER_ID = 123456789012345678  # đổi thành ID owner
TOKEN = os.getenv("DISCORD_TOKEN")
OPENAI_KEY = os.getenv("OPENAI_API_KEY")  # thêm key vào Render
openai.api_key = OPENAI_KEY

INTENTS = discord.Intents.default()
INTENTS.members = True
INTENTS.message_content = True
bot = commands.Bot(command_prefix=BOT_PREFIX, intents=INTENTS)

# ==== DATA ====
default_data = {"coins":{}, "hourly":{}, "quiz":{}, "bets":{}, "stocks":{}}

def load():
    if not os.path.exists(DATA_FILE):
        with open(DATA_FILE,"w") as f: json.dump(default_data,f)
    return json.load(open(DATA_FILE,"r"))

def save(d): open(DATA_FILE,"w").write(json.dumps(d,indent=2))
data = load()

# ==== HELPERS ====
def bal(uid): return data["coins"].get(str(uid),0)
def add(uid,amt): data["coins"][str(uid)]=bal(uid)+amt; save(data)
def can_hr(uid,h=1):
    u=str(uid); last=data["hourly"].get(u)
    if not last: return True,None
    diff=datetime.utcnow()-datetime.fromisoformat(last)
    remain=timedelta(hours=h)-diff
    return remain<=timedelta(0),remain if remain>timedelta(0) else None
def set_hr(uid): data["hourly"][str(uid)]=datetime.utcnow().isoformat(); save(data)

# ==== KEEP ALIVE ====
keep_alive()

# ==== EVENTS ====
@bot.event
async def on_ready():
    print(f"✅ Bot {bot.user} online")
    stock_update.start()

# ==== BASIC ====
@bot.command()
async def ping(ctx): await ctx.send(f"Pong {round(bot.latency*1000)}ms")

@bot.command()
async def bal(ctx,m:discord.Member=None):
    m=m or ctx.author
    await ctx.send(f"{m.display_name} có {bal(m.id)} 💰 Skibidi Coin")

@bot.command()
async def lb(ctx,top:int=10):
    arr=[(int(u),c) for u,c in data["coins"].items()]
    arr.sort(key=lambda x:x[1],reverse=True)
    if not arr: return await ctx.send("Chưa có ai có coin")
    emb=discord.Embed(title="🏆 Leaderboard",color=discord.Color.gold())
    for i,(uid,c) in enumerate(arr[:top],1):
        mem=ctx.guild.get_member(uid)
        emb.add_field(name=f"#{i} {mem.display_name if mem else uid}",value=f"{c} 💰",inline=False)
    await ctx.send(embed=emb)

@bot.command()
async def hr(ctx):
    ok,remain=can_hr(ctx.author.id)
    if not ok: return await ctx.send(f"Đợi {int(remain.total_seconds()//60)}m nữa")
    reward=random.randint(10,50); add(ctx.author.id,reward); set_hr(ctx.author.id)
    await ctx.send(f"{ctx.author.mention} nhận {reward} 💰")

# ==== QUIZ ====
QUIZ=[{"q":"2+2?","a":"4"},{"q":"Thủ đô Nhật Bản?","a":"tokyo"}]

@bot.group(invoke_without_command=True)
async def quiz(ctx): await ctx.send("Dùng ?quiz start / answer / end")

@quiz.command()
async def start(ctx):
    g=str(ctx.guild.id)
    if data["quiz"].get(g,{}).get("active"): return await ctx.send("Đang có quiz")
    q=random.choice(QUIZ); data["quiz"][g]={"q":q["q"],"a":q["a"],"active":True,"pts":{}}
    save(data); await ctx.send(f"🎲 Quiz: {q['q']}")

@quiz.command()
async def answer(ctx,*,ans):
    g=str(ctx.guild.id); s=data["quiz"].get(g)
    if not s or not s["active"]: return await ctx.send("Không có quiz")
    if ans.lower()==s["a"]:
        s["pts"][str(ctx.author.id)]=s["pts"].get(str(ctx.author.id),0)+1
        add(ctx.author.id,20); save(data)
        await ctx.send(f"{ctx.author.mention} đúng! +20 💰")
    else: await ctx.send("Sai rồi!")

@quiz.command()
async def end(ctx):
    g=str(ctx.guild.id); s=data["quiz"].get(g)
    if not s or not s["active"]: return
    s["active"]=False; pts=s["pts"]; save(data)
    if not pts: return await ctx.send("Kết thúc, không ai ghi điểm")
    emb=discord.Embed(title="Kết quả Quiz")
    for i,(uid,p) in enumerate(sorted(pts.items(), key=lambda x:x[1],reverse=True),1):
        m=ctx.guild.get_member(int(uid))
        emb.add_field(name=f"#{i} {m.display_name if m else uid}",value=f"{p} điểm")
    await ctx.send(embed=emb)

# ==== HORSE RACE ====
HORSES=["🐎","🏇","🐴","🦄"]

@bot.command()
async def race(ctx):
    g=str(ctx.guild.id)
    if g in data["bets"]: return await ctx.send("Đang có race")
    msg=await ctx.send("🐎 Đua ngựa! cược bằng ?bet <số> <coin>")
    data["bets"][g]={"bets":{},"msg":msg.id}; save(data)
    await asyncio.sleep(30)
    if not data["bets"][g]["bets"]: 
        await msg.delete(); data["bets"].pop(g); save(data)

@bot.command()
async def bet(ctx,horse:int,amt:int):
    g=str(ctx.guild.id); s=data["bets"].get(g)
    if not s: return
    if bal(ctx.author.id)<amt: return await ctx.send("Không đủ coin")
    add(ctx.author.id,-amt); s["bets"][str(ctx.author.id)]={"h":horse,"a":amt}
    save(data); await ctx.send(f"{ctx.author.display_name} cược {amt} vào {HORSES[horse-1]}")

@bot.command()
async def startrace(ctx):
    g=str(ctx.guild.id); s=data["bets"].get(g)
    if not s: return
    win=random.randint(1,len(HORSES)); txt=f"🏁 Thắng: {HORSES[win-1]}\n"
    winners=[]
    for uid,bet in s["bets"].items():
        if bet["h"]==win: reward=bet["a"]*2; add(int(uid),reward); winners.append((uid,reward))
    txt+="\n".join([f"<@{u}> +{r}" for u,r in winners]) if winners else "Không ai thắng"
    await ctx.send(txt); data["bets"].pop(g); save(data)

# ==== COINFLIP ====
@bot.command()
async def coinflip(ctx,amt:int,side:str):
    if bal(ctx.author.id)<amt: return await ctx.send("Không đủ coin")
    if side.lower() not in ["heads","tails"]: return await ctx.send("Chọn heads/tails")
    res=random.choice(["heads","tails"])
    if res==side.lower(): add(ctx.author.id,amt); await ctx.send(f"Kết quả {res}, bạn thắng {amt} 💰")
    else: add(ctx.author.id,-amt); await ctx.send(f"Kết quả {res}, bạn thua {amt} 💰")

# ==== STOCKS ====
STOCKS=["APPL","MSFT","BTC","ETH"]

@tasks.loop(minutes=5)
async def stock_update():
    for s in STOCKS:
        price=random.randint(50,500)
        data["stocks"][s]=price
    save(data)

@bot.group(invoke_without_command=True)
async def stock(ctx): await ctx.send("Dùng ?stock prices / buy / sell")

@stock.command()
async def prices(ctx):
    txt="\n".join([f"{s}: {p}💰" for s,p in data["stocks"].items()])
    await ctx.send(f"📈 Giá cổ phiếu:\n{txt}")

@stock.command()
async def buy(ctx,sym:str,amt:int):
    if sym not in STOCKS: return
    price=data["stocks"].get(sym,100); cost=price*amt
    if bal(ctx.author.id)<cost: return await ctx.send("Không đủ coin")
    add(ctx.author.id,-cost)
    port=data.setdefault("portfolio",{}).setdefault(str(ctx.author.id),{})
    port[sym]=port.get(sym,0)+amt; save(data)
    await ctx.send(f"Mua {amt} {sym} giá {cost}💰")

@stock.command()
async def sell(ctx,sym:str,amt:int):
    port=data.setdefault("portfolio",{}).setdefault(str(ctx.author.id),{})
    if port.get(sym,0)<amt: return await ctx.send("Không đủ cổ phiếu")
    price=data["stocks"].get(sym,100); gain=price*amt
    port[sym]-=amt; add(ctx.author.id,gain); save(data)
    await ctx.send(f"Bán {amt} {sym}, nhận {gain}💰")

# ==== CHATGPT ====
@bot.command()
async def ask(ctx,*,q):
    if not OPENAI_KEY: return await ctx.send("Chưa config API key")
    try:
        resp=openai.ChatCompletion.create(
            model="gpt-3.5-turbo",
            messages=[{"role":"user","content":q}]
        )
        await ctx.send(resp["choices"][0]["message"]["content"][:1900])
    except Exception as e:
        await ctx.send(f"Lỗi API: {e}")

# ==== ADMIN ====
@bot.command()
@commands.has_permissions(administrator=True)
async def editbal(ctx,m:discord.Member,amt:int):
    data["coins"][str(m.id)]=amt; save(data)
    await ctx.send(f"{m.display_name} = {amt} 💰")

@bot.command()
@commands.has_permissions(administrator=True)
async def adcmd(ctx):
    await ctx.send("Admin cmds: ?editbal | ?clear | ?kick | ?ban")

# ==== OWNER ====
def is_owner():
    async def pred(ctx): return ctx.author.id==OWNER_ID
    return commands.check(pred)

@bot.command()
@is_owner()
async def shutdown(ctx): await ctx.send("Tắt bot"); await bot.close()

@bot.command()
@is_owner()
async def owncmd(ctx): await ctx.send("Owner cmds: ?shutdown | ?eval")

# ==== RUN ====
if TOKEN: bot.run(TOKEN)
else: print("❌ Thiếu DISCORD_TOKEN")
