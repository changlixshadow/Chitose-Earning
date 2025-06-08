import os
import json
import random
import string
import datetime
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    ApplicationBuilder, CommandHandler,
    CallbackQueryHandler, MessageHandler, filters, ContextTypes
)
from shortener_api import create_short_link  # ✅ Replace with actual implementation

# --- CONFIG ---
BOT_TOKEN = "8006836827:AAERFD1tDpBDJhvKm_AHy20uSAzZdoRwbZc"
BOT_USERNAME = "anime_fetch_robot"
ADMIN_IDS = [5759232282]
GROUP_ID = -1002453946876  # ✅ Private channel for posting codes
DAILY_LIMIT = 5

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
        "history": [],
        "pending_code": None
    })
    today = datetime.date.today().isoformat()
    if u["today"] != today:
        u["today"] = today
        u["count"] = 0
        u["pending_code"] = None
    save_json(USERS_FILE, users)
    return u

def add_balance(uid, amt, note):
    users = load_json(USERS_FILE)
    u = users[str(uid)]
    u["balance"] += amt
    u["history"].append(f"+₹{amt:.3f} {note}")
    save_json(USERS_FILE, users)

# --- /start ---
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
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
        caption="Welcome! Earn ₹0.01 per mission.\nUse /shortener to start!",
        reply_markup=InlineKeyboardMarkup(kb)
    )

# --- /shortener ---
async def shortener(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    u = get_user(uid)

    if u["count"] >= DAILY_LIMIT:
        return await update.message.reply_text("❌ Daily mission limit reached.")

    if u.get("pending_code"):
        code = u["pending_code"]
        codes = load_json(CODES_FILE)
        if not codes.get(code, {}).get("used", False):
            short_url = codes[code]["short_url"]
            return await update.message.reply_text(f"🔗 {short_url}\nComplete the ads and return with your code.")

    code = gen_code()
    short_url = create_short_link(code)  # replace with actual shortening

    # Post code to group privately
    await context.bot.send_message(
        chat_id=GROUP_ID,
        text=f"✅ Code for {uid}: `{code}`",
        parse_mode="Markdown"
    )

    # Save code info
    codes = load_json(CODES_FILE)
    codes[code] = {"uid": uid, "used": False, "short_url": short_url}
    save_json(CODES_FILE, codes)

    u["pending_code"] = code
    u["count"] += 1
    users = load_json(USERS_FILE)
    users[str(uid)] = u
    save_json(USERS_FILE, users)

    await update.message.reply_text(f"🔗 {short_url}\nComplete the ads and come back to submit the code.")

# --- Callback Handler ---
async def cb_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    uid = q.from_user.id
    u = get_user(uid)

    if q.data == "m":
        await shortener(q, context)

    elif q.data == "r":
        await q.message.reply_text(
            f"👥 Invite:\nhttps://t.me/{BOT_USERNAME}?start={uid}"
        )

    elif q.data == "b":
        bal = u["balance"]
        await q.message.reply_text(f"💰 Balance: ₹{bal:.3f}")

    elif q.data == "w":
        await q.message.reply_text("Send like this: `<UPI_ID> <Amount>` (₹1‑10)", parse_mode="Markdown")

# --- Text Handler (Code / UPI) ---
async def text_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text.strip()
    uid = update.effective_user.id

    if " " in text:  # Withdrawal
        try:
            upi, amt = text.split(maxsplit=1)
            amt = float(amt)
        except:
            return
        u = get_user(uid)
        if 1 <= amt <= 10 and u["balance"] >= amt:
            add_balance(uid, -amt, f"Withdraw to {upi}")
            await update.message.reply_text("💸 Withdrawal request received!")
            for aid in ADMIN_IDS:
                await context.bot.send_message(aid, f"User {uid} requested ₹{amt:.2f} to {upi}")
        return

    # Code submission
    text = text.upper()
    if len(text) == 6 and text.isalnum():
        codes = load_json(CODES_FILE)
        if text not in codes:
            return await update.message.reply_text("❌ Invalid code.")
        d = codes[text]
        if d["used"]:
            return await update.message.reply_text("⚠️ Code already used.")
        if d["uid"] != uid:
            return await update.message.reply_text("🚫 Not your code.")

        d["used"] = True
        save_json(CODES_FILE, codes)

        u = get_user(uid)
        u["pending_code"] = None
        save_json(USERS_FILE, load_json(USERS_FILE))

        add_balance(uid, 0.01, "Mission")

        # Referral bonus
        ref = u.get("referral")
        if ref:
            add_balance(int(ref), 0.01, "Referral")
            add_balance(int(ref), 0.001, "Ref-Watch")

        await update.message.reply_text("✅ ₹0.01 added!")

# --- MAIN ---
if __name__ == "__main__":
    app = ApplicationBuilder().token(BOT_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("shortener", shortener))
    app.add_handler(CallbackQueryHandler(cb_handler))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, text_handler))
    print("Bot running...")
    app.run_polling()
