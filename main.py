import os
import json
import random
import string
import datetime
from flask import Flask, request
from telegram import (
    Update, InlineKeyboardButton, InlineKeyboardMarkup
)
from telegram.ext import (
    ApplicationBuilder, CommandHandler, MessageHandler, CallbackQueryHandler,
    filters, ContextTypes
)
from shortener_api import create_short_link  # Your shortener integration

# Config - Replace with your own values
API_TOKEN = "7543065984:AAE-uDLt92tbZ2kHpgOhDyjZ-dBHTcKgHg0"
ADMIN_IDS = [5759232282]  # Admin Telegram user IDs for notifications
GROUP_ID = -1002453946876  # Group or channel ID to receive withdrawal requests
BOT_USERNAME = "Chitose_robot"
DAILY_LIMIT = 1  # Daily mission limit per user
SHORTENERS = ["linkcents"]  # List shorteners to rotate

# Storage files
USERS_FILE = "users.json"
CODES_FILE = "codes.json"

# Ensure storage files exist
for file in [USERS_FILE, CODES_FILE]:
    if not os.path.exists(file):
        with open(file, "w") as f:
            json.dump({}, f)

# JSON helpers
def load_json(file):
    with open(file, "r") as f:
        return json.load(f)

def save_json(file, data):
    with open(file, "w") as f:
        json.dump(data, f, indent=2)

# User management
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
    today = datetime.date.today().isoformat()
    if u["last_day"] != today:
        u["today_count"] = 0
        u["last_day"] = today
        u["shortener_count"] = {}
        save_json(USERS_FILE, users)
    return u

def add_balance(uid, amount, note):
    users = load_json(USERS_FILE)
    u = users[str(uid)]
    u["balance"] += amount
    u["history"].append(f"+₹{amount:.3f} {note}")
    save_json(USERS_FILE, users)

def gen_code(length=6):
    return ''.join(random.choices(string.ascii_uppercase + string.digits, k=length))

# /start handler
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    args = context.args
    u = get_user(user.id)

    # Handle referral parameter if present
    if args:
        ref_id = args[0]
        if ref_id != str(user.id):
            ref_user = get_user(ref_id)
            if user.id not in ref_user["referred_users"]:
                ref_user["referred_users"].append(user.id)
                # Set referral only if not set before
                if u["referral"] is None:
                    u["referral"] = int(ref_id)
                save_json(USERS_FILE, load_json(USERS_FILE))

    keyboard = [
        [
            InlineKeyboardButton("🎯 Missions", callback_data="m_"),
            InlineKeyboardButton("👥 Refer", callback_data="r_")
        ],
        [
            InlineKeyboardButton("💰 Balance", callback_data="b_"),
            InlineKeyboardButton("📤 Withdraw", callback_data="w_")
        ],
        [
            InlineKeyboardButton("❌ Close", callback_data="close_")
        ]
    ]
    await update.message.reply_photo(
        photo="https://telegra.ph/file/050a20dace942a60220c0-6afbc023e43fad29c7.jpg",
        caption=(
            "*🚀 Welcome to Chitose‑Earning Bot!*\n"
            "Earn via shortener missions and referrals!\n\n"
            "Use buttons below to get started."
        ),
        parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )

# Callback query handler for navigation
async def nav_cb(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    uid = q.from_user.id

    if q.data == "m_":  # Missions
        u = get_user(uid)
        if u["today_count"] >= DAILY_LIMIT:
            await q.message.reply_text(f"You reached your daily limit of {DAILY_LIMIT} missions 🌙")
            return

        code = gen_code()
        short_url = create_short_link(code)  # Your shortener API call

        codes = load_json(CODES_FILE)
        codes[code] = {"user": uid, "claimed": False}
        save_json(CODES_FILE, codes)

        u["today_count"] += 1
        u["shortener_count"]["linkcents"] = u["shortener_count"].get("linkcents", 0) + 1
        add_balance(uid, 0, "")  # Save user data
        save_json(USERS_FILE, load_json(USERS_FILE))

        await q.message.reply_text(
            f"🔗 *Click & complete:* {short_url}\n"
            f"Once done, send code: `{code}`",
            parse_mode="Markdown"
        )
        return

    elif q.data == "r_":  # Referral link
        await q.message.reply_text(
            f"👥 Invite friends using your link:\n"
            f"`https://t.me/{BOT_USERNAME}?start={uid}`",
            parse_mode="Markdown"
        )
        return

    elif q.data == "b_":  # Balance
        balance = get_user(uid)["balance"]
        await q.message.reply_text(f"💰 *Balance:* ₹{balance:.3f}", parse_mode="Markdown")
        return

    elif q.data == "w_":  # Withdraw info
        await q.message.reply_text(
            "📤 To withdraw, send a message in this format:\n"
            "`<UPI_ID> <Amount>`\n"
            "Amount must be between ₹1 and ₹10.",
            parse_mode="Markdown"
        )
        return

    elif q.data == "close_":  # Close message
        await q.message.delete()
        return

# Code redemption handler
async def code_reply(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text.strip().upper()
    codes = load_json(CODES_FILE)
    if text not in codes:
        await update.message.reply_text("❌ Invalid code.")
        return

    entry = codes[text]
    if entry["claimed"]:
        await update.message.reply_text("❌ This code is already used.")
        return

    uid = entry["user"]
    if uid != update.effective_user.id:
        await update.message.reply_text("❌ This code does not belong to you.")
        return

    entry["claimed"] = True
    save_json(CODES_FILE, codes)

    add_balance(uid, 0.01, "Mission")

    user_data = get_user(uid)
    ref_id = user_data["referral"]
    if ref_id:
        add_balance(ref_id, 0.01, "Referral Bonus")
        add_balance(ref_id, 0.001, "Referral Watch Bonus")

    await update.message.reply_text("✅ Code accepted! ₹0.01 credited.")

# Withdraw handler (expecting "<UPI_ID> <Amount>" message)
async def withdraw_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    parts = update.message.text.strip().split()
    if len(parts) != 2:
        return
    upi, amt_str = parts
    try:
        amt = float(amt_str)
    except ValueError:
        return

    if amt < 1 or amt > 10:
        await update.message.reply_text("Amount must be between ₹1 and ₹10.")
        return

    user_id = update.effective_user.id
    user_data = get_user(user_id)

    if amt > user_data["balance"]:
        await update.message.reply_text("Insufficient balance for withdrawal.")
        return

    add_balance(user_id, -amt, f"Withdraw {upi}")

    await update.message.reply_text("✅ Withdrawal request sent to admin.")

    msg = (
        f"💸 Withdrawal Request:\n"
        f"User ID: {user_id}\n"
        f"Amount: ₹{amt:.2f}\n"
        f"UPI ID: `{upi}`"
    )

    # Notify admins
    for admin_id in ADMIN_IDS:
        await context.bot.send_message(chat_id=admin_id, text=msg, parse_mode="Markdown")

    # Also notify GROUP_ID if set and different from admin
    if GROUP_ID not in ADMIN_IDS:
        await context.bot.send_message(chat_id=GROUP_ID, text=msg, parse_mode="Markdown")

# Flask app & webhook
app = Flask(__name__)

@app.route(f"/{API_TOKEN}", methods=["POST"])
def webhook():
    from telegram import Update
    from telegram.ext import ContextTypes

    data = request.get_json(force=True)
    update = Update.de_json(data, application.bot)
    application.process_update(update)
    return "OK"

@app.route("/")
def index():
    return "Chitose-Earning Bot is running."

if __name__ == "__main__":
    application = ApplicationBuilder().token(API_TOKEN).build()

    # Command handlers
    application.add_handler(CommandHandler("start", start))

    # Callback query handler for buttons
    application.add_handler(CallbackQueryHandler(nav_cb))

    # Message handlers
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, code_reply))
    application.add_handler(MessageHandler(filters.Regex(r".+ .+"), withdraw_handler))

    # Start Flask app
    # For Render or other hosting platforms, port is usually from env var PORT
    port = int(os.environ.get("PORT", "8080"))

    # Save global bot and app reference for webhook
    bot = application.bot

    app.run(host="0.0.0.0", port=port)
