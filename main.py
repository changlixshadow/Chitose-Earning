import os
import json
import random
import string
import datetime
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    ApplicationBuilder, CommandHandler,
    CallbackQueryHandler, MessageHandler, filters
)
from shortener_api import create_short_link

# --- CONFIG ---
BOT_TOKEN = "8006836827:AAERFD1tDpBDJhvKm_AHy20uSAzZdoRwbZc"
BOT_USERNAME = "anime_fetch_robot"
ADMIN_IDS = [5759232282]
GROUP_ID = -1002453946876
DAILY_LIMIT = 1

# --- STORAGE FILES ---
USERS_FILE = "users.json"
CODES_FILE = "codes.json"

for f in [USERS_FILE, CODES_FILE]:
    if not os.path.exists(f):
        with open(f, "w") as wr:
            json.dump({}, wr)

# --- UTILITIES ---
def load_json(path):
    with open(path, "r") as f:
        return json.load(f)

def save_json(path, data):
    with open(path, "w") as f:
        json.dump(data, f, indent=2)

def gen_code():
    return ''.join(random.choices(string.ascii_uppercase + string.digits, k=6))

def get_user(uid):
    users = load_json(USERS_FILE)
    u = users.setdefault(str(uid), {
        "balance": 0.0,
        "referral": None,
        "today": "",
        "count": 0,
        "history": []
    })
    today = datetime.date.today().isoformat()
    if u["today"] != today:
        u["today"] = today
        u["count"] = 0
    save_json(USERS_FILE, users)
    return u

def add_balance(uid, amt, note):
    users = load_json(USERS_FILE)
    u = users[str(uid)]
    u["balance"] += amt
    u["history"].append(f"+₹{amt:.3f} {note}")
    save_json(USERS_FILE, users)

# --- COMMAND HANDLERS ---
async def start(update: Update, context):
    uid = update.effective_user.id
    u = get_user(uid)
    args = context.args
    if args:
        ref = args[0]
        if ref != str(uid) and u["referral"] is None:
            u["referral"] = ref
            save_json(USERS_FILE, load_json(USERS_FILE))

    kb = [
        [InlineKeyboardButton("🎯 Mission", callback_data="m")],
        [InlineKeyboardButton("👥 Refer", callback_data="r"),
         InlineKeyboardButton("💰 Balance", callback_data="b")],
        [InlineKeyboardButton("📤 Withdraw", callback_data="w")]
    ]
    await update.message.reply_photo(
        photo="https://telegra.ph/file/050a20dace942a60220c0-6afbc023e43fad29c7.jpg",
        caption="Welcome! Earn ₹0.01 per mission.",
        reply_markup=InlineKeyboardMarkup(kb)
    )

# --- CALLBACK HANDLER ---
async def cb_handler(update: Update, context):
    q = update.callback_query
    await q.answer()
    uid = q.from_user.id
    u = get_user(uid)

    if q.data == "m":
        if u["count"] >= DAILY_LIMIT:
            return await q.message.reply_text("Daily limit reached.")
        code = gen_code()
        link = create_short_link(code)
        # store mission
        codes = load_json(CODES_FILE)
        codes[code] = {"uid": uid, "used": False}
        save_json(CODES_FILE, codes)
        u["count"] += 1
        save_json(USERS_FILE, load_json(USERS_FILE))
        return await q.message.reply_text(
            f"🔗 {link}\nComplete ads then send `{code}`"
        )

    if q.data == "r":
        return await q.message.reply_text(
            f"Invite link:\nhttps://t.me/{BOT_USERNAME}?start={uid}"
        )

    if q.data == "b":
        bal = get_user(uid)["balance"]
        return await q.message.reply_text(f"Balance: ₹{bal:.2f}")

    if q.data == "w":
        return await q.message.reply_text("Send `<UPI_ID> <Amount>` (₹1‑10)")

# --- TEXT HANDLERS ---
async def text_handler(update: Update, context):
    text = update.message.text.strip()
    # Handle withdrawal pattern
    if " " in text:
        upi, amt_s = text.split(maxsplit=1)
        try:
            amt = float(amt_s)
        except:
            return
        u = get_user(update.effective_user.id)
        if 1 <= amt <= 10 and u["balance"] >= amt:
            add_balance(update.effective_user.id, -amt, f"Withdraw {upi}")
            await update.message.reply_text("Withdrawal requested!")
            msg = f"User {update.effective_user.id} withdraw ₹{amt}, UPI: {upi}"
            for aid in ADMIN_IDS:
                await context.bot.send_message(aid, msg)
        return

    # Handle codes (6 char uppercase)
    text = text.upper()
    if len(text) == 6 and text.isalnum():
        codes = load_json(CODES_FILE)
        if text not in codes:
            return await update.message.reply_text("Invalid code.")
        d = codes[text]
        if d["used"]:
            return await update.message.reply_text("Already used.")
        if d["uid"] != update.effective_user.id:
            return await update.message.reply_text("Not your code.")
        d["used"] = True
        save_json(CODES_FILE, codes)
        add_balance(d["uid"], 0.01, "Mission")
        ref = get_user(d["uid"])["referral"]
        if ref:
            add_balance(int(ref), 0.01, "Referral")
            add_balance(int(ref), 0.001, "Ref-Watch")
        return await update.message.reply_text("✅ ₹0.01 added!")
    # else ignore

# --- MAIN ---
if __name__ == "__main__":
    app = ApplicationBuilder().token(BOT_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CallbackQueryHandler(cb_handler))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, text_handler))
    print("Running polling...")
    app.run_polling()
