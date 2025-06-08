import os
import json
import random
import string
import time
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, InputMediaPhoto
from telegram.ext import (Application, CommandHandler, MessageHandler, filters,
                          CallbackQueryHandler, ContextTypes, ConversationHandler)
from telegram.constants import ParseMode

# =============== CONFIG ===================
TOKEN = "YOUR_TOKEN_HERE"
ADMIN_ID = 5759232282  # Your Telegram ID

START_IMAGE = "https://telegra.ph/file/050a20dace942a60220c0-6afbc023e43fad29c7.jpg"
ABOUT_IMAGE = "https://telegra.ph/file/9d18345731db88fff4f8c-d2b3920631195c5747.jpg"
HELP_IMAGE = "https://telegra.ph/file/e6ec31fc792d072da2b7e-54e7c7d4c5651823b3.jpg"

USERS_FILE = "users.json"
CODES_FILE = "codes.json"
SHORTENERS_FILE = "shorteners.json"

LINKCENTS_API_KEY = "a3dede8bbc12f4bd0afd61cf1ac691f3545d5faf"
BASE_EARN_URL = "https://yourdestinationlink.com"

ASK_UPI = range(1)

# =============== JSON UTILS ===============
def load_json(fn): return json.load(open(fn)) if os.path.exists(fn) else {}
def save_json(fn, data): json.dump(data, open(fn, 'w'), indent=2)

# ============ USER MANAGEMENT ===========
def get_user(uid: int):
    u = load_json(USERS_FILE)
    if str(uid) not in u:
        u[str(uid)] = {"balance": 0.0, "used_codes": [], "upi": None, "referrals": [], "refer_by": None}
        save_json(USERS_FILE, u)
    return u[str(uid)]

def update_user(uid:int, data:dict):
    u = load_json(USERS_FILE); u[str(uid)] = data; save_json(USERS_FILE, u)

# ============ CODE MANAGEMENT ===========
def is_code_used(code): return code in load_json(CODES_FILE)
def add_code(code):
    d = load_json(CODES_FILE); d[code] = True; save_json(CODES_FILE, d)

# ========== SHORT LINK GENERATION =========
def gen_alias(): return ''.join(random.choices(string.ascii_letters+string.digits, k=6))
def gen_short_link(uid: int):
    alias = gen_alias()
    url = f"{BASE_EARN_URL}?ref={uid}"
    link = f"https://linkcents.com/api?api={LINKCENTS_API_KEY}&url={url}&alias={alias}"

    data = load_json(SHORTENERS_FILE)
    data[alias] = {"user": uid, "url": url, "short": link, "time": time.time()}
    save_json(SHORTENERS_FILE, data)

    return link

# ========== HANDLER HELPERS ==========
def main_kb(): return InlineKeyboardMarkup([
    [InlineKeyboardButton("📢 About", "about"), InlineKeyboardButton("🆘 Help", "help")],
    [InlineKeyboardButton("❌ Close", "close")]
])
def back_kb(): return InlineKeyboardMarkup([
    [InlineKeyboardButton("🔙 Back", "start"), InlineKeyboardButton("❌ Close", "close")]
])

# =========== BOT HANDLERS ============
async def start(update: Update, ctx):
    uid = update.effective_user.id
    args = ctx.args
    if args and args[0]!=str(uid):
        u = get_user(uid)
        if not u["refer_by"]:
            u["refer_by"]=args[0]; update_user(uid,u)
            r = get_user(int(args[0])); r["balance"]+=0.02; r["referrals"].append(uid); update_user(int(args[0]), r)
    txt = ("<b>🎉 Welcome!</b>\n"
           "💰 Use /shortener to earn by sharing links.\n"
           "💼 /balance, /withdraw, /refer.\n"
           "📞 Friendly bot with Buttons below.")
    await update.message.reply_photo(START_IMAGE, caption=txt, parse_mode=ParseMode.HTML, reply_markup=main_kb())

async def cb_handler(update: Update, ctx):
    q = update.callback_query; await q.answer()
    d = q.data
    if d=="close": return await q.message.delete()
    md = EXPECTED = {"start":START_IMAGE, "about":ABOUT_IMAGE, "help":HELP_IMAGE}[d]
    caption = {"start": "🎉 Welcome back!", 
               "about": "<b>📢 About</b>\nEarn by sharing short links.", 
               "help": "<b>🆘 Help</b>\nUse commands to earn."}[d]
    kb = main_kb() if d=="start" else back_kb()
    await q.message.edit_media(InputMediaPhoto(md), caption=caption, parse_mode=ParseMode.HTML, reply_markup=kb)

async def shortener(update: Update, ctx):
    uid = update.effective_user.id
    link = gen_short_link(uid); u = get_user(uid); u["last"] = link; update_user(uid,u)
    await update.message.reply_text(f"🔗 Your short link:\n{link}")

async def balance(update: Update, ctx):
    u = get_user(update.effective_user.id)
    await update.message.reply_text(f"💰 Balance: ₹{u['balance']:.2f}")

async def refer(update: Update, ctx):
    u = get_user(update.effective_user.id)
    cnt = len(u["referrals"])
    ref = await ctx.bot.get_me()
    link = f"https://t.me/{ref.username}?start={update.effective_user.id}"
    await update.message.reply_text(f"👥 Referred: {cnt}\nReferral link:\n{link}", parse_mode=ParseMode.HTML)

async def withdraw(update: Update, ctx):
    u = get_user(update.effective_user.id)
    if not (1<=u["balance"]<=10): return await update.message.reply_text("❌ Withdraw between ₹1-10 only.")
    await update.message.reply_text(f"Enter your UPI to withdraw ₹{u['balance']:.2f}")
    return ASK_UPI

async def recv_upi(update: Update, ctx):
    uid = update.effective_user.id; u = get_user(uid); amt = u["balance"]; u["upi"]=update.message.text; u["balance"]=0; update_user(uid,u)
    await ctx.bot.send_message(ADMIN_ID, f"Withdraw request: uid={uid}, amt=₹{amt:.2f}, UPI={u['upi']}")
    await update.message.reply_text("✅ Requested! You’ll be paid within 24h.")
    return ConversationHandler.END

async def handle_code(update: Update, ctx):
    code = update.message.text.strip()
    if not code or is_code_used(code):
        return await update.message.reply_text("❌ Invalid or used code.")
    add_code(code); u=get_user(update.effective_user.id); u["balance"]+=0.01; u["used_codes"].append(code); update_user(u:=update.effective_user.id, u)
    await update.message.reply_text("✅ Code accepted! You earned ₹0.01")

async def users_cmd(update: Update, ctx):
    if update.effective_user.id!=ADMIN_ID:
        return await update.message.reply_text("❌ Unauthorized.")
    u=load_json(USERS_FILE); total=len(u)
    top=sorted(u.items(), key=lambda x: x[1]["balance"], reverse=True)[:5]
    msg=f"👥 Users: {total}\n"
    for i,(uid,dat) in enumerate(top,1):
        msg+=f"{i}. {uid}: ₹{dat['balance']:.2f}\n"
    await update.message.reply_text(msg)

# Register handlers
withdraw_conv = ConversationHandler(entry_points=[CommandHandler("withdraw", withdraw)],
    states={ASK_UPI:[MessageHandler(filters.TEXT & ~filters.COMMAND, recv_upi)]}, fallbacks=[])
app = Application.builder().token(TOKEN).build()
for h in [CommandHandler("start", start), CallbackQueryHandler(cb_handler), CommandHandler("shortener", shortener),
          CommandHandler("balance", balance), CommandHandler("refer", refer), CommandHandler("users", users_cmd),
          withdraw_conv, MessageHandler(filters.TEXT & ~filters.COMMAND, handle_code)]:
    app.add_handler(h)

print("Bot running..."), app.run_polling()
