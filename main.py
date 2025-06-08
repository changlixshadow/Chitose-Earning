import os
import json
import random
import string
import datetime
from flask import Flask, request
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, InputMediaPhoto
from telegram.ext import (
    ApplicationBuilder, CommandHandler, MessageHandler, CallbackQueryHandler,
    filters, ContextTypes
)
from shortener_api import create_short_link

# 🔧 Config - Update these!
API_TOKEN = "7543065984:AAE-uDLt92tbZ2kHpgOhDyjZ-dBHTcKgHg0"
BOT_USERNAME = "Chitose_robot"
GROUP_ID = -1002453946876
DAILY_LIMIT = 1  # Set user daily mission limit
SHORTENERS = ["linkcents"]  # Add to rotate if multiple

# 📂 Files
USERS_FILE = "users.json"
CODES_FILE = "codes.json"

# ✅ Ensure storage files exist
for file in [USERS_FILE, CODES_FILE]:
    if not os.path.exists(file):
        with open(file, "w") as f:
            json.dump({}, f)

# 🔁 JSON helpers
def load_json(f): return json.load(open(f, "r"))
def save_json(f, d): open(f, "w").write(json.dumps(d, indent=2))

# 🎯 User and mission logic
def get_user(uid):
    users = load_json(USERS_FILE)
    u = users.setdefault(str(uid), {
        "balance": 0.0,
        "referral": None,
        "referred_users": [],
        "today_count": 0,
        "last_day": "",
        "shortener_count": {},
        "history": []
    })
    # Reset daily if new day
    today = datetime.date.today().isoformat()
    if u["last_day"] != today:
        u["today_count"] = 0
        u["last_day"] = today
        u["shortener_count"] = {}
    save_json(USERS_FILE, users)
    return u

def add_balance(uid, amt, note):
    users = load_json(USERS_FILE)
    u = users[str(uid)]
    u["balance"] += amt
    u["history"].append(f"+₹{amt:.3f} {note}")
    save_json(USERS_FILE, users)

def gen_code(): return ''.join(random.choices(string.ascii_uppercase + string.digits, k=6))

# ✨ /start handler with media + navigation buttons
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    args = context.args
    get_user(user.id)

    if args:
        ref = args[0]
        ref_user = get_user(ref)
        if user.id not in ref_user["referred_users"]:
            ref_user["referred_users"].append(user.id)
            save_json(USERS_FILE, load_json(USERS_FILE))

    keyboard = [[
        InlineKeyboardButton("🎯 Missions", callback_data="m_"),
        InlineKeyboardButton("👥 Refer", callback_data="r_")
    ],[
        InlineKeyboardButton("💰 Balance", callback_data="b_"),
        InlineKeyboardButton("📤 Withdraw", callback_data="w_")
    ]]
    await update.message.reply_photo(
        photo="https://telegra.ph/file/050a20dace942a60220c0-6afbc023e43fad29c7.jpg",
        caption="*🚀 Welcome to Chitose‑Earning Bot!*\nEarn via shortener missions and referrals!",
        parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )

# 🧭 Navigation callbacks
async def nav_cb(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    uid = q.from_user.id

    if q.data == "m_":  # Mission
        u = get_user(uid)
        if u["today_count"] >= DAILY_LIMIT:
            return await q.message.reply_text(f"You reached daily limit of {DAILY_LIMIT} missions 🌙")
        code = gen_code()
        short = create_short_link(code)
        codes = load_json(CODES_FILE)
        codes[code] = {"user": uid, "claimed": False}
        save_json(CODES_FILE, codes)

        u["today_count"] += 1
        sc = u["shortener_count"]
        sc["linkcents"] = sc.get("linkcents", 0) + 1
        add_balance(uid, 0, "")  # touch saving only
        save_json(USERS_FILE, load_json(USERS_FILE))

        return await q.message.reply_text(
            f"🔗 *Click & complete*: {short}\nOnce done, send code: `{code}`",
            parse_mode="Markdown"
        )

    if q.data == "r_":
        return await q.message.reply_text(f"👥 Invite: `https://t.me/{BOT_USERNAME}?start={uid}`", parse_mode="Markdown")

    if q.data == "b_":
        bal = get_user(uid)["balance"]
        return await q.message.reply_text(f"💰 *Balance:* ₹{bal:.3f}", parse_mode="Markdown")

    if q.data == "w_":
        return await q.message.reply_text("📤 To withdraw, send:\n`<UPI_ID> <Amount>` (₹1‑10)", parse_mode="Markdown")

# 📥 Code replies
async def code_reply(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text.strip().upper()
    codes = load_json(CODES_FILE)
    if text not in codes:
        return await update.message.reply_text("❌ Invalid code.")
    entry = codes[text]
    if entry["claimed"]:
        return await update.message.reply_text("❌ Already used.")
    uid = entry["user"]
    if uid != update.effective_user.id:
        return await update.message.reply_text("❌ This isn't your code.")

    entry["claimed"] = True
    save_json(CODES_FILE, codes)
    add_balance(uid, 0.01, "Mission")
    u = get_user(uid)
    ref = u["referral"]
    if ref:
        add_balance(ref, 0.01, "Referral")
        add_balance(ref, 0.001, "Ref‑Watch")

    await update.message.reply_text("✅ Code accepted! ₹0.01 credited.")

# 🏦 Withdraw handler (UPI text)
async def withdraw_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    parts = update.message.text.strip().split()
    if len(parts) != 2: return
    upi, amt = parts
    try:
        amt = float(amt)
    except:
        return
    if amt < 1 or amt > 10: 
        return await update.message.reply_text("Amount must be ₹1‑10")
    bal = get_user(update.effective_user.id)["balance"]
    if amt > bal:
        return await update.message.reply_text("Insufficient balance.")

    add_balance(update.effective_user.id, -amt, f"Withdraw {upi}")
    await update.message.reply_text("✅ Withdrawal request sent to admin.")
    await context.bot.send_message(GROUP_ID, f"💸 Withdraw {amt} from {update.effective_user.id}, UPI: `{upi}`", parse_mode="Markdown")

# 🚀 Run app
app = Flask(__name__)

@app.route(f"/{API_TOKEN}", methods=["POST"])
def webhook():
    data = request.get_json(force=True)
    update = Update.de_json(data, context.bot)
    context.application.process_update(update)
    return "ok"

@app.route("/")
def index(): return "Bot running"

if __name__ == "__main__":
    application = ApplicationBuilder().token(API_TOKEN).build()
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CallbackQueryHandler(nav_cb))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, code_reply))
    application.add_handler(MessageHandler(filters.Regex(r".+ .+"), withdraw_handler))

    application.run_polling()
