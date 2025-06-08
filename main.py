import os
import json
import random
import string
import time
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, InputMediaPhoto
from telegram.ext import (
    Application, CommandHandler, MessageHandler, filters,
    CallbackQueryHandler, ContextTypes, ConversationHandler
)
from telegram.constants import ParseMode

TOKEN = "8006836827:AAERFD1tDpBDJhvKm_AHy20uSAzZdoRwbZc"

ADMIN_ID = 5759232282

START_IMAGE = "https://telegra.ph/file/050a20dace942a60220c0-6afbc023e43fad29c7.jpg"
ABOUT_IMAGE = "https://telegra.ph/file/9d18345731db88fff4f8c-d2b3920631195c5747.jpg"
HELP_IMAGE = "https://telegra.ph/file/e6ec31fc792d072da2b7e-54e7c7d4c5651823b3.jpg"

USERS_FILE = "users.json"
CODES_FILE = "codes.json"
SHORTENERS_FILE = "shorteners.json"
ASK_UPI = range(1)

# ========== UTILITIES ==========
def load_json(path): return json.load(open(path)) if os.path.exists(path) else {}
def save_json(path, data): json.dump(data, open(path, 'w'), indent=2)

def get_user(uid: int):
    data = load_json(USERS_FILE)
    if str(uid) not in data:
        data[str(uid)] = {"balance": 0.0, "used_codes": [], "upi": None, "referrals": [], "refer_by": None, "shortener_index": 0}
        save_json(USERS_FILE, data)
    return data[str(uid)]

def update_user(uid: int, new_data: dict):
    data = load_json(USERS_FILE)
    data[str(uid)] = new_data
    save_json(USERS_FILE, data)

def is_code_used(code): return code in load_json(CODES_FILE)
def add_code(code):
    data = load_json(CODES_FILE)
    data[code] = True
    save_json(CODES_FILE, data)

def gen_alias(): return ''.join(random.choices(string.ascii_letters + string.digits, k=6))

# ========== MAIN HANDLERS ==========
def main_kb(): return InlineKeyboardMarkup([
    [InlineKeyboardButton("📢 About", callback_data="about"), InlineKeyboardButton("🆘 Help", callback_data="help")],
    [InlineKeyboardButton("❌ Close", callback_data="close")]
])
def back_kb(): return InlineKeyboardMarkup([
    [InlineKeyboardButton("🔙 Back", callback_data="start"), InlineKeyboardButton("❌ Close", callback_data="close")]
])

async def start(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    args = ctx.args
    if args and args[0] != str(uid):
        user = get_user(uid)
        if not user["refer_by"]:
            user["refer_by"] = args[0]
            update_user(uid, user)
            ref_user = get_user(int(args[0]))
            ref_user["balance"] += 0.02
            ref_user["referrals"].append(uid)
            update_user(int(args[0]), ref_user)
    text = ("<b>🎉 Welcome!</b>\n"
            "💰 Use /shortener to earn by sharing links.\n"
            "💼 /balance, /withdraw, /refer\n"
            "📞 Friendly bot with buttons below.")
    await update.message.reply_photo(START_IMAGE, caption=text, parse_mode=ParseMode.HTML, reply_markup=main_kb())

async def cb_handler(update: Update, ctx):
    q = update.callback_query
    await q.answer()
    data = q.data
    if data == "close":
        return await q.message.delete()
    img = {"start": START_IMAGE, "about": ABOUT_IMAGE, "help": HELP_IMAGE}[data]
    caption = {
        "start": "🎉 Welcome back!",
        "about": "<b>📢 About</b>\nEarn by sharing short links.",
        "help": "<b>🆘 Help</b>\nUse commands like /shortener and /refer to earn money."
    }[data]
    kb = main_kb() if data == "start" else back_kb()
    await q.message.edit_media(InputMediaPhoto(img), caption=caption, parse_mode=ParseMode.HTML, reply_markup=kb)

# ========== SHORTENER ==========
async def shortener(update: Update, ctx):
    uid = update.effective_user.id
    user = get_user(uid)
    shorteners = load_json(SHORTENERS_FILE)
    idx = user.get("shortener_index", 0)

    if idx >= len(shorteners):
        return await update.message.reply_text("✅ Today’s mission completed! Come back tomorrow.")

    short_api = shorteners[idx]["api"]
    alias = gen_alias()
    earn_url = f"https://yourdestinationlink.com?ref={uid}"
    final_link = short_api.replace("{url}", earn_url).replace("{alias}", alias)

    user["shortener_index"] = idx + 1
    user["last"] = final_link
    update_user(uid, user)

    all_links = load_json("shortlinks.json")
    all_links[alias] = {"user": uid, "short": final_link, "url": earn_url, "time": time.time()}
    save_json("shortlinks.json", all_links)

    await update.message.reply_text(f"🔗 Your short link:\n{final_link}")

# ========== BASIC COMMANDS ==========
async def balance(update: Update, ctx): await update.message.reply_text(f"💰 Balance: ₹{get_user(update.effective_user.id)['balance']:.2f}")

async def refer(update: Update, ctx):
    uid = update.effective_user.id
    bot_name = (await ctx.bot.get_me()).username
    user = get_user(uid)
    ref_link = f"https://t.me/{bot_name}?start={uid}"
    await update.message.reply_text(f"👥 Referred: {len(user['referrals'])}\nReferral Link:\n{ref_link}", parse_mode=ParseMode.HTML)

# ========== WITHDRAW ==========
async def withdraw(update: Update, ctx):
    user = get_user(update.effective_user.id)
    if not (1 <= user["balance"] <= 10):
        return await update.message.reply_text("❌ Withdraw between ₹1–₹10 only.")
    await update.message.reply_text(f"Enter your UPI to withdraw ₹{user['balance']:.2f}")
    return ASK_UPI

async def recv_upi(update: Update, ctx):
    uid = update.effective_user.id
    user = get_user(uid)
    upi = update.message.text.strip()
    amt = user["balance"]
    user["upi"] = upi
    user["balance"] = 0
    update_user(uid, user)
    await ctx.bot.send_message(ADMIN_ID, f"Withdraw request from {uid}\nUPI: {upi}\nAmount: ₹{amt:.2f}")
    await update.message.reply_text("✅ Withdraw requested. You’ll be paid within 24h.")
    return ConversationHandler.END

# ========== CODE SYSTEM ==========
async def handle_code(update: Update, ctx):
    code = update.message.text.strip()
    uid = update.effective_user.id
    if not code or is_code_used(code):
        return await update.message.reply_text("❌ Invalid or already used code.")
    add_code(code)
    user = get_user(uid)
    user["balance"] += 0.01
    user["used_codes"].append(code)
    update_user(uid, user)
    await update.message.reply_text("✅ Code accepted! You earned ₹0.01.")

# ========== ADMIN ==========
async def users_cmd(update: Update, ctx):
    if update.effective_user.id != ADMIN_ID:
        return await update.message.reply_text("❌ Unauthorized.")
    users = load_json(USERS_FILE)
    top = sorted(users.items(), key=lambda x: x[1]["balance"], reverse=True)[:5]
    msg = f"👥 Total Users: {len(users)}\n"
    for i, (uid, data) in enumerate(top, 1):
        msg += f"{i}. {uid}: ₹{data['balance']:.2f}\n"
    await update.message.reply_text(msg)

# ========== MAIN ==========
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
    CommandHandler("users", users_cmd),
    withdraw_conv,
    MessageHandler(filters.TEXT & ~filters.COMMAND, handle_code),
]
for h in handlers: app.add_handler(h)

print("✅ Bot running..."); app.run_polling()
