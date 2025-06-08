import os
import json
import random
import string
import datetime
from flask import Flask, request
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    ApplicationBuilder, CommandHandler, MessageHandler, CallbackQueryHandler,
    filters
)
from shortener_api import create_short_link

### ---- CONFIG ---- ###
API_TOKEN = "8006836827:AAERFD1tDpBDJhvKm_AHy20uSAzZdoRwbZc"
BOT_USERNAME = "anime_fetch_robot"
ADMIN_IDS = [5759232282]
GROUP_ID = -1002453946876
DAILY_LIMIT = 1
SHORTENER = "linkcents"
### ------------------ ###

USERS_FILE = "users.json"
CODES_FILE = "codes.json"

for f in [USERS_FILE, CODES_FILE]:
    if not os.path.exists(f):
        with open(f, "w") as wr:
            json.dump({}, wr)

def load_json(f):
    return json.load(open(f))

def save_json(f, data):
    open(f, "w").write(json.dumps(data, indent=2))

def get_user(uid):
    users = load_json(USERS_FILE)
    u = users.setdefault(str(uid), {
        "balance": 0.0,
        "referral": None,
        "today_count": 0,
        "last_day": "",
        "history": []
    })
    today = datetime.date.today().isoformat()
    if u["last_day"] != today:
        u.update({"today_count": 0, "last_day": today})
        save_json(USERS_FILE, users)
    return u

def add_balance(uid, amt, reason):
    users = load_json(USERS_FILE)
    u = users[str(uid)]
    u["balance"] += amt
    u["history"].append(f"+₹{amt}: {reason}")
    save_json(USERS_FILE, users)

def gen_code():
    return ''.join(random.choices(string.ascii_uppercase + string.digits, k=6))

async def start(update: Update, context):
    u = get_user(update.effective_user.id)
    kb = [
        [InlineKeyboardButton("🎯 Missions", callback_data="m")],
        [InlineKeyboardButton("👥 Refer", callback_data="r"), InlineKeyboardButton("💰 Balance", callback_data="b")],
        [InlineKeyboardButton("📤 Withdraw", callback_data="w")]
    ]
    await update.message.reply_photo(
        photo="https://telegra.ph/file/050a20dace942a60220c0-6afbc023e43fad29c7.jpg",
        caption="Welcome to *Chitose Earning Bot*! ₹0.01 per mission.",
        parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup(kb)
    )

async def callback_handler(update: Update, context):
    q = update.callback_query
    await q.answer()
    u = get_user(q.from_user.id)

    if q.data == "m":
        if u["today_count"] >= DAILY_LIMIT:
            return await q.message.reply_text("Daily limit reached.")
        code = gen_code()
        link = create_short_link(code)  # returns ad link
        codes = load_json(CODES_FILE)
        codes[code] = {"user": q.from_user.id, "claimed": False}
        save_json(CODES_FILE, codes)
        u["today_count"] += 1
        save_json(USERS_FILE, load_json(USERS_FILE))
        await q.message.reply_text(f"🔗 {link}\nAfter ads, click and get code.\nSend `{code}` here.", parse_mode="Markdown")

    elif q.data == "r":
        await q.message.reply_text(f"Invite link:\n`https://t.me/{BOT_USERNAME}?start={q.from_user.id}`", parse_mode="Markdown")

    elif q.data == "b":
        await q.message.reply_text(f"Balance: ₹{get_user(q.from_user.id)['balance']:.2f}")

    elif q.data == "w":
        await q.message.reply_text("Send <UPI_ID> <Amount> to withdraw.")

async def handle_code(update: Update, context):
    txt = update.message.text.strip().upper()
    codes = load_json(CODES_FILE)
    if txt not in codes:
        return await update.message.reply_text("Invalid code.")
    ent = codes[txt]
    if ent["claimed"]:
        return await update.message.reply_text("Already used.")
    if ent["user"] != update.effective_user.id:
        return await update.message.reply_text("Not your code.")
    ent["claimed"] = True
    save_json(CODES_FILE, codes)
    add_balance(ent["user"], 0.01, "mission")
    u = get_user(ent["user"])
    if u["referral"]:
        add_balance(int(u["referral"]), 0.01, "referral")
        add_balance(int(u["referral"]), 0.001, "ref-watch")
    await update.message.reply_text("✅ Earned ₹0.01")

async def withdraw(update: Update, context):
    parts = update.message.text.split()
    if len(parts) != 2:
        return
    upi, amt = parts; amt = float(amt)
    u = get_user(update.effective_user.id)
    if not (1 <= amt <= 10 and u["balance"] >= amt):
        return await update.message.reply_text("Invalid request.")
    add_balance(update.effective_user.id, -amt, f"withdraw {upi}")
    await update.message.reply_text("✅ Request sent")
    msg = f"Withdraw ₹{amt} from {update.effective_user.id}, UPI:{upi}"
    for aid in ADMIN_IDS:
        await context.bot.send_message(aid, msg)

app = Flask(__name__)
application = ApplicationBuilder().token(API_TOKEN).build()
application.add_handler(CommandHandler("start", start))
application.add_handler(CallbackQueryHandler(callback_handler))
application.add_handler(MessageHandler(filters.Regex(r"^[A-Z0-9]{6}$"), handle_code))
application.add_handler(MessageHandler(filters.Regex(r".+ .+"), withdraw))

@app.route(f"/{API_TOKEN}", methods=["POST"])
def webhook():
    data = request.get_json(force=True)
    update = Update.de_json(data, application.bot)
    application.process_update(update)
    return "OK"

@app.route("/")
def home():
    return "Bot Running"

if __name__ == "__main__":
    port = int(os.getenv("PORT", "8080"))
    app.run("0.0.0.0", port)
