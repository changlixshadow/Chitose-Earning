# main.py

import os
import json
import random
import string
import time
import requests
from datetime import datetime, timedelta
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, InputMediaPhoto
from telegram.ext import (Application, CommandHandler, MessageHandler, filters,
                          CallbackQueryHandler, ContextTypes, ConversationHandler)
from telegram.constants import ParseMode

# =============== CONFIG ===================
TOKEN = "8006836827:AAERFD1tDpBDJhvKm_AHy20uSAzZdoRwbZc"
ADMIN_ID = 5759232282
START_IMAGE = "https://telegra.ph/file/050a20dace942a60220c0-6afbc023e43fad29c7.jpg"
ABOUT_IMAGE = "https://telegra.ph/file/9d18345731db88fff4f8c-d2b3920631195c5747.jpg"
HELP_IMAGE = "https://telegra.ph/file/e6ec31fc792d072da2b7e-54e7c7d4c5651823b3.jpg"

LINKCENTS_API_KEY = "a3dede8bbc12f4bd0afd61cf1ac691f3545d5faf"
BASE_EARN_URL = "https://yourdestinationlink.com"
SHORTEN_LIMIT = 5
SHORTEN_INTERVAL = 12 * 60 * 60  # 12 hours in seconds

USERS_FILE = "users.json"
CODES_FILE = "codes.json"
HISTORY_FILE = "history.json"
ASK_UPI = range(1)

# =============== UTILS ===================
def load_json(fn): return json.load(open(fn)) if os.path.exists(fn) else {}
def save_json(fn, data): json.dump(data, open(fn, 'w'), indent=2)

# =============== USER MGMT =================
def get_user(uid):
    u = load_json(USERS_FILE)
    uid = str(uid)
    if uid not in u:
        u[uid] = {"balance": 0.0, "used_codes": [], "upi": None, "referrals": [],
                  "refer_by": None, "last_time": 0, "shorts_done": 0}
        save_json(USERS_FILE, u)
    return u[uid]

def update_user(uid, data):
    u = load_json(USERS_FILE)
    u[str(uid)] = data
    save_json(USERS_FILE, u)

def log_history(uid, text):
    h = load_json(HISTORY_FILE)
    h.setdefault(str(uid), []).append({"time": time.time(), "action": text})
    save_json(HISTORY_FILE, h)

# =============== CODE MGMT =================
def is_code_used(code): return code in load_json(CODES_FILE)
def add_code(code):
    d = load_json(CODES_FILE)
    d[code] = True
    save_json(CODES_FILE, d)

# =============== SHORTENER ==================
def gen_alias(): return ''.join(random.choices(string.ascii_letters + string.digits, k=6))
def generate_short_link(uid):
    alias = gen_alias()
    url = f"{BASE_EARN_URL}?ref={uid}"
    api_url = f"https://linkcents.com/api?api={LINKCENTS_API_KEY}&url={url}&alias={alias}"
    response = requests.get(api_url).json()
    return response.get("shortenedUrl", "")

# =============== UI =========================
def main_kb():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("📢 About", callback_data="about"),
         InlineKeyboardButton("🆘 Help", callback_data="help")],
        [InlineKeyboardButton("❌ Close", callback_data="close")]
    ])

def back_kb():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("🔙 Back", callback_data="start")],
        [InlineKeyboardButton("❌ Close", callback_data="close")]
    ])

# =============== COMMAND HANDLERS ===============
async def start(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    args = ctx.args
    user = get_user(uid)

    if args and args[0] != str(uid) and not user["refer_by"]:
        user["refer_by"] = args[0]
        update_user(uid, user)

    txt = ("<b>🎉 Welcome!</b>\n💰 Use /shortener to earn by sharing links.\n"
           "💼 Commands: /balance /withdraw /refer /history\n👥 Share referral to earn more.")
    await update.message.reply_photo(START_IMAGE, caption=txt, parse_mode=ParseMode.HTML, reply_markup=main_kb())

async def cb_handler(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    data = q.data

    if data == "close":
        return await q.message.delete()

    images = {"start": START_IMAGE, "about": ABOUT_IMAGE, "help": HELP_IMAGE}
    captions = {
        "start": "<b>🎉 Welcome Back!</b>",
        "about": "<b>📢 About:</b> Earn by sharing links and referring.",
        "help": "<b>🆘 Help:</b>\nUse /shortener to get links. Submit code here after completion."
    }
    kb = main_kb() if data == "start" else back_kb()
    await q.message.edit_media(InputMediaPhoto(images[data]), caption=captions[data], parse_mode=ParseMode.HTML, reply_markup=kb)

async def shortener(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    user = get_user(uid)
    now = time.time()

    if user["shorts_done"] >= SHORTEN_LIMIT and now - user["last_time"] < SHORTEN_INTERVAL:
        return await update.message.reply_text("🚫 12 hour limit exceeded. Come back later!")

    if now - user["last_time"] >= SHORTEN_INTERVAL:
        user["shorts_done"] = 0

    link = generate_short_link(uid)
    user["shorts_done"] += 1
    user["last_time"] = now
    update_user(uid, user)
    log_history(uid, f"Claimed short link: {link}")

    await update.message.reply_text(f"🔗 Your short link:\n{link}\n\n📝 After visiting, submit the code you get here.")

async def handle_code(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    code = update.message.text.strip()
    uid = update.effective_user.id
    user = get_user(uid)

    if not code or is_code_used(code):
        return await update.message.reply_text("❌ Invalid or already used code.")

    add_code(code)
    user["balance"] += 0.01
    user["used_codes"].append(code)
    update_user(uid, user)
    log_history(uid, f"Code submitted: {code}")

    # Referral reward
    ref_id = user.get("refer_by")
    if ref_id:
        ref_user = get_user(ref_id)
        if uid not in ref_user["referrals"]:
            ref_user["referrals"].append(uid)
            ref_user["balance"] += 0.01  # Referral reward
            log_history(ref_id, f"Referral complete by {uid}")
            update_user(ref_id, ref_user)

        # Referral bonus
        ref_user["balance"] += 0.001
        update_user(ref_id, ref_user)

    await update.message.reply_text("✅ Code accepted! You earned ₹0.01")

async def balance(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    user = get_user(update.effective_user.id)
    await update.message.reply_text(f"💰 Your balance: ₹{user['balance']:.3f}")

async def refer(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    user = get_user(update.effective_user.id)
    bot = await ctx.bot.get_me()
    ref_link = f"https://t.me/{bot.username}?start={update.effective_user.id}"
    await update.message.reply_text(f"👥 Share this link:\n{ref_link}")

async def history(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    logs = load_json(HISTORY_FILE).get(str(update.effective_user.id), [])
    if not logs:
        return await update.message.reply_text("📜 No transaction history.")
    msg = "\n".join([f"{datetime.fromtimestamp(e['time']).strftime('%d-%m %H:%M')} - {e['action']}" for e in logs[-10:]])
    await update.message.reply_text(f"📜 Last 10 transactions:\n{msg}")

async def withdraw(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    user = get_user(update.effective_user.id)
    if not (1 <= user["balance"] <= 10):
        return await update.message.reply_text("❌ Withdraw between ₹1 to ₹10 only.")
    await update.message.reply_text(f"💳 Enter your UPI ID to withdraw ₹{user['balance']:.2f}:")
    return ASK_UPI

async def recv_upi(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    user = get_user(uid)
    user["upi"] = update.message.text
    amt = user["balance"]
    user["balance"] = 0
    update_user(uid, user)
    log_history(uid, f"Withdrawal requested ₹{amt:.2f} to {user['upi']}")
    await ctx.bot.send_message(ADMIN_ID, f"💸 Withdraw Request:\nUser: {uid}\nAmt: ₹{amt:.2f}\nUPI: {user['upi']}")
    await update.message.reply_text("✅ Withdrawal request submitted! Paid in 24h.")
    return ConversationHandler.END

async def users(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID:
        return await update.message.reply_text("⛔ Unauthorized")
    u = load_json(USERS_FILE)
    msg = f"👥 Total users: {len(u)}\n"
    for i, (uid, dat) in enumerate(sorted(u.items(), key=lambda x: x[1]['balance'], reverse=True)[:5], 1):
        msg += f"{i}. {uid}: ₹{dat['balance']:.3f}\n"
    await update.message.reply_text(msg)

# =============== SETUP ===================
withdraw_conv = ConversationHandler(
    entry_points=[CommandHandler("withdraw", withdraw)],
    states={ASK_UPI: [MessageHandler(filters.TEXT & ~filters.COMMAND, recv_upi)]},
    fallbacks=[]
)

app = Application.builder().token(TOKEN).build()
handlers = [
    CommandHandler("start", start),
    CallbackQueryHandler(cb_handler),
    CommandHandler("shortener", shortener),
    CommandHandler("balance", balance),
    CommandHandler("refer", refer),
    CommandHandler("withdraw", withdraw),
    CommandHandler("history", history),
    CommandHandler("users", users),
    withdraw_conv,
    MessageHandler(filters.TEXT & ~filters.COMMAND, handle_code)
]
for h in handlers: app.add_handler(h)
print("✅ Bot running...")
app.run_polling()
