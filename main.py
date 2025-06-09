import os, json, random, string, datetime, requests
from flask import Flask, request
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    ApplicationBuilder, CommandHandler, MessageHandler,
    CallbackQueryHandler, filters, ContextTypes
)

# --- CONFIG ---
BOT_TOKEN = "8006836827:AAERFD1tDpBDJhvKm_AHy20uSAzZdoRwbZc"
BOT_USERNAME = "anime_fetch_robot"
GROUP_ID = -1002453946876  # Private channel
ADMIN_IDS = [5759232282]
DAILY_LIMIT = 5

USERS_FILE = "users.json"
CODES_FILE = "codes.json"

for f in [USERS_FILE, CODES_FILE]:
    if not os.path.exists(f):
        with open(f, "w") as wr:
            json.dump({}, wr)

def load_json(p): return json.load(open(p))
def save_json(p, d): open(p, "w").write(json.dumps(d, indent=2))

def gen_code(): return ''.join(random.choices(string.ascii_uppercase + string.digits, k=6))

def get_user(uid):
    users = load_json(USERS_FILE)
    u = users.setdefault(str(uid), {
        "balance": 0.0,
        "referral": None,
        "today": "",
        "count": 0,
        "history": [],
        "pending_code": None
    })
    today = datetime.date.today().isoformat()
    if u["today"] != today:
        u["today"], u["count"], u["pending_code"] = today, 0, None
    save_json(USERS_FILE, users)
    return u

def add_balance(uid, amt, note):
    users = load_json(USERS_FILE)
    u = users[str(uid)]
    u["balance"] += amt
    u["history"].append(f"+₹{amt:.3f} {note}")
    save_json(USERS_FILE, users)

def create_short_link(url):
    # Replace with your actual shortener API call
    # E.g. requests.get(...) and return shortened URL
    return url

app = Flask(__name__)
application = ApplicationBuilder().token(BOT_TOKEN).build()

# --- /start ---
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    u = get_user(uid)
    args = context.args
    if args and u["referral"] is None:
        ref = args[0]
        if ref != str(uid):
            u["referral"] = ref
            save_json(USERS_FILE, load_json(USERS_FILE))

    kb = [
        [InlineKeyboardButton("🎯 Shortener", callback_data="cmd_short")],
        [InlineKeyboardButton("👥 Refer", callback_data="cmd_refer"),
         InlineKeyboardButton("💰 Balance", callback_data="cmd_balance")],
        [InlineKeyboardButton("📤 Withdraw", callback_data="cmd_withdraw")],
    ]
    await update.message.reply_photo(
        photo="https://telegra.ph/file/050a20dace942a60220c0-6afbc023e43fad29c7.jpg",
        caption="🚀 *Welcome to Chitose Earning Bot!*\nEarn ₹0.01 per shortener task.",
        parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup(kb),
    )

# --- /shortener via button or command ---
async def cmd_short(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    u = get_user(uid)
    if u["count"] >= DAILY_LIMIT:
        return await update.message.reply_text("❌ Daily limit reached.")
    if u["pending_code"]:
        code = u["pending_code"]
        codes = load_json(CODES_FILE)
        if not codes[code]["used"]:
            return await update.message.reply_text(
                f"🔗 Task pending! Use link:\n{codes[code]['url']}"
            )
    code = gen_code()
    # Post code in private channel
    msg = await context.bot.send_message(
        chat_id=GROUP_ID,
        text=f"🎁 Code for `{uid}`: `{code}`",
        parse_mode="Markdown"
    )
    task_link = f"https://t.me/{BOT_USERNAME}?start={code}"
    short = create_short_link(task_link)
    codes = load_json(CODES_FILE)
    codes[code] = {"uid": uid, "used": False, "url": short}
    save_json(CODES_FILE, codes)
    u["pending_code"], u["count"] = code, u["count"] + 1
    save_json(USERS_FILE, load_json(USERS_FILE))
    return await update.message.reply_text(
        f"🔗 Here’s your short link:\n{short}\n🔁 Complete it and come back to redeem."
    )

# --- /verify command ---
async def verify(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        return await update.message.reply_text("Usage: /verify <CODE>")
    code = context.args[0].strip().upper()
    codes = load_json(CODES_FILE)
    if code not in codes:
        return await update.message.reply_text("❌ Invalid code.")
    data = codes[code]
    if data["used"]:
        return await update.message.reply_text("⚠️ Code already used.")
    uid = update.effective_user.id
    if data["uid"] != uid:
        return await update.message.reply_text("🚫 Not your code.")
    # Mark as used
    data["used"] = True
    save_json(CODES_FILE, codes)
    u = get_user(uid)
    u["pending_code"] = None
    save_json(USERS_FILE, load_json(USERS_FILE))
    add_balance(uid, 0.01, "Mission completed")
    if u["referral"]:
        add_balance(int(u["referral"]), 0.01, "Referral")
        add_balance(int(u["referral"]), 0.001, "Ref-Watch")
    return await update.message.reply_text(
        "✅ Successfully claimed ₹0.01!"
    )

# --- Callback Buttons ---
async def cb_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    cmd = q.data
    if cmd == "cmd_short":
        return await cmd_short(update, context)
    if cmd == "cmd_balance":
        bal = get_user(q.from_user.id)["balance"]
        return await q.message.reply_text(f"💰 Balance: ₹{bal:.2f}")
    if cmd == "cmd_refer":
        uid = q.from_user.id
        return await q.message.reply_text(
            f"🔗 Invite Link:\nhttps://t.me/{BOT_USERNAME}?start={uid}",
            parse_mode="Markdown"
        )
    if cmd == "cmd_withdraw":
        return await q.message.reply_text("📤 Send `<UPI_ID> <Amount>` (₹1-10)")

# --- Catch All Text for /verify, withdrawal ---
async def text_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    txt = update.message.text.strip()
    if ' ' in txt:
        upi, amt = txt.split(None, 1)
        try:
            amt = float(amt)
        except:
            return
        u = get_user(update.effective_user.id)
        if 1 <= amt <= 10 and u["balance"] >= amt:
            add_balance(update.effective_user.id, -amt, f"Withdraw to {upi}")
            await update.message.reply_text("💸 Withdrawal requested!")
            for aid in ADMIN_IDS:
                await context.bot.send_message(aid, f"📤 User {update.effective_user.id} withdraw ₹{amt} to {upi}")
        return
    # ignore other chat

# --- Setup ---
application.add_handler(CommandHandler("start", start))
application.add_handler(CommandHandler("shortener", cmd_short))
application.add_handler(CommandHandler("verify", verify))
application.add_handler(CallbackQueryHandler(cb_handler))
application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, text_handler))

# Use polling for now
application.run_polling()
